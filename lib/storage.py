from pathlib import Path
import json
from typing import Iterable, Dict, Any, Optional
from config import OUTPUT_DIR, log, OUTPUT_MODE, DB_TYPE
from lib.db import insert_members, insert_forum_topics, insert_thread_posts, insert_generic_data


# -------- Env & Paths --------

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def init_storage():
    """Initialize storage system"""
    log.info("Storage system initialized")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def close_storage():
    """Close storage system and cleanup"""
    log.info("Storage system closed")
'''
def _store_mysql(collection: str, rows: Iterable[Dict[str, Any]]) -> None:
    payload = [(collection, json.dumps(r, ensure_ascii=False)) for r in rows]
    if not payload:
        return
    print(payload)
'''
def _store_file(collection: str, rows: Iterable[Dict[str, Any]], out_file: Optional[str] = None) -> None:
    path = Path(out_file) if out_file else (OUTPUT_DIR / f"{collection}.jsonl")
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    with path.open("a", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    log.debug("[storage] Wrote %s rows to %s", len(rows), path)

def store_data(collection: str, rows: Iterable[Dict[str, Any]], out_file: Optional[str] = None) -> None:
    rows = list(rows)
    if not rows:
        return

    if OUTPUT_MODE == "file":
        _store_file(collection, rows, out_file)
        return

    if OUTPUT_MODE == "db":
        if DB_TYPE == "mysql":
            _store_mysql(collection, rows)
            return
        # Unknown DB type → fall back to file
        log.warning("[storage] Unknown DB_TYPE '%s' → using FILE fallback", DB_TYPE)
    
    _store_file(collection, rows, out_file)


def _store_mysql(collection: str, rows: Iterable[Dict[str, Any]]) -> None:
    """Store data in MySQL database using appropriate table"""
    rows = list(rows)
    if not rows:
        return
    
    success = False
    
    # Route to appropriate database function based on collection name
    if collection == "members":
        success = insert_members(rows)
    elif collection == "forum_topics":
        success = insert_forum_topics(rows)
    elif collection == "thread_posts":
        success = insert_thread_posts(rows)
    else:
        # For other collections, use generic data table
        success = insert_generic_data(collection, rows)
    
    if not success:
        log.warning("[storage] MySQL storage failed, falling back to file storage")
        _store_file(collection, rows)
    else:
        log.debug("[storage] Stored %s rows in MySQL collection '%s'", len(rows), collection)