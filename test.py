#!/usr/bin/env python3
"""
Playwright-driven PhpBB member scraper (full-file update)

- Uses Playwright (Chromium) for all fetching so Cloudflare sees a single trusted browser fingerprint.
- Saves and reuses Playwright storage state (session.json) so you don't have to manually log in every run.
- Parses each member profile HTML with BeautifulSoup and stores results via lib.storage.store_data.
- Simple CLI args to control range, pause, and whether to force interactive login.

Requirements:
    pip install playwright bs4
    playwright install chromium

Usage:
    python scraper_playwright.py --start 1 --end 500 --pause 1.0
"""
from __future__ import annotations

import os
import time
import json
import argparse
import asyncio
from typing import Optional

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from lib.storage import store_data
from config import BASE_URL, HEADERS

MEMBER_URL = f"{BASE_URL}memberlist.php?mode=viewprofile&u="
SESSION_FILE = "session.json"


# -------------------------
# PARSER
# -------------------------
def extract_text(soup: BeautifulSoup, selector: str) -> Optional[str]:
    el = soup.select_one(selector)
    return el.get_text(strip=True) if el else None


def parse_member(html: str, uid: int) -> dict:
    """Parse a PhpBB member profile page HTML into a dict."""
    soup = BeautifulSoup(html, "lxml")

    # Detect missing or error message
    error_box = soup.select_one("div#message div.message-content")
    if error_box:
        msg = error_box.get_text(strip=True)
        return {"error": True, "message": msg, "uid": uid}

    # Adjust selectors as needed for your forum theme
    username = extract_text(soup, "h2.username") or extract_text(soup, "a.username")
    rank = extract_text(soup, "dd.rank")
    join_date = extract_text(soup, "dd.joined")
    total_posts = extract_text(soup, "dd.posts")
    location = extract_text(soup, "dd.from")

    return {
        "uid": uid,
        "username": username,
        "rank": rank,
        "join_date": join_date,
        "total_posts": total_posts,
        "location": location,
        "error": False,
    }


# -------------------------
# PLAYWRIGHT UTILITIES
# -------------------------
async def ensure_session_state(force_interactive: bool = False, cookies: Optional[list] = None) -> None:
    """
    Ensure session.json exists. If not, launch a visible browser for interactive login or
    use provided cookies to try to clear Cloudflare and then save storage_state.
    """
    if os.path.exists(SESSION_FILE) and not force_interactive:
        print(f"[*] Found existing {SESSION_FILE}, reusing it.")
        return

    print("[*] No saved Playwright session found (or forced interactive). Launching Chromium for login/verification...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=["--disable-blink-features=AutomationControlled"])
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/141.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
        )

        # If the caller provides cookies, add them before navigating.
        if cookies:
            print("[*] Adding provided cookies to the context.")
            await context.add_cookies(cookies)

        page = await context.new_page()
        print(f"[*] Opening {BASE_URL} in the browser. Complete any login/CAPTCHA if necessary.")
        await page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60000)

        # Wait for Cloudflare challenge or user login. We try a series of checks:
        max_wait = 120  # seconds to wait for user or CF to clear
        waited = 0
        poll = 2
        while waited < max_wait:
            content = await page.content()
            # heuristics: logged-in page often has profile/username link, or CF challenge text appears otherwise
            if any(token in content.lower() for token in ("log out", "logout", "profile", "view profile", "my messages")):
                print("[+] Looks like you're logged in or the page shows profile links.")
                break
            if any(token in content for token in ("Checking your browser", "cf-challenge", "cloudflare")):
                print("[*] Cloudflare JS challenge detected, waiting for it to complete...")
            # else, continue waiting for manual login or JS challenge resolution
            await asyncio.sleep(poll)
            waited += poll
            print(f"  waited {waited}/{max_wait}s...")

        # After waiting, save storage state so subsequent runs use this session
        await context.storage_state(path=SESSION_FILE)
        print(f"[+] Saved Playwright storage state -> {SESSION_FILE}")
        await browser.close()


async def new_context_from_state(headless: bool = True) -> BrowserContext:
    """Create a Playwright browser context loaded with the saved storage state."""
    async with async_playwright() as p:
        # Note: we create a short-lived browser here only to return a context.
        # But because async_playwright() is a context manager, we need to manage lifecycle differently.
        # To make a persistent context for scraping we will open browser in the scraping function instead.
        raise RuntimeError("Do not call new_context_from_state() directly - see scrape_with_playwright()")


