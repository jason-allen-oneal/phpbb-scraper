import re
import time
from typing import Optional
from config.session import session
from lib.storage import store_data
from lib.parsers.topic import parse_posts

def fetch_page(url):
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code != 200:
            print(f"[!] Error {resp.status_code} on {url}")
            return None
        html = resp.text
        if "The requested topic does not exist." in html:
            print("[x] This topic does not exist or was deleted.")
            return None
        return html
    except Exception as e:
        print(f"[!] Network error: {e}")
        return None

def scrape_topic(topic_url: str, out_collection: str = "posts"):
    """Scrape one topic's print pages and store posts."""
    if "&view=print" not in topic_url and "view=print" not in topic_url:
        sep = "&" if ("?" in topic_url) else "?"
        topic_url = f"{topic_url}{sep}view=print"

    html = fetch_page(topic_url)
    if not html:
        return 0

    posts = parse_posts(html)
    tid = None
    m = re.search(r"[?&]t=(\d+)", topic_url) or re.search(r"-t(\d+)", topic_url)
    if m:
        tid = int(m.group(1))
    for p in posts:
        p["topic_id"] = tid
    store_data(out_collection, posts)
    print(f"[✔] Stored {len(posts)} posts from {topic_url}")
    return len(posts)

def scrape_all_pages(base_print_url: str, start=0, stop=None, step=10, pause=1.0, out_collection="thread_posts"):
    all_count = 0
    page_index = start
    print(f"[+] Starting thread scrape: start={start}, step={step}")

    while True:
        url = base_print_url if page_index == 0 else f"{base_print_url}&start={page_index}"
        html = fetch_page(url)
        if not html:
            break
        posts = parse_posts(html)
        for p in posts:
            p["is_thread_op"] = (page_index == 0 and p.get("is_thread_op", False))
        if not posts or (stop is not None and page_index >= stop):
            break
        store_data(out_collection, posts)
        all_count += len(posts)
        print(f"[+] Page start={page_index} → {len(posts)} posts")
        page_index += step
        time.sleep(pause)
    print(f"[✔] Saved {all_count} posts to collection={out_collection}")
