import re
import time
from typing import Optional, Dict, Any, List

from config.session import session
from lib.storage import store_data
from lib.parsers.profile import parse_profile

PROFILE_BASE = "https://www.darkforum.com/memberlist.php?mode=viewprofile&u={uid}"

# Detect "user not found" or Cloudflare page
def is_invalid_profile(html: str) -> bool:
    # Lowercase match for safety
    text = html.lower()
    # Known patterns for missing or blocked profiles
    if "the requested user does not exist" in text:
        return True
    if "<h2>information</h2>" in text and "requested user" in text:
        return True
    if "cf-challenge" in text or "just a moment" in text:
        return True
    return False


def fetch_profile_html(uid: int) -> Optional[str]:
    """Fetch raw profile HTML for a given user ID."""
    url = PROFILE_BASE.format(uid=uid)
    try:
        resp = session.get(url, timeout=30)
        if resp.status_code in (403, 404):
            print(f"[-] UID {uid} → HTTP {resp.status_code}")
            return None
        if resp.status_code != 200:
            print(f"[!] UID {uid} → Unexpected HTTP {resp.status_code}")
            return None
        if is_invalid_profile(resp.text):
            print(f"[-] UID {uid} → Invalid profile (user does not exist)")
            return None
        return resp.text
    except Exception as e:
        print(f"[!] UID {uid} → Network error: {e}")
        return None


def scrape_members(start_uid: int = 1, stop_uid: Optional[int] = None, delay: float = 1.0):
    """
    Sequentially enumerates member profiles via ?u={id}.
    Example: memberlist.php?mode=viewprofile&u=220
    """
    all_profiles: List[Dict[str, Any]] = []
    current = start_uid
    consecutive_failures = 0
    max_failures = 20  # stop if we hit too many dead UIDs in a row

    print(f"[+] Starting direct member scrape from UID={start_uid}")

    while True:
        if stop_uid and current > stop_uid:
            break

        html = fetch_profile_html(current)
        if html:
            data = parse_profile(html)
            data["user_id"] = current
            data["profile_url"] = PROFILE_BASE.format(uid=current)
            all_profiles.append(data)
            store_data("profiles", [data])
            print(f"[+] UID {current} → Parsed {data.get('username') or 'unknown'}")
            consecutive_failures = 0  # reset fail streak
        else:
            consecutive_failures += 1
            print(f"[-] UID {current} → Skipped (fail {consecutive_failures}/{max_failures})")
            if consecutive_failures >= max_failures:
                print(f"[!] {consecutive_failures} consecutive failures → stopping.")
                break

        current += 1
        time.sleep(delay)

    print(f"[✔] Total valid profiles scraped: {len(all_profiles)}")
