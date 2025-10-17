#!/usr/bin/env python3
"""Utilities for managing a Playwright backed scraping session."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional

from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from config import BASE_URL, HEADERS


class SessionManager:
    """Owns a Playwright browser/context pair and handles login persistence."""

    def __init__(self, session_file: str = "session.json", *, headless: bool = True) -> None:
        self.session_file = session_file
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None

    async def __aenter__(self) -> "SessionManager":
        await self.start_session(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:  # type: ignore[override]
        await self.close_session()

    async def start_session(self, *, headless: Optional[bool] = None) -> None:
        """Start Playwright and open a browser context."""

        if headless is not None:
            self.headless = headless

        if self.playwright is not None:
            return

        print("[*] Starting Playwright session...")
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ],
        )

        self.context = await self.browser.new_context(
            user_agent=HEADERS.get(
                "User-Agent",
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36",
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers=HEADERS,
        )

        await self._load_session_state()
        self.page = await self.context.new_page()
        print("[+] Playwright session started")

    async def close_session(self) -> None:
        """Persist session cookies and close the browser."""

        if self.context:
            try:
                await self.context.storage_state(path=self.session_file)
                print(f"[*] Session saved to {self.session_file}")
            except Exception as exc:  # pragma: no cover - defensive logging
                print(f"[!] Failed to save session: {exc}")

        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()

        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        print("[*] Playwright session closed")

    async def ensure_logged_in(self, *, force_login: bool = False) -> bool:
        """Ensure the session represents an authenticated user."""

        if not self.page:
            raise RuntimeError("Session not started. Call start_session() first.")

        if not force_login and await self._looks_logged_in():
            return True

        print("[*] Performing login process...")
        return await self._perform_login()

    async def make_request(self, url: str, method: str = "GET", **kwargs: Any) -> Optional[Dict[str, Any]]:
        """Fetch a URL using the active Playwright page."""

        if not self.page:
            raise RuntimeError("Session not started")

        try:
            if method.upper() == "GET":
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if not response:
                    return None

                await asyncio.sleep(2)
                content = await self.page.content()
                if any(token in content for token in ("Just a moment", "cf-challenge", "challenge-platform")):
                    print(f"[*] Cloudflare challenge detected for {url}, waiting...")
                    await self._handle_cloudflare_challenge()
                    content = await self.page.content()

                return {"content": content, "status": response.status, "url": response.url}

            payload = kwargs.get("payload")
            headers = kwargs.get("headers", {})
            body = json.dumps(payload) if isinstance(payload, (dict, list)) else payload
            script = (
                "fetch('" + url + "', {method: '" + method.upper() + "', headers: "
                + json.dumps(headers)
                + (", body: '" + body + "'" if body else "")
                + "}).then(r => r.text())"
            )
            content = await self.page.evaluate(script)
            return {"content": content, "status": 200, "url": url}

        except Exception as exc:
            print(f"[!] Request failed for {url}: {exc}")
            return None

    async def _looks_logged_in(self) -> bool:
        """Best-effort detection of whether the current page is authenticated."""

        assert self.page is not None

        try:
            await self.page.goto(f"{BASE_URL}index.php", wait_until="domcontentloaded", timeout=15000)
            await asyncio.sleep(2)
            content = (await self.page.content()).lower()

            logout_links = await self.page.query_selector_all('a[href*="logout"], a[href*="ucp.php?mode=logout"]')
            if logout_links:
                print("[+] Already logged in (found logout link)")
                return True

            ucp_links = await self.page.query_selector_all('a[href*="ucp.php?mode=profile"], a[href*="mode=logout"]')
            if ucp_links:
                print("[+] Already logged in (found control panel link)")
                return True

            login_forms = await self.page.query_selector_all('form[action*="ucp.php"], input[name="username"], input[name="password"]')
            if login_forms:
                print("[*] Login form found – authentication required")
                return False

            indicators = ["logout", "user control panel", "my messages"]
            found = [indicator for indicator in indicators if indicator in content]
            if len(found) >= 2:
                print(f"[+] Already logged in (found indicators: {found})")
                return True

            print(f"[*] Not logged in (indicators found: {found})")
            return False

        except Exception as exc:
            print(f"[!] Error checking login status: {exc}")
            return False

    async def _perform_login(self) -> bool:
        assert self.page is not None and self.context is not None

        try:
            login_url = f"{BASE_URL}ucp.php?mode=login"
            print(f"[*] Navigating to login page: {login_url}")
            await self.page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
            await self._handle_cloudflare_challenge()

            print("[*] Please complete login in the browser window…")
            max_wait = 300
            waited = 0
            poll = 5

            while waited < max_wait:
                await asyncio.sleep(poll)
                waited += poll

                try:
                    content = (await self.page.content()).lower()
                except Exception as exc:  # pragma: no cover - defensive
                    print(f"  [!] Error checking login status: {exc}")
                    continue

                if any(keyword in content for keyword in ("logout", "user control panel", "welcome back")):
                    print("[+] Login successful!")
                    await self.context.storage_state(path=self.session_file)
                    return True

                if "ucp.php?mode=login" in self.page.url:
                    print(f"  [*] Still on login page… ({waited}/{max_wait}s)")

            print("[!] Login timeout - please try again")
            return False

        except Exception as exc:
            print(f"[!] Login failed: {exc}")
            return False

    async def _handle_cloudflare_challenge(self) -> None:
        assert self.page is not None

        try:
            max_wait = 120
            waited = 0
            poll = 3

            while waited < max_wait:
                content = (await self.page.content()).lower()
                if not any(
                    token in content
                    for token in (
                        "checking your browser",
                        "cf-challenge",
                        "cloudflare",
                        "challenge-platform",
                        "just a moment",
                        "verifying you are human",
                    )
                ):
                    if waited:
                        print("[+] Cloudflare challenge completed")
                    return

                print(f"  [*] Waiting for Cloudflare… ({waited}/{max_wait}s)")
                await asyncio.sleep(poll)
                waited += poll

            print("[!] Cloudflare challenge timeout - may need manual intervention")

        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[!] Error handling Cloudflare challenge: {exc}")

    async def _load_session_state(self) -> None:
        if not self.context or not os.path.exists(self.session_file):
            return

        try:
            with open(self.session_file, "r", encoding="utf-8") as handle:
                session_data = json.load(handle)

            if isinstance(session_data, dict) and "cookies" in session_data:
                await self.context.add_cookies(session_data["cookies"])
            elif isinstance(session_data, list):
                await self.context.add_cookies(session_data)
            else:
                print(f"[*] Session file {self.session_file} has unknown format; starting fresh")
        except Exception as exc:  # pragma: no cover - defensive logging
            print(f"[!] Failed to load session: {exc}")


async def create_session(*, headless: bool = True, force_login: bool = False) -> SessionManager:
    """Helper to create and initialize a session manager."""

    session = SessionManager(headless=headless)
    await session.start_session()
    await session.ensure_logged_in(force_login=force_login)
    return session


if __name__ == "__main__":
    async def _main() -> None:
        async with SessionManager(headless=False) as session:
            await session.ensure_logged_in(force_login=True)
            print("Session ready!")

    asyncio.run(_main())
