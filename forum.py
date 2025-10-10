import time
from typing import List, Dict, Any, Optional

from config.session import session, refresh_session_cookies
from lib.storage import store_data
from lib.parsers.forum import parse_forum_index, parse_forum_topics, has_next_page

BASE = "https://www.darkforum.com/"

def fetch(url: str, allow_retry: bool = True) -> Optional[str]:
    try:
        r = session.get(url, timeout=30)
        
        # If we get a 403, try to refresh cookies once
        if r.status_code == 403 and allow_retry:
            print(f"[!] HTTP 403 on {url}, attempting to refresh cookies...")
            if refresh_session_cookies(session, url):
                print(f"[+] Cookies refreshed, retrying {url}")
                # Retry the request with refreshed cookies, but don't allow further retries
                return fetch(url, allow_retry=False)
            else:
                print(f"[-] Failed to refresh cookies for {url}")
                return None
        
        if r.status_code != 200:
            print(f"[!] HTTP {r.status_code} → {url}")
            return None
        return r.text
    except Exception as e:
        print(f"[!] Network error: {e} on {url}")
        return None

def get_forums() -> List[Dict[str, Any]]:
    html = fetch(BASE)
    if not html:
        return []
    forums = parse_forum_index(html)
    store_data("forums", forums)
    print(f"[+] Found {len(forums)} forums on index")
    return forums

def scrape_forum_topics(fid: int, delay: float = 1.0, limit_pages: Optional[int] = None):
    """Iterate a forum and collect its topics."""
    start = 0
    pages = 0
    topics_total = 0
    while True:
        url = f"{BASE}viewforum.php?f={fid}&start={start}"
        html = fetch(url)
        if not html:
            break
        topics = parse_forum_topics(html)
        if not topics:
            break
        for t in topics:
            t["forum_id"] = fid
        store_data("topics_index", topics)
        topics_total += len(topics)
        pages += 1
        print(f"[+] Forum f={fid}, start={start} → {len(topics)} topics")
        if limit_pages and pages >= limit_pages:
            break
        if not has_next_page(html):
            break
        start += 50
        time.sleep(delay)
    print(f"[✔] Forum f={fid} collected topics={topics_total}")

def scrape_all_forums(delay: float = 1.0, limit_pages: Optional[int] = None):
    forums = get_forums()
    for f in forums:
        scrape_forum_topics(f["forum_id"], delay=delay, limit_pages=limit_pages)
