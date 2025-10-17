#!/usr/bin/env python3
"""
Debug content parsing issues
"""

import asyncio
from lib.session_manager import SessionManager
from config import BASE_URL
from bs4 import BeautifulSoup


async def debug_member_content():
    """Debug member page content"""
    print("=== Member Content Debug ===")
    
    async with SessionManager() as session:
        await session.ensure_logged_in()
        
        # Test member page
        member_url = f"{BASE_URL}memberlist.php?mode=viewprofile&u=1"
        print(f"[*] Testing member URL: {member_url}")
        
        response = await session.make_request(member_url)
        if response:
            html = response.get("content", "")
            print(f"[*] Member page content length: {len(html)}")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for username
            username_tags = soup.find_all(['h2', 'h3'], class_='username')
            print(f"[*] Found {len(username_tags)} username tags")
            
            for tag in username_tags:
                print(f"  - Username tag: {tag.get_text(strip=True)}")
            
            # Look for any username-like content
            username_links = soup.find_all('a', href=True)
            for link in username_links:
                href = link.get('href', '')
                if 'memberlist.php?mode=viewprofile' in href:
                    print(f"  - Member link: {link.get_text(strip=True)} -> {href}")
            
            # Check for error messages
            error_divs = soup.find_all('div', class_='message-content')
            for div in error_divs:
                print(f"  - Error message: {div.get_text(strip=True)}")
            
            # Save sample content
            with open('debug_member.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("[*] Saved member page to debug_member.html")


async def debug_forum_content():
    """Debug forum page content"""
    print("\n=== Forum Content Debug ===")
    
    async with SessionManager() as session:
        await session.ensure_logged_in()
        
        # Test forum index
        forum_url = f"{BASE_URL}index.php"
        print(f"[*] Testing forum URL: {forum_url}")
        
        response = await session.make_request(forum_url)
        if response:
            html = response.get("content", "")
            print(f"[*] Forum page content length: {len(html)}")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'lxml')
            
            # Look for forum links
            all_links = soup.find_all('a', href=True)
            print(f"[*] Found {len(all_links)} total links")
            
            forum_links = []
            for link in all_links:
                href = link.get('href', '')
                if 'viewforum.php' in href:
                    forum_links.append((link.get_text(strip=True), href))
            
            print(f"[*] Found {len(forum_links)} forum links:")
            for name, href in forum_links[:10]:  # Show first 10
                print(f"  - {name} -> {href}")
            
            # Look for other forum-related patterns
            forum_patterns = ['forum', 'category', 'board']
            for pattern in forum_patterns:
                pattern_links = [link for link in all_links if pattern in link.get('href', '').lower()]
                print(f"[*] Found {len(pattern_links)} links with '{pattern}' pattern")
            
            # Save sample content
            with open('debug_forum.html', 'w', encoding='utf-8') as f:
                f.write(html)
            print("[*] Saved forum page to debug_forum.html")


async def main():
    await debug_member_content()
    await debug_forum_content()


if __name__ == "__main__":
    asyncio.run(main())
