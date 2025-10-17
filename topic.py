#!/usr/bin/env python3
import requests, json, time, asyncio
from bs4 import BeautifulSoup
from lib.storage import store_data
from config import HEADERS, BASE_URL
from lib.session_manager import SessionManager

# =========================
# CONFIGURATION
# =========================
BASE_URL = f"{BASE_URL}viewtopic.php"

# =========================
# PARSER
# =========================
def parse_print_view(html):
    """Parse a Tapatalk/PhpBB print view.
    Detects error pages and extracts posts with author ID, name, timestamp, and content.
    """
    soup = BeautifulSoup(html, "lxml")

    # Detect error/info page
    error_box = soup.select_one("div#message div.message-content")
    if error_box:
        msg = error_box.get_text(strip=True)
        return {"error": True, "message": msg, "posts": []}

    posts = []
    for post in soup.select("div.post"):
        # --- Author ---
        author_link = post.select_one("div.author a[href*='memberlist.php?mode=viewprofile']")
        if author_link:
            author = author_link.get_text(strip=True)
            href = author_link.get("href", "")
            # Extract numeric author id from the link (u=###)
            author_id = None
            if "u=" in href:
                try:
                    author_id = href.split("u=")[-1].split("&")[0]
                except Exception:
                    author_id = None
        else:
            # fallback: try <div.author strong>
            author_div = post.select_one("div.author strong")
            author = author_div.get_text(strip=True) if author_div else None
            author_id = None

        # --- Timestamp ---
        date_div = post.select_one("div.date strong")
        timestamp = date_div.get_text(strip=True) if date_div else None

        # --- Content ---
        content_div = post.select_one("div.content")
        content = ""
        if content_div:
            for br in content_div.find_all("br"):
                br.replace_with("\n")
            content = content_div.get_text("\n", strip=True)

        posts.append({
            "author": author,
            "author_id": author_id,
            "timestamp": timestamp,
            "content": content,
        })

    return {"error": False, "posts": posts}


# =========================
# SCRAPER FOR ONE TOPIC
# =========================
def scrape_all_pages_for_topic(session, forum_id, topic_id, step=10, pause=1.0):
    """Scrape all paginated print-view pages for a given topic."""
    all_posts = []
    offset = 0
    prev_signature = None

    while True:
        url = f"{BASE_URL}?f={forum_id}&t={topic_id}&view=print"
        if offset > 0:
            url += f"&start={offset}"

        print(f"[+] Fetching forum={forum_id}, topic={topic_id}, start={offset}")
        try:
            r = session.get(url, timeout=15)
            r.raise_for_status()
        except Exception as e:
            print(f"[!] Request error for f={forum_id}, t={topic_id}, start={offset}: {e}")
            break

        parsed = parse_print_view(r.text)
        if parsed["error"]:
            print(f"[x] Error page for f={forum_id}, t={topic_id}: {parsed['message']}")
            break

        posts = parsed["posts"]
        if not posts:
            print(f"[!] No posts found on page start={offset}, stopping.")
            break

        signature = "|".join(f"{p['author']}@{p['timestamp']}" for p in posts)
        if signature == prev_signature:
            print(f"[!] Duplicate page detected at start={offset}, stopping pagination.")
            break
        prev_signature = signature

        print(f"    -> {len(posts)} posts parsed")
        all_posts.extend(posts)

        offset += step
        time.sleep(pause)

    return all_posts


async def scrape_all_pages_for_topic_async(session: SessionManager, forum_id, topic_id, step=10, pause=1.0):
    """Async version of topic scraping using session manager"""
    all_posts = []
    offset = 0
    prev_signature = None

    while True:
        url = f"{BASE_URL}?f={forum_id}&t={topic_id}&view=print"
        if offset > 0:
            url += f"&start={offset}"

        print(f"[+] Fetching forum={forum_id}, topic={topic_id}, start={offset}")
        try:
            response = await session.make_request(url)
            if not response:
                print(f"[!] Request error for f={forum_id}, t={topic_id}, start={offset}")
                break
                
            html = response.get("content", "")
        except Exception as e:
            print(f"[!] Request error for f={forum_id}, t={topic_id}, start={offset}: {e}")
            break

        parsed = parse_print_view(html)
        if parsed["error"]:
            print(f"[x] Error page for f={forum_id}, t={topic_id}: {parsed['message']}")
            break

        posts = parsed["posts"]
        if not posts:
            print(f"[!] No posts found on page start={offset}, stopping.")
            break

        signature = "|".join(f"{p['author']}@{p['timestamp']}" for p in posts)
        if signature == prev_signature:
            print(f"[!] Duplicate page detected at start={offset}, stopping pagination.")
            break
        prev_signature = signature

        print(f"    -> {len(posts)} posts parsed")
        all_posts.extend(posts)

        offset += step
        await asyncio.sleep(pause)

    return all_posts


# =========================
# SCRAPER FOR MULTIPLE FORUMS + TOPICS
# =========================
def scrape_forums(start_f=1, end_f=100, start_t=1, end_t=10000, step=10, pause=1.0, consecutive_errors=20):
    """Iterate through all forums and topics sequentially."""
    session = requests.Session()
    session.headers.update(HEADERS)

    for f in range(start_f, end_f + 1):
        print(f"\n########## FORUM {f} ##########")
        error_streak = 0

        for t in range(start_t, end_t + 1):
            url = f"{BASE_URL}?f={f}&t={t}&view=print"
            print(f"\n=== Forum {f} | Topic {t} ===")

            try:
                r = session.get(url, timeout=15)
                r.raise_for_status()
                parsed = parse_print_view(r.text)
            except Exception as e:
                print(f"[!] Request error for f={f}, t={t}: {e}")
                error_streak += 1
                if error_streak >= consecutive_errors:
                    print("[!] Too many consecutive failures. Skipping to next forum.")
                    break
                continue

            if parsed["error"]:
                print(f"[x] Missing f={f}, t={t}: {parsed['message']}")
                error_streak += 1
                if error_streak >= consecutive_errors:
                    print("[!] Too many missing topics in a row — moving to next forum.")
                    break
                continue

            error_streak = 0
            print(f"[+] Valid topic {t} in forum {f}, scraping pages...")

            all_posts = scrape_all_pages_for_topic(session, f, t, step=step, pause=pause)

            if all_posts:
                collection_name = f"forum_{f}_topic_{t}"
                store_data(collection_name, all_posts)
                print(f"[✔] Stored {len(all_posts)} posts in collection {collection_name}")
            else:
                print(f"[!] Topic {t} in forum {f} had no posts extracted.")

            time.sleep(pause)

        print(f"########## Finished forum {f} ##########\n")
        time.sleep(pause * 2)


# =========================
# MAIN ENTRY POINT
# =========================
if __name__ == "__main__":
    scrape_forums(
        start_f=1,
        end_f=300,
        start_t=1,
        end_t=20000,
        step=10,
        pause=1.0,
        consecutive_errors=200
    )
