"""Forum discovery and scraping helpers."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import parse_qs, urljoin, urlparse

from bs4 import BeautifulSoup

from config import BASE_URL
from lib.session_manager import SessionManager
from lib.storage import store_data
from lib import topic

PAGE_SIZE = 30


@dataclass(slots=True)
class ForumInfo:
    forum_id: int
    name: str
    url: str

    def to_record(self) -> dict:
        return {"forum_id": self.forum_id, "forum_name": self.name, "forum_url": self.url}


@dataclass(slots=True)
class TopicInfo:
    forum_id: int
    topic_id: int
    title: str
    url: str

    def to_record(self) -> dict:
        return {
            "forum_id": self.forum_id,
            "topic_id": self.topic_id,
            "topic_title": self.title,
            "topic_url": self.url,
        }


def _parse_first_int(values: Iterable[str]) -> Optional[int]:
    for value in values:
        if value.isdigit():
            return int(value)
    return None


def _extract_forum_id(href: str) -> Optional[int]:
    parsed = urlparse(urljoin(BASE_URL, href))
    params = parse_qs(parsed.query)
    return _parse_first_int(params.get("f", []))


def _extract_topic_id(href: str) -> Optional[int]:
    parsed = urlparse(urljoin(BASE_URL, href))
    params = parse_qs(parsed.query)
    return _parse_first_int(params.get("t", []))


async def fetch_forum_index(session: SessionManager) -> list[ForumInfo]:
    url = urljoin(BASE_URL, "index.php")
    response = await session.make_request(url)
    if not response:
        print("[!] Failed to fetch forum index")
        return []

    soup = BeautifulSoup(response.get("content", ""), "lxml")
    seen: set[int] = set()
    forums: list[ForumInfo] = []

    for anchor in soup.find_all("a", href=True):
        forum_id = _extract_forum_id(anchor["href"])
        if forum_id is None or forum_id in seen:
            continue
        name = anchor.get_text(strip=True)
        if not name:
            continue
        seen.add(forum_id)
        forums.append(ForumInfo(forum_id=forum_id, name=name, url=urljoin(BASE_URL, anchor["href"])))

    print(f"[+] Discovered {len(forums)} forums")
    return forums


async def fetch_topic_page(session: SessionManager, forum: ForumInfo, page: int) -> list[TopicInfo]:
    start = page * PAGE_SIZE
    url = urljoin(BASE_URL, f"viewforum.php?f={forum.forum_id}&start={start}")
    print(f"  [>] Fetching forum {forum.forum_id} page {page + 1}: {url}")
    response = await session.make_request(url)
    if not response:
        print(f"  [!] Failed to fetch forum {forum.forum_id} page {page + 1}")
        return []

    html = response.get("content", "")
    if "No topics" in html or "No posts" in html:
        return []

    soup = BeautifulSoup(html, "lxml")
    topics: list[TopicInfo] = []
    for anchor in soup.find_all("a", href=True):
        topic_id = _extract_topic_id(anchor["href"])
        if topic_id is None:
            continue
        title = anchor.get_text(strip=True)
        if not title:
            continue
        topics.append(
            TopicInfo(
                forum_id=forum.forum_id,
                topic_id=topic_id,
                title=title,
                url=urljoin(BASE_URL, anchor["href"]),
            )
        )

    return topics


async def scrape_forum(
    session: SessionManager,
    forum: ForumInfo,
    *,
    delay: float = 1.0,
    limit_pages: Optional[int] = None,
) -> list[TopicInfo]:
    print(f"\n[>] Scraping forum: {forum.name} (ID: {forum.forum_id})")

    seen_topics: set[int] = set()
    page = 0
    collected: list[TopicInfo] = []

    while True:
        if limit_pages is not None and page >= limit_pages:
            break

        topics = await fetch_topic_page(session, forum, page)
        unique_topics = [topic_info for topic_info in topics if topic_info.topic_id not in seen_topics]

        if not unique_topics:
            break

        seen_topics.update(topic_info.topic_id for topic_info in unique_topics)
        collected.extend(unique_topics)
        store_data("forum_topics", [topic_info.to_record() for topic_info in unique_topics])
        print(f"  [+] Stored {len(unique_topics)} topics from page {page + 1}")

        for topic_info in unique_topics:
            print(f"    [>] Scraping topic: {topic_info.title}")
            await topic.scrape_topic(
                session,
                forum_id=topic_info.forum_id,
                topic_id=topic_info.topic_id,
                topic_title=topic_info.title,
                delay=delay,
            )
            await asyncio.sleep(delay)

        page += 1
        await asyncio.sleep(delay)

    return collected


async def scrape_all_forums(
    *,
    session: Optional[SessionManager] = None,
    delay: float = 1.0,
    limit_pages: Optional[int] = None,
) -> list[ForumInfo]:
    managed_session = session is None

    if managed_session:
        session = SessionManager()
        await session.start_session()
        await session.ensure_logged_in()

    assert session is not None

    try:
        forums = await fetch_forum_index(session)
        for forum in forums:
            await scrape_forum(session, forum, delay=delay, limit_pages=limit_pages)
            await asyncio.sleep(delay)
        return forums
    finally:
        if managed_session:
            await session.close_session()
