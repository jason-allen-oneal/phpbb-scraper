# config/session.py
import os
import logging
from typing import Optional, Iterable
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from dotenv import load_dotenv, set_key, dotenv_values

load_dotenv()

log = logging.getLogger("session")
log.addHandler(logging.NullHandler())

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/141.0.0.0 Safari/537.36"
)

# Which host we expect cookies for
DEFAULT_DOMAIN = os.getenv("DF_DOMAIN", "www.darkforum.com")


def _parse_cookie_string(cookie_str: str, default_domain: str) -> requests.cookies.RequestsCookieJar:
    jar = requests.cookies.RequestsCookieJar()
    if not cookie_str:
        return jar
    for p in [x.strip() for x in cookie_str.split(";") if x.strip()]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        # allow empty values but preserve key
        jar.set(k.strip(), v.strip(), domain=default_domain)
    return jar


def _serialize_cookie_jar(jar: requests.cookies.RequestsCookieJar, default_domain: str) -> str:
    # produce "k=v; k2=v2; ..." representation (no domains)
    parts = []
    for c in jar:
        # only include cookies for our domain (avoid extraneous)
        # cookie attributes in requests.Cookie are: name, value, domain...
        if default_domain and getattr(c, "domain", "") and default_domain not in c.domain:
            # still include it — sometimes cookie domain differs (tapatalk cdn), but we only need relevant cookies
            pass
        parts.append(f"{c.name}={c.value}")
    return "; ".join(parts)


def _load_env_cookies(default_domain: str) -> requests.cookies.RequestsCookieJar:
    cookie_str = os.getenv("DF_COOKIES", "").strip()
    return _parse_cookie_string(cookie_str, default_domain)


def _write_env_cookies(cookie_str: str) -> None:
    """
    Replace DF_COOKIES in the .env file (create or update).
    Uses python-dotenv.set_key which preserves file formatting.
    """
    env_path = os.getenv("DOTENV_PATH", ".env")
    try:
        # ensure file exists
        if not os.path.exists(env_path):
            # create minimal .env
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"DF_COOKIES={cookie_str}\n")
            log.info("[session] Created %s with DF_COOKIES", env_path)
            # also set in process env
            os.environ["DF_COOKIES"] = cookie_str
            return

        # update with set_key (keeps structure)
        set_key(env_path, "DF_COOKIES", cookie_str)
        os.environ["DF_COOKIES"] = cookie_str
        log.info("[session] Updated %s DF_COOKIES", env_path)
    except Exception as e:
        log.exception("[session] Failed to write cookies to %s: %s", env_path, e)


def _merge_cookies_to_session(s: requests.Session, jar: requests.cookies.RequestsCookieJar) -> None:
    # requests.Session.cookies.update accepts cookiejar or dict
    s.cookies.update(jar)


