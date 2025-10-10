import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

BASE = "https://www.darkforum.com/"

def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()

def parse_forum_index(html: str):
    """
    Extract forums from the board index page.
    Returns list of dicts: {forum_id, name, url}
    """
    soup = BeautifulSoup(html, "lxml")
    forums = []
    for a in soup.select("a.forumtitle"):
        name = _clean(a.text)
        href = a.get("href") or ""
        url = urljoin(BASE, href)
        fid = None
        # Try query param first (viewforum.php?f=181)
        q = parse_qs(urlparse(url).query)
        if "f" in q and q["f"]:
            try:
                fid = int(q["f"][0])
            except Exception:
                pass
        # Fallback to slug pattern like "...-f181/"
        if fid is None:
            m = re.search(r"-f(\d+)/?", url)
            if m:
                fid = int(m.group(1))
        if fid is None:
            continue
        forums.append({"forum_id": fid, "name": name, "url": url})
    return forums

def parse_forum_topics(html: str):
    """
    Parse a forum listing page to extract topics.
    Returns list of dicts: {topic_id, title, url, author, replies, views, last_post_time?}
    """
    soup = BeautifulSoup(html, "lxml")
    topics = []
    for row in soup.select("ul.topiclist.topics li.row"):
        a = row.select_one("a.topictitle")
        if not a:
            continue
        title = _clean(a.text)
        href = a.get("href") or ""
        url = urljoin(BASE, href)
        tid = None
        # ...-t12345.html or viewtopic.php?t=12345
        m = re.search(r"[?&]t=(\d+)", url)
        if not m:
            m = re.search(r"-t(\d+)", url)
        if not m:
            continue
        tid = int(m.group(1))
        author_el = row.select_one(".username, .username-coloured")
        author = _clean(author_el.text) if author_el else None
        replies = None
        views = None
        posts_dd = row.select_one("dd.posts")
        views_dd = row.select_one("dd.views")
        if posts_dd:
            m = re.search(r"(\d[\d,\.]*)", posts_dd.text)
            replies = m.group(1).replace(",", "") if m else None
        if views_dd:
            m = re.search(r"(\d[\d,\.]*)", views_dd.text)
            views = m.group(1).replace(",", "") if m else None
        last_time_el = row.select_one("dd.lastpost .lastposttime, dd.lastpost time")
        last_time = _clean(last_time_el.text) if last_time_el else None
        topics.append({
            "topic_id": tid,
            "title": title,
            "url": url,
            "author": author,
            "replies": int(replies) if (isinstance(replies, str) and replies.isdigit()) else replies,
            "views": int(views) if (isinstance(views, str) and views.isdigit()) else views,
            "last_post_time": last_time,
        })
    return topics

def has_next_page(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    if soup.select_one("link[rel=next], a[rel=next]"):
        return True
    for a in soup.select(".pagination a"):
        if "next" in (a.get("rel") or []) or "Next" in a.text:
            return True
    return False
