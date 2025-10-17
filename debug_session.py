#!/usr/bin/env python3
"""
Debug session and login issues
"""

import asyncio
import json
from lib.session_manager import SessionManager
from config import BASE_URL


async def debug_session():
    """Debug session and login process"""
    print("=== Session Debug ===")
    
    # Check if session file exists
    try:
        with open("session.json", "r") as f:
            session_data = json.load(f)
            print(f"[*] Session file exists: {type(session_data)}")
            if isinstance(session_data, dict):
                print(f"[*] Session keys: {list(session_data.keys())}")
            elif isinstance(session_data, list):
                print(f"[*] Session has {len(session_data)} items")
    except FileNotFoundError:
        print("[*] No session file found")
    except Exception as e:
        print(f"[!] Error reading session file: {e}")
    
    # Test session manager
    print("\n[*] Testing session manager...")
    session = SessionManager()
    
    try:
        await session.start_session(headless=False)  # Visible browser
        print("[+] Session started")
        
        # Test navigation
        print(f"[*] Navigating to {BASE_URL}")
        await session.page.goto(BASE_URL, wait_until="domcontentloaded", timeout=15000)
        await asyncio.sleep(3)
        
        # Check page content
        content = await session.page.content()
        print(f"[*] Page loaded, content length: {len(content)}")
        
        # Check for login indicators
        login_indicators = ["logout", "log out", "profile", "my messages", "user control panel"]
        found_indicators = [indicator for indicator in login_indicators if indicator in content.lower()]
        print(f"[*] Login indicators found: {found_indicators}")
        
        # Check for specific elements
        try:
            elements = await session.page.query_selector_all('a[href*="ucp.php"], a[href*="logout"], .username')
            print(f"[*] Found {len(elements)} user-related elements")
        except Exception as e:
            print(f"[!] Error checking elements: {e}")
        
        # Save current state
        await session.context.storage_state(path="debug_session.json")
        print("[*] Saved debug session")
        
    except Exception as e:
        print(f"[!] Session error: {e}")
    finally:
        await session.close_session()


if __name__ == "__main__":
    asyncio.run(debug_session())