def _requests_session_with_retries() -> requests.Session:
    s = requests.Session()

    ua = os.getenv("USER_AGENT", DEFAULT_UA).strip() or DEFAULT_UA

    # stealth headers (close to a real browser)
    s.headers.update({
        "User-Agent": ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Referer": f"https://{DEFAULT_DOMAIN}/",
        "Connection": "keep-alive",
    })

    retry = Retry(
        total=int(os.getenv("HTTP_TOTAL_RETRY", "5")),
        backoff_factor=float(os.getenv("HTTP_BACKOFF", "0.6")),
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    s.mount("https://", adapter)
    s.mount("http://", adapter)

    return s


def _attempt_cloudscraper_refresh(url: str) -> Optional[requests.cookies.RequestsCookieJar]:
    """
    Try to use cloudscraper to solve JS challenge and return a cookie jar.
    Requires 'cloudscraper' to be installed. If not installed, returns None.
    """
    try:
        import cloudscraper
    except Exception as e:
        log.warning("[session] cloudscraper not available: %s", e)
        return None

    try:
        log.info("[session] Attempting cloudscraper solve for %s", url)
        # create a cloudscraper instance that behaves like Chrome on Linux
        scraper = cloudscraper.create_scraper(
            browser={'browser': 'chrome', 'platform': 'linux', 'mobile': False},
            # doubleDown will attempt to solve again if first attempt returns 403
            doubleDown=True,
            delay=5,
        )
        # perform a request to the target url (or root)
        r = scraper.get(url, timeout=int(os.getenv("HTTP_TIMEOUT", "30")))
        if r.status_code not in (200, 302):
            log.warning("[session] cloudscraper returned status %s", r.status_code)
        # cloudscraper has a requests-like .cookies
        jar = scraper.cookies  # RequestsCookieJar
        # Serialize into requests cookiejar form by copying
        new_jar = requests.cookies.RequestsCookieJar()
        for c in jar:
            new_jar.set(c.name, c.value, domain=c.domain or DEFAULT_DOMAIN, path=c.path)
        log.info("[session] cloudscraper obtained %d cookies", len(new_jar))
        return new_jar
    except Exception as e:
        log.exception("[session] cloudscraper attempt failed: %s", e)
        return None


def _cookies_differ(env_cookie_str: str, jar: requests.cookies.RequestsCookieJar) -> bool:
    # compare by name/value pairs for simplicity
    env_map = {}
    for p in [x.strip() for x in env_cookie_str.split(";") if x.strip()]:
        if "=" not in p:
            continue
        k, v = p.split("=", 1)
        env_map[k.strip()] = v.strip()
    for c in jar:
        if env_map.get(c.name) != c.value:
            return True
    # also check for env cookies missing from jar
    for k in env_map:
        if not any(c.name == k for c in jar):
            return True
    return False


def build_session(base_domain: str = DEFAULT_DOMAIN) -> requests.Session:
    """
    Build and return a requests.Session which is:
      - pre-populated with cookies from DF_COOKIES (if present)
      - uses robust headers + retries
      - will try cloudscraper to refresh cookies if a blocking response is encountered
      - will persist new cookies back into .env automatically (DF_COOKIES)
    """
    s = _requests_session_with_retries()

    cookie_jar = _load_env_cookies(base_domain)
    if cookie_jar:
        _merge_cookies_to_session(s, cookie_jar)
        log.debug("[session] Loaded %d cookies from DF_COOKIES", len(cookie_jar))
    else:
        log.debug("[session] No DF_COOKIES in env to load")

    # quick smoke test: homepage should be reachable with current cookies
    test_url = os.getenv("SESSION_TEST_URL", f"https://{base_domain}/")
    try:
        r = s.get(test_url, timeout=int(os.getenv("HTTP_TIMEOUT", "15")), allow_redirects=True)
        if r.status_code == 200 and r.headers.get("Server", "").lower().startswith("cloudflare"):
            log.debug("[session] Test request OK (200) to %s", test_url)
            # If cookies in response differ from env, update them
            current_env = os.getenv("DF_COOKIES", "")
            new_cookie_str = _serialize_cookie_jar(s.cookies, base_domain)
            if current_env and _cookies_differ(current_env, s.cookies):
                # persist
                log.info("[session] Detected cookie differences — updating .env")
                _write_env_cookies(new_cookie_str)
            return s
        else:
            log.warning("[session] Test request returned status=%s (will attempt cloudscraper fallback)", r.status_code)
    except Exception as e:
        log.warning("[session] Test request failed: %s (will attempt cloudscraper)", e)

    # If we get here, test failed or returned non-200; try cloudscraper
    refresh_url = os.getenv("SESSION_REFRESH_URL", test_url)
    new_jar = _attempt_cloudscraper_refresh(refresh_url)
    if new_jar:
        # copy cookies into our requests session
        _merge_cookies_to_session(s, new_jar)
        # persist serialized cookies into .env if changed
        new_cookie_str = _serialize_cookie_jar(s.cookies, base_domain)
        current_env = os.getenv("DF_COOKIES", "")
        if not current_env or _cookies_differ(current_env, s.cookies):
            log.info("[session] Saving refreshed cookies into .env")
            try:
                _write_env_cookies(new_cookie_str)
            except Exception:
                log.exception("[session] Failed saving refreshed cookies to .env")
        return s

    # final fallback: return session even if not refreshed — caller must handle 403s
    log.warning("[session] Could not refresh cookies (no cloudscraper or refresh failed). Requests may be blocked by Cloudflare.")
    return s


def refresh_session_cookies(s: requests.Session, failed_url: str, base_domain: str = DEFAULT_DOMAIN) -> bool:
    """
    Attempt to refresh session cookies using cloudscraper when a 403 is encountered.
    Returns True if cookies were successfully refreshed, False otherwise.
    """
    log.info("[session] Attempting to refresh cookies due to 403 on %s", failed_url)
    
    # Try cloudscraper refresh on the failed URL
    new_jar = _attempt_cloudscraper_refresh(failed_url)
    if new_jar:
        # Update session cookies
        _merge_cookies_to_session(s, new_jar)
        # Persist to .env
        new_cookie_str = _serialize_cookie_jar(s.cookies, base_domain)
        current_env = os.getenv("DF_COOKIES", "")
        if not current_env or _cookies_differ(current_env, s.cookies):
            log.info("[session] Saving refreshed cookies into .env after 403")
            try:
                _write_env_cookies(new_cookie_str)
            except Exception:
                log.exception("[session] Failed saving refreshed cookies to .env")
        return True
    
    log.warning("[session] Failed to refresh cookies for 403 error")
    return False


# Expose module-level session for convenience
session = build_session()