# -------------------------
# SCRAPING (Playwright-based)
# -------------------------
async def scrape_with_playwright(start: int, end: int, pause: float = 1.0, headless: bool = False) -> None:
    """
    Main scraping loop that uses Playwright to fetch each profile page and BeautifulSoup to parse.
    """
    if not os.path.exists(SESSION_FILE):
        raise RuntimeError(f"Missing {SESSION_FILE} — run ensure_session_state() first to create it.")

    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
        context: BrowserContext = await browser.new_context(storage_state=SESSION_FILE)
        # Ensure headers align with config for any direct requests Playwright might make
        # Playwright's page requests will still carry browser-level headers; we include HEADERS to be explicit.
        page: Page = await context.new_page()
        await page.set_extra_http_headers(HEADERS)

        print(f"[*] Starting scrape from uid={start} to uid={end} (pause={pause}s) - headless={headless}")
        error_streak = 0

        try:
            for uid in range(start, end + 1):
                member_url = f"{MEMBER_URL}{uid}"
                print(f"\n########## MEMBER {uid} ########## -> {member_url}")

                try:
                    # Navigate and wait for DOM; Cloudflare should already trust this context
                    resp = await page.goto(member_url, wait_until="domcontentloaded", timeout=30000)
                    status = resp.status if resp else None
                    print(f"HTTP status: {status}")

                    # Short delay to let client-side content settle (if any)
                    await asyncio.sleep(0.3)
                    html = await page.content()

                    # Quick checks for forbidden / login page
                    if status == 403 or "Access denied" in html or "You don't have permission" in html:
                        print("[!] Server returned 403/forbidden for this request.")
                        error_streak += 1
                    elif "The requested user does not exist" in html:
                        print("[x] User does not exist.")
                        error_streak = 0
                    else:
                        data = parse_member(html, uid)
                        if data and not data.get("error"):
                            store_data("members", [data])
                            print(f"[+] Member {uid}: {data.get('username')}")
                            error_streak = 0
                        else:
                            print(f"[x] Member {uid}: missing or invalid (parse error or flagged).")
                            error_streak += 1

                except Exception as e:
                    print(f"[!] Exception fetching member {uid}: {e}")
                    error_streak += 1

                # Stop if too many consecutive errors (protective)
                if error_streak >= 100:
                    print("[!] Too many consecutive failures. Stopping.")
                    break

                # polite pause
                await asyncio.sleep(pause)

        finally:
            await context.close()
            await browser.close()
            print("[*] Browser closed, scraping finished.")


# -------------------------
# COMMAND-LINE INTERFACE
# -------------------------
def main():
    parser = argparse.ArgumentParser(description="Playwright-backed PhpBB member scraper")
    parser.add_argument("--start", type=int, default=1, help="Start UID")
    parser.add_argument("--end", type=int, default=13100, help="End UID")
    parser.add_argument("--pause", type=float, default=1.0, help="Pause between requests (seconds)")
    parser.add_argument("--headless", action="store_true", help="Run Playwright in headless mode for scraping (not for interactive login)")
    parser.add_argument("--force-login", action="store_true", help="Force the interactive login flow even if session.json exists")
    parser.add_argument("--cookies-file", type=str, default=None, help="Optional JSON file with cookies to add before verification")
    args = parser.parse_args()

    cookies = None
    if args.cookies_file:
        if os.path.exists(args.cookies_file):
            with open(args.cookies_file, "r") as fh:
                cookies = json.load(fh)
            print(f"[*] Loaded {len(cookies)} cookies from {args.cookies_file}")
        else:
            print(f"[!] Cookies file not found: {args.cookies_file} (ignoring)")

    # Step 1: ensure we have a saved Playwright session (interactive if needed)
    # This will open a visible browser if session.json doesn't exist or if force_login True.
    asyncio.run(ensure_session_state(force_interactive=args.force_login, cookies=cookies))

    # Step 2: run the Playwright scraping loop (can be headless if you already have a session.json)
    asyncio.run(scrape_with_playwright(start=args.start, end=args.end, pause=args.pause, headless=args.headless))


if __name__ == "__main__":
    main()
