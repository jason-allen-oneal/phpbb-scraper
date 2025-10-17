import json
import logging
import os
import sqlite3
from pathlib import Path
from typing import Iterable, Dict, Any, Optional

try:
    import pymysql  # optional, for MySQL
except Exception:  # pragma: no cover
    pymysql = None

log = logging.getLogger("storage")

# -------- Env & Paths --------
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

OUTPUT_MODE = os.getenv("OUTPUT_MODE", "file").strip().lower()  # "file" or "db"

DB_TYPE = os.getenv("DB_TYPE", "").strip().lower()              # "sqlite" or "mysql"
DB_PATH = os.getenv("DB_PATH", str(OUTPUT_DIR / "darkforum.db"))
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_NAME = os.getenv("DB_NAME", "darkforum")

# -------- Internal globals --------
_sqlite_conn: Optional[sqlite3.Connection] = None
_mysql_conn: Optional["pymysql.connections.Connection"] = None  # type: ignore

# Single generic table schema for DB backends
_CREATE_SQLITE = """
CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    collection TEXT NOT NULL,
    data TEXT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""
_CREATE_MYSQL = """
CREATE TABLE IF NOT EXISTS records (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    collection VARCHAR(64) NOT NULL,
    data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
"""

def _ensure_sqlite() -> sqlite3.Connection:
    global _sqlite_conn
    if _sqlite_conn is None:
        path = Path(DB_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        _sqlite_conn = sqlite3.connect(str(path))
        _sqlite_conn.execute("PRAGMA journal_mode=WAL;")
        _sqlite_conn.execute("PRAGMA synchronous=NORMAL;")
        _sqlite_conn.execute(_CREATE_SQLITE)
        _sqlite_conn.commit()
        log.info("[storage] SQLite initialized at %s", path)
    return _sqlite_conn

def _ensure_mysql():
    global _mysql_conn
    if pymysql is None:
        raise RuntimeError("pymysql not available; install it or use sqlite/file backends.")
    if _mysql_conn is None:
        _mysql_conn = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            charset="utf8mb4",
            autocommit=True,
        )
        with _mysql_conn.cursor() as cur:
            cur.execute(_CREATE_MYSQL)
        log.info("[storage] MySQL connected to %s:%d/%s", DB_HOST, DB_PORT, DB_NAME)
    return _mysql_conn

def init_storage() -> None:
    """Initialize the selected storage backend (no-op for file)."""
    if OUTPUT_MODE == "db":
        if DB_TYPE == "sqlite":
            _ensure_sqlite()
        elif DB_TYPE == "mysql":
            _ensure_mysql()
        else:
            log.warning("[storage] OUTPUT_MODE=db but DB_TYPE unset/unknown → using FILE fallback")

def close_storage() -> None:
    global _sqlite_conn, _mysql_conn
    if _sqlite_conn is not None:
        _sqlite_conn.close()
        _sqlite_conn = None
    if _mysql_conn is not None:
        _mysql_conn.close()
        _mysql_conn = None

def _store_file(collection: str, rows: Iterable[Dict[str, Any]], out_file: Optional[str] = None) -> None:
    path = Path(out_file) if out_file else (OUTPUT_DIR / f"{collection}.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    log.debug("[storage] Wrote %s rows to %s", len(rows), path)

def _store_sqlite(collection: str, rows: Iterable[Dict[str, Any]]) -> None:
    conn = _ensure_sqlite()
    payload = [(collection, json.dumps(r, ensure_ascii=False)) for r in rows]
    if not payload:
        return
    conn.executemany("INSERT INTO records (collection, data) VALUES (?, ?)", payload)
    conn.commit()

def _store_mysql(collection: str, rows: Iterable[Dict[str, Any]]) -> None:
    conn = _ensure_mysql()
    payload = [(collection, json.dumps(r, ensure_ascii=False)) for r in rows]
    if not payload:
        return
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO records (collection, data) VALUES (%s, CAST(%s AS JSON))", payload)

def store_data(collection: str, rows: Iterable[Dict[str, Any]], out_file: Optional[str] = None) -> None:
    rows = list(rows)
    if not rows:
        return

    if OUTPUT_MODE == "file":
        _store_file(collection, rows, out_file)
        return

    if OUTPUT_MODE == "db":
        if DB_TYPE == "sqlite":
            _store_sqlite(collection, rows)
            return
        if DB_TYPE == "mysql":
            _store_mysql(collection, rows)
            return
        # Unknown DB type → fall back to file
        log.warning("[storage] Unknown DB_TYPE '%s' → using FILE fallback", DB_TYPE)

    _store_file(collection, rows, out_file)
