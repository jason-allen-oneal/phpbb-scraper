import re
from bs4 import BeautifulSoup

def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def parse_posts(html: str):
    soup = BeautifulSoup(html, "lxml")
    posts = []
    post_divs = soup.select("div.post")
    for idx, div in enumerate(post_divs):
        date = div.select_one(".date strong, .author time")
        author = div.select_one(".author strong, .username, .username-coloured")
        content = div.select_one(".content, .postbody")
        body = content.get_text(separator="\n").strip() if content else ""
        posts.append({
            "is_thread_op": (idx == 0),
            "author": author.text.strip() if author else None,
            "date": date.text.strip() if date else None,
            "content": clean_text(body) if body else None,
        })
    return posts
