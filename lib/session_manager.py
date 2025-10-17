#!/usr/bin/env python3
"""
Playwright Session Manager for DarkForum Scraper
Handles login, cookie management, and session persistence
"""

import os
import json
import time
import asyncio
from typing import Optional, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from config import BASE_URL, HEADERS


class SessionManager:
    """Manages Playwright sessions, login, and cookie persistence"""
    
    def __init__(self, session_file: str = "session.json"):
        self.session_file = session_file
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
    
    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_session()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close_session()
    
    async def start_session(self, headless: bool = True) -> None:
        """Start a new Playwright session"""
        print("[*] Starting Playwright session...")
        self.playwright = await async_playwright().start()
        
        # Launch browser with stealth settings
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-web-security",
                "--disable-features=VizDisplayCompositor",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        
        # Create context with realistic settings
        self.context = await self.browser.new_context(
            user_agent=HEADERS.get("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"),
            viewport={"width": 1366, "height": 768},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers=HEADERS
        )
        
        # Load existing session if available
        if os.path.exists(self.session_file):
            try:
                with open(self.session_file, 'r') as f:
                    session_data = json.load(f)
                    # Handle both old format (cookies array) and new format (storage state)
                    if 'cookies' in session_data:
                        await self.context.add_cookies(session_data['cookies'])
                        print(f"[*] Loaded existing session from {self.session_file}")
                    elif isinstance(session_data, list):
                        # Old format - direct cookies array
                        await self.context.add_cookies(session_data)
                        print(f"[*] Loaded existing session from {self.session_file}")
                    else:
                        print(f"[*] Session file format not recognized, starting fresh")
            except Exception as e:
                print(f"[!] Failed to load session: {e}")
                print(f"[*] Starting with fresh session")
        
        self.page = await self.context.new_page()
        print("[+] Playwright session started")
    
    async def close_session(self) -> None:
        """Close the Playwright session and save cookies"""
        if self.context:
            try:
                # Save session state
                await self.context.storage_state(path=self.session_file)
                print(f"[*] Session saved to {self.session_file}")
            except Exception as e:
                print(f"[!] Failed to save session: {e}")
        
        if self.browser:
            await self.browser.close()
        
        if self.playwright:
            await self.playwright.stop()
        
        print("[*] Playwright session closed")
    
    async def ensure_logged_in(self, force_login: bool = False) -> bool:
        """Ensure user is logged in, perform login if necessary"""
        if not self.page:
            raise RuntimeError("Session not started. Call start_session() first.")
        
        # Check if already logged in - be VERY strict
        if not force_login:
            try:
                await self.page.goto(f"{BASE_URL}index.php", wait_until="domcontentloaded", timeout=15000)
                await asyncio.sleep(3)  # Wait longer for page to load
                
                # Check for STRICT login indicators - must be very specific
                content = await self.page.content()
                
                # Look for very specific logged-in elements
                try:
                    # Check for actual logout link (not just text)
                    logout_links = await self.page.query_selector_all('a[href*="logout"], a[href*="ucp.php?mode=logout"]')
                    if logout_links and len(logout_links) > 0:
                        print("[+] Already logged in (found logout link)")
                        return True
                    
                    # Check for user control panel link
                    ucp_links = await self.page.query_selector_all('a[href*="ucp.php?mode=profile"]')
                    if ucp_links and len(ucp_links) > 0:
                        print("[+] Already logged in (found UCP link)")
                        return True
                        
                except Exception as e:
                    print(f"[!] Error checking specific elements: {e}")
                
                # Check for login form (if present, we're NOT logged in)
                login_forms = await self.page.query_selector_all('form[action*="ucp.php"], input[name="username"], input[name="password"]')
                if login_forms and len(login_forms) > 0:
                    print("[*] Login form found - NOT logged in")
                    return False
                
                # Very strict text check
                strict_indicators = ["logout", "user control panel", "my messages"]
                found_indicators = [indicator for indicator in strict_indicators if indicator in content.lower()]
                
                if len(found_indicators) >= 2:  # Need at least 2 indicators
                    print(f"[+] Already logged in (found indicators: {found_indicators})")
                    return True
                else:
                    print(f"[*] Not logged in (found only: {found_indicators})")
                    return False
                    
            except Exception as e:
                print(f"[!] Error checking login status: {e}")
                print("[*] Will attempt login")
        
        # Need to login
        print("[*] Performing login process...")
        return await self.perform_login()
    
    async def perform_login(self) -> bool:
        """Perform interactive login"""
        try:
            # Navigate to login page
            login_url = f"{BASE_URL}ucp.php?mode=login"
            print(f"[*] Navigating to login page: {login_url}")
            await self.page.goto(login_url, wait_until="domcontentloaded", timeout=30000)
            
            # Wait for Cloudflare challenge if present
            await self.handle_cloudflare_challenge()
            
            # Wait for user to complete login
            print("[*] Please complete login in the browser window...")
            print("[*] Waiting for login completion (max 5 minutes)...")
            
            # Wait for login completion
            max_wait = 300  # 5 minutes
            waited = 0
            poll_interval = 5
            
            while waited < max_wait:
                try:
                    # Check if we're on a logged-in page
                    current_url = self.page.url
                    content = await self.page.content()
                    
                    # Look for login success indicators
                    if any(indicator in content.lower() for indicator in [
                        "logout", "log out", "profile", "my messages", 
                        "user control panel", "welcome back"
                    ]):
                        print("[+] Login successful!")
                        # Save session
                        await self.context.storage_state(path=self.session_file)
                        return True
                    
                    # Check if still on login page
                    if "ucp.php?mode=login" in current_url or "login" in current_url.lower():
                        print(f"  [*] Still on login page... ({waited}/{max_wait}s)")
                    else:
                        print(f"  [*] Navigated to: {current_url}")
                    
                except Exception as e:
                    print(f"  [!] Error checking login status: {e}")
                
                await asyncio.sleep(poll_interval)
                waited += poll_interval
            
            print("[!] Login timeout - please try again")
            return False
            
        except Exception as e:
            print(f"[!] Login failed: {e}")
            return False
    
    async def handle_cloudflare_challenge(self) -> None:
        """Handle Cloudflare challenge if present"""
        try:
            content = await self.page.content()
            if any(indicator in content.lower() for indicator in [
                "checking your browser", "cf-challenge", "cloudflare", 
                "please wait", "verifying you are human", "just a moment"
            ]):
                print("[*] Cloudflare challenge detected, waiting for completion...")
                
                # Wait for challenge to complete
                max_wait = 120  # 2 minutes
                waited = 0
                poll_interval = 3
                
                while waited < max_wait:
                    await asyncio.sleep(poll_interval)
                    waited += poll_interval
                    
                    content = await self.page.content()
                    if not any(indicator in content.lower() for indicator in [
                        "checking your browser", "cf-challenge", "please wait", 
                        "just a moment", "challenge-platform"
                    ]):
                        print("[+] Cloudflare challenge completed")
                        # Wait a bit more for page to fully load
                        await asyncio.sleep(2)
                        break
                    
                    print(f"  [*] Waiting for Cloudflare... ({waited}/{max_wait}s)")
                
                if waited >= max_wait:
                    print("[!] Cloudflare challenge timeout - may need manual intervention")
                    
        except Exception as e:
            print(f"[!] Error handling Cloudflare challenge: {e}")
    
    async def get_session_cookies(self) -> list:
        """Get current session cookies"""
        if not self.context:
            return []
        
        try:
            cookies = await self.context.cookies()
            return cookies
        except Exception as e:
            print(f"[!] Error getting cookies: {e}")
            return []
    
    async def make_request(self, url: str, method: str = "GET", **kwargs) -> Optional[Dict[str, Any]]:
        """Make a request using the current session"""
        if not self.page:
            raise RuntimeError("Session not started")
        
        try:
            if method.upper() == "GET":
                response = await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            else:
                # For other methods, use page.evaluate to make requests
                response = await self.page.evaluate(f"""
                    fetch('{url}', {{
                        method: '{method.upper()}',
                        headers: {json.dumps(kwargs.get('headers', {}))}
                    }}).then(r => r.text())
                """)
                return {"content": response}
            
            if response:
                # Wait a bit for any Cloudflare challenges to complete
                await asyncio.sleep(2)
                
                # Check for Cloudflare challenge
                content = await self.page.content()
                if "Just a moment" in content or "cf-challenge" in content or "challenge-platform" in content:
                    print(f"[*] Cloudflare challenge detected for {url}, waiting...")
                    await self.handle_cloudflare_challenge()
                    # Get content again after challenge
                    content = await self.page.content()
                
                return {
                    "content": content,
                    "status": response.status,
                    "url": response.url
                }
            return None
            
        except Exception as e:
            print(f"[!] Request failed for {url}: {e}")
            return None
    
    def get_sync_session(self):
        """Get a synchronous session for use with requests library"""
        if not self.context:
            raise RuntimeError("Session not started")
        
        # Extract cookies for use with requests
        cookies = asyncio.run(self.get_session_cookies())
        cookie_dict = {}
        for cookie in cookies:
            cookie_dict[cookie['name']] = cookie['value']
        
        return {
            'cookies': cookie_dict,
            'headers': HEADERS
        }


# Convenience functions for easy usage
async def create_session(headless: bool = True, force_login: bool = False) -> SessionManager:
    """Create and initialize a session manager"""
    session = SessionManager()
    await session.start_session(headless=headless)
    await session.ensure_logged_in(force_login=force_login)
    return session


def get_session_for_requests() -> Dict[str, Any]:
    """Get session data for use with requests library"""
    session = SessionManager()
    return session.get_sync_session()


if __name__ == "__main__":
    async def main():
        async with SessionManager() as session:
            await session.ensure_logged_in(force_login=True)
            print("Session ready!")
    
    asyncio.run(main())
