"""Thread scraping utilities for DarkForum."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from config import BASE_URL
from lib.session_manager import SessionManager
from lib.storage import store_data


@dataclass(slots=True)
class ThreadPost:
    """Representation of a single post in a thread print view."""

    author: Optional[str]
    author_id: Optional[str]
    timestamp: Optional[str]
    content: str
    forum_id: Optional[int] = None
    topic_id: Optional[int] = None
    topic_title: Optional[str] = None
    page_offset: Optional[int] = None

    def with_context(self, **context: int | str | None) -> "ThreadPost":
        for key, value in context.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def to_record(self) -> dict:
        record = {
            "author": self.author,
            "author_id": self.author_id,
            "timestamp": self.timestamp,
            "content": self.content,
            "forum_id": self.forum_id,
            "topic_id": self.topic_id,
            "topic_title": self.topic_title,
            "page_offset": self.page_offset,
        }
        return {key: value for key, value in record.items() if value is not None}


@dataclass(slots=True)
class TopicIdentifiers:
    forum_id: Optional[int]
    topic_id: Optional[int]


def ensure_print_view(url: str) -> str:
    """Ensure the provided URL references the print view."""

    parsed = urlparse(urljoin(BASE_URL, url))
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["view"] = ["print"]
    params.pop("start", None)
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def build_page_url(base_print_url: str, offset: int) -> str:
    if offset <= 0:
        return base_print_url

    parsed = urlparse(base_print_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["start"] = [str(offset)]
    new_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=new_query))


def parse_topic_url(url: str) -> TopicIdentifiers:
    parsed = urlparse(urljoin(BASE_URL, url))
    params = parse_qs(parsed.query)

    def _parse_int(values: Iterable[str]) -> Optional[int]:
        for value in values:
            if value.isdigit():
                return int(value)
        return None

    return TopicIdentifiers(
        forum_id=_parse_int(params.get("f", [])),
        topic_id=_parse_int(params.get("t", [])),
    )


def parse_print_view(html: str) -> tuple[list[ThreadPost], Optional[str]]:
    """Parse the print view HTML and return posts along with an optional error message."""

    soup = BeautifulSoup(html, "lxml")
    error_box = soup.select_one("div#message div.message-content")
    if error_box:
        return [], error_box.get_text(strip=True)

    posts: list[ThreadPost] = []
    for container in soup.select("div.post"):
        author_link = container.select_one("div.author a[href*='memberlist.php?mode=viewprofile']")
        author_div = container.select_one("div.author strong")
        author = (author_link or author_div).get_text(strip=True) if (author_link or author_div) else None
        author_id = None
        if author_link:
            href = author_link.get("href", "")
            if "u=" in href:
                author_id = href.split("u=")[-1].split("&")[0]

        timestamp_div = container.select_one("div.date strong")
        timestamp = timestamp_div.get_text(strip=True) if timestamp_div else None

        content_div = container.select_one("div.content")
        content = ""
        if content_div:
            for br in content_div.find_all("br"):
                br.replace_with("\n")
            content = content_div.get_text("\n", strip=True)

        posts.append(ThreadPost(author=author, author_id=author_id, timestamp=timestamp, content=content))

    return posts, None


async def scrape_print_view(
    session: SessionManager,
    base_print_url: str,
    *,
    start: int = 0,
    stop: Optional[int] = None,
    step: int = 10,
    delay: float = 1.0,
    collection: str = "thread_posts",
    context: Optional[dict] = None,
) -> list[ThreadPost]:
    """Scrape a thread print view and store the posts."""

    context = context or {}
    offset = max(0, start)
    previous_signature: Optional[tuple] = None
    all_posts: list[ThreadPost] = []

    while True:
        if stop is not None and offset > stop:
            break

        page_url = build_page_url(base_print_url, offset)
        print(f"[>] Fetching thread page start={offset}: {page_url}")
        response = await session.make_request(page_url)
        if not response:
            print(f"[!] Failed to fetch page at offset {offset}")
            break

        html = response.get("content", "")
        posts, error = parse_print_view(html)
        if error:
            print(f"[x] Error while scraping thread: {error}")
            break
        if not posts:
            print("[!] No posts found on this page, stopping")
            break

        signature = tuple((post.author, post.timestamp, post.content) for post in posts)
        if previous_signature == signature:
            print("[!] Duplicate page detected, stopping pagination")
            break
        previous_signature = signature

        enriched = [post.with_context(page_offset=offset, **context) for post in posts]
        store_data(collection, [post.to_record() for post in enriched])
        all_posts.extend(enriched)
        print(f"[+] Stored {len(posts)} posts from offset {offset}")

        offset += step
        if step <= 0:
            break
        await asyncio.sleep(delay)

    return all_posts


async def scrape_topic(
    session: SessionManager,
    forum_id: int,
    topic_id: int,
    *,
    topic_title: Optional[str] = None,
    delay: float = 1.0,
    step: int = 10,
    stop: Optional[int] = None,
) -> list[ThreadPost]:
    base = ensure_print_view(f"viewtopic.php?f={forum_id}&t={topic_id}")
    context = {"forum_id": forum_id, "topic_id": topic_id, "topic_title": topic_title}
    return await scrape_print_view(
        session,
        base,
        start=0,
        stop=stop,
        step=step,
        delay=delay,
        collection="thread_posts",
        context=context,
    )


async def scrape_thread_from_url(
    session: SessionManager,
    topic_url: str,
    *,
    start: int = 0,
    stop: Optional[int] = None,
    step: int = 10,
    delay: float = 1.0,
) -> list[ThreadPost]:
    """Scrape a thread using an arbitrary topic URL."""

    base_print_url = ensure_print_view(topic_url)
    identifiers = parse_topic_url(topic_url)
    context = {
        "forum_id": identifiers.forum_id,
        "topic_id": identifiers.topic_id,
    }
    return await scrape_print_view(
        session,
        base_print_url,
        start=start,
        stop=stop,
        step=step,
        delay=delay,
        collection="thread_posts",
        context=context,
    )
