#!/usr/bin/env python3
"""
Playwright-based phpBB member profile scraper
---------------------------------------------
Uses a real Chromium browser session to bypass Cloudflare.
Scrapes member profiles sequentially and saves to JSON.

Usage:
    python3 scrape_members_playwright.py --start 1 --end 13000 --pause 1.0 --headless False
"""

import os
import re
import json
import time
import argparse
import asyncio
from bs4 import BeautifulSoup
from lib.storage import store_data
from lib.session_manager import SessionManager

BASE_URL = "https://www.darkforum.com/memberlist.php?mode=viewprofile&u={uid}"
OUTPUT_DIR = "output/members"
SESSION_PATH = "session.json"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())

def parse_profile(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    profile = {}

    username_tag = soup.find("h2", class_="username") or soup.find("h3", class_="username")
    profile["username"] = clean_text(username_tag.text) if username_tag else None

    def extract_info(label):
        el = soup.find(string=re.compile(label, re.I))
        if el and el.parent:
            nxt = el.find_next("dd")
            return clean_text(nxt.text) if nxt else None
        return None

    profile["joined"] = extract_info("Joined")
    profile["posts"] = extract_info("Total posts")
    profile["rank"] = extract_info("Rank")
    profile["warnings"] = extract_info("Warnings")
    profile["contact"] = extract_info("Contact")

    sig = soup.find("div", class_="signature")
    if sig:
        profile["signature"] = clean_text(sig.text)
    else:
        about = soup.find("div", class_="panel") or soup.find("div", id="profile-field-bio")
        profile["signature"] = clean_text(about.text) if about else None

    avatar_tag = soup.find("img", {"class": re.compile("avatar", re.I)})
    profile["avatar"] = avatar_tag["src"] if avatar_tag and "src" in avatar_tag.attrs else None

    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(x in href for x in ("http", "mailto")):
            links.append(href)
    profile["links"] = list(sorted(set(links)))

    return profile

async def scrape_member_async(session: SessionManager, uid: int) -> dict | None:
    """Async version of member scraping"""
    url = BASE_URL.format(uid=uid)
    try:
        response = await session.make_request(url)
        if not response:
            print(f"[!] Failed to fetch UID {uid}")
            return None
            
        html = response.get("content", "")
    except Exception as e:
        print(f"[!] Error fetching UID {uid}: {e}")
        return None

    if "cf-error" in html or "Attention Required!" in html:
        print(f"[!] Cloudflare challenge detected on UID {uid}.")
        return None

    profile = parse_profile(html)
    if not profile.get("username"):
        print(f"[!] UID {uid}: No username found.")
        return None

    # Add UID to profile data
    profile['uid'] = uid
    
    # Store using the storage system (will use database or file based on config)
    store_data("members", [profile])
    
    # Also save individual file for backup
    filepath = os.path.join(OUTPUT_DIR, f"{uid}_{profile['username']}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    print(f"[+] Saved UID {uid} ({profile['username']})")
    return profile


def scrape_member(page, uid: int) -> dict | None:
    """Legacy sync version - kept for compatibility"""
    url = BASE_URL.format(uid=uid)
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
    except Exception as e:
        print(f"[!] Timeout or navigation error on UID {uid}: {e}")
        return None

    html = page.content()
    if "cf-error" in html or "Attention Required!" in html:
        print(f"[!] Cloudflare challenge detected on UID {uid}.")
        return None

    profile = parse_profile(html)
    if not profile.get("username"):
        print(f"[!] UID {uid}: No username found.")
        return None

    # Add UID to profile data
    profile['uid'] = uid
    
    # Store using the storage system (will use database or file based on config)
    store_data("members", [profile])
    
    # Also save individual file for backup
    filepath = os.path.join(OUTPUT_DIR, f"{uid}_{profile['username']}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(profile, f, indent=2, ensure_ascii=False)

    print(f"[+] Saved UID {uid} ({profile['username']})")
    return profile

async def scrape_members_async(start_uid=1, stop_uid=None, delay=1.0, headless=True):
    """
    Async member scraping using session manager
    """
    print(f"[>] Starting member scraping: UIDs {start_uid} to {stop_uid or 'end'}, delay={delay}s")
    
    async with SessionManager() as session:
        # Ensure we're logged in
        await session.ensure_logged_in()
        
        for uid in range(start_uid, (stop_uid or start_uid) + 1):
            await scrape_member_async(session, uid)
            await asyncio.sleep(delay)


def scrape_members(start_uid=1, stop_uid=None, delay=1.0, headless=True):
    """
    Main function to scrape members - compatible with main.py interface
    """
    asyncio.run(scrape_members_async(start_uid, stop_uid, delay, headless))


def main():
    """Command-line interface for member scraper"""
    parser = argparse.ArgumentParser(description="DarkForum Member Scraper")
    parser.add_argument("--start", type=int, default=1, help="Start UID")
    parser.add_argument("--end", type=int, default=100, help="End UID")
    parser.add_argument("--pause", type=float, default=1.0, help="Pause between requests (seconds)")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    args = parser.parse_args()
    
    scrape_members(
        start_uid=args.start,
        stop_uid=args.end,
        delay=args.pause,
        headless=args.headless
    )

if __name__ == "__main__":
    main()
