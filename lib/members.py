"""Member profile scraping helpers."""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup

from config import BASE_URL
from lib.session_manager import SessionManager
from lib.storage import store_data

PROFILE_URL = f"{BASE_URL}memberlist.php?mode=viewprofile&u={{uid}}"
OUTPUT_DIR = Path("output/members")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class MemberProfile:
    """Structured representation of a forum member."""

    uid: int
    username: str
    rank: Optional[str] = None
    join_date: Optional[str] = None
    total_posts: Optional[str] = None
    location: Optional[str] = None
    warnings: Optional[str] = None
    contact: Optional[str] = None
    signature: Optional[str] = None
    avatar: Optional[str] = None
    links: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        data = {
            "uid": self.uid,
            "username": self.username,
            "rank": self.rank,
            "join_date": self.join_date,
            "total_posts": self.total_posts,
            "location": self.location,
            "warnings": self.warnings,
            "contact": self.contact,
            "signature": self.signature,
            "avatar": self.avatar,
            "links": list(self.links),
        }
        return {key: value for key, value in data.items() if value is not None}


def _clean_text(text: str | None) -> Optional[str]:
    if text is None:
        return None
    stripped = " ".join(text.split())
    return stripped if stripped else None


def _extract_info(soup: BeautifulSoup, label: str) -> Optional[str]:
    element = soup.find(string=lambda value: isinstance(value, str) and label.lower() in value.lower())
    if not element:
        return None
    container = element.find_next("dd") if hasattr(element, "find_next") else None
    if not container:
        return None
    return _clean_text(container.text)


def parse_profile(html: str, uid: int) -> Optional[MemberProfile]:
    """Parse the member profile HTML into a :class:`MemberProfile`."""

    soup = BeautifulSoup(html, "lxml")
    error_box = soup.select_one("div#message div.message-content")
    if error_box:
        message = error_box.get_text(strip=True)
        print(f"[x] UID {uid}: {message}")
        return None

    username_tag = soup.find(["h2", "h3"], class_="username") or soup.find("a", class_="username")
    username = _clean_text(username_tag.text if username_tag else None)
    if not username:
        print(f"[!] UID {uid}: Could not locate username")
        return None

    links = {
        anchor["href"]
        for anchor in soup.find_all("a", href=True)
        if any(prefix in anchor["href"] for prefix in ("http", "mailto"))
    }

    signature_container = soup.find("div", class_="signature") or soup.find("div", id="profile-field-bio")
    avatar_tag = soup.find("img", class_=lambda value: value and "avatar" in value)

    profile = MemberProfile(
        uid=uid,
        username=username,
        rank=_extract_info(soup, "Rank"),
        join_date=_extract_info(soup, "Joined"),
        total_posts=_extract_info(soup, "Total posts"),
        location=_extract_info(soup, "Location"),
        warnings=_extract_info(soup, "Warnings"),
        contact=_extract_info(soup, "Contact"),
        signature=_clean_text(signature_container.text if signature_container else None),
        avatar=avatar_tag.get("src") if avatar_tag else None,
        links=tuple(sorted(links)),
    )

    return profile


def _write_backup(profile: MemberProfile) -> None:
    filename = OUTPUT_DIR / f"{profile.uid}_{profile.username}.json"
    with filename.open("w", encoding="utf-8") as handle:
        json.dump(profile.to_dict(), handle, indent=2, ensure_ascii=False)


async def fetch_member(session: SessionManager, uid: int) -> Optional[MemberProfile]:
    url = PROFILE_URL.format(uid=uid)
    print(f"[>] Fetching member {uid}: {url}")

    response = await session.make_request(url)
    if not response:
        print(f"[!] Failed to fetch UID {uid}")
        return None

    html = response.get("content", "")
    if "cf-error" in html or "Attention Required" in html:
        print(f"[!] Cloudflare challenge while fetching UID {uid}")
        return None

    return parse_profile(html, uid)


async def scrape_members(
    *,
    session: Optional[SessionManager] = None,
    start_uid: int = 1,
    stop_uid: Optional[int] = None,
    delay: float = 1.0,
) -> list[MemberProfile]:
    """Scrape member profiles sequentially and store them using the storage backend."""

    if stop_uid is None:
        stop_uid = start_uid

    scraped: list[MemberProfile] = []
    managed_session = session is None

    if managed_session:
        session = SessionManager()
        await session.start_session()
        await session.ensure_logged_in()

    assert session is not None

    try:
        for uid in range(start_uid, stop_uid + 1):
            profile = await fetch_member(session, uid)
            if not profile:
                await asyncio.sleep(delay)
                continue

            store_data("members", [profile.to_dict()])
            _write_backup(profile)
            scraped.append(profile)
            print(f"[+] Saved UID {profile.uid} ({profile.username})")
            await asyncio.sleep(delay)
    finally:
        if managed_session:
            await session.close_session()

    return scraped


async def _run_from_cli(args: argparse.Namespace) -> None:
    async with SessionManager(headless=not args.show_browser) as session:
        await session.ensure_logged_in(force_login=args.force_login)
        await scrape_members(
            session=session,
            start_uid=args.start,
            stop_uid=args.stop,
            delay=args.delay,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="DarkForum member scraper")
    parser.add_argument("--start", type=int, default=1, help="Start UID")
    parser.add_argument("--stop", type=int, default=1, help="Stop UID (inclusive)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests in seconds")
    parser.add_argument("--show-browser", action="store_true", help="Run Playwright in headed mode")
    parser.add_argument("--force-login", action="store_true", help="Always prompt for login")
    args = parser.parse_args()

    asyncio.run(_run_from_cli(args))


if __name__ == "__main__":
    main()
