from dotenv import load_dotenv
import os
import logging
from pathlib import Path

load_dotenv()

log = logging.getLogger("storage")

BASE_URL = os.getenv("BASE_URL")

OUTPUT_MODE = os.getenv("OUTPUT_MODE", "file").strip().lower()
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))

DB_TYPE = os.getenv("DB_TYPE", "mysql")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "")

HEADERS = {
    "User-Agent": os.getenv("USER_AGENT"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE_URL,
    "Cookie": os.getenv("DF_COOKIES"),
}


