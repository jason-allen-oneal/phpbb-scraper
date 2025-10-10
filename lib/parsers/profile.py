import re
from bs4 import BeautifulSoup


def parse_profile(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    def clean(text):
        return re.sub(r"\s+", " ", text.strip()) if text else None

    data = {}

    username_el = soup.select_one(".edit-username-span") or soup.select_one(".username")
    data["username"] = clean(username_el.text) if username_el else None

    avatar_el = soup.select_one(".profile-avatar .avatar-bg") or soup.select_one(".avatar-bg")
    if avatar_el and avatar_el.get("style"):
        m = re.search(r"url\((.*?)\)", avatar_el["style"])
        data["avatar_url"] = m.group(1) if m else None

    rank_el = soup.select_one(".profile-rank-name")
    data["rank"] = clean(rank_el.text) if rank_el else None

    posts = soup.select(".posts_container .posts_block a")
    if len(posts) >= 3:
        data["posts"] = clean(posts[0].text)
        data["likes_received"] = clean(posts[1].text)
        data["likes_given"] = clean(posts[2].text)

    for row in soup.select(".group .cl-af"):
        left_el = row.select_one(".left")
        right_el = row.select_one(".right")
        if left_el and right_el:
            key = clean(left_el.text).lower().replace(" ", "_")
            value = clean(right_el.text)
            data[key] = value

    groups = [opt.text.strip() for opt in soup.select("select[name=g] option")]
    if groups:
        data["groups"] = groups

    sig_el = soup.select_one(".signature.standalone")
    data["signature"] = clean(sig_el.text) if sig_el else None

    link_el = soup.find("link", rel="canonical")
    data["profile_url"] = link_el["href"] if link_el else None

    # try to derive user_id
    if data.get("profile_url"):
        m = re.search(r"[?&]u=(\d+)", data["profile_url"])
        if m:
            data["user_id"] = int(m.group(1))

    return data
