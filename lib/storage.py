"""Simple storage abstraction for scraped data."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from config import DB_TYPE, OUTPUT_DIR, OUTPUT_MODE, log
from lib.db import insert_forum_topics, insert_generic_data, insert_members, insert_thread_posts


class StorageManager:
    """Coordinate writing scraped data either to disk or to the configured database."""

    def __init__(self) -> None:
        self.output_dir = OUTPUT_DIR
        self.mode = OUTPUT_MODE
        self.db_type = DB_TYPE
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def init(self) -> None:
        log.info("Storage system initialized (mode=%s)", self.mode)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        log.info("Storage system closed")

    def store(self, collection: str, rows: Iterable[Dict[str, Any]], out_file: Optional[str] = None) -> None:
        payload = [dict(row) for row in rows]
        if not payload:
            return

        if self.mode == "db" and self.db_type == "mysql":
            if self._store_mysql(collection, payload):
                return
            log.warning("[storage] Falling back to file storage for collection '%s'", collection)

        self._store_file(collection, payload, out_file)

    def _store_file(self, collection: str, rows: list[Dict[str, Any]], out_file: Optional[str]) -> None:
        path = Path(out_file) if out_file else self.output_dir / f"{collection}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        log.debug("[storage] Wrote %s rows to %s", len(rows), path)

    def _store_mysql(self, collection: str, rows: list[Dict[str, Any]]) -> bool:
        handler = {
            "members": insert_members,
            "forum_topics": insert_forum_topics,
            "thread_posts": insert_thread_posts,
        }.get(collection, lambda payload: insert_generic_data(collection, payload))

        try:
            success = handler(rows)
        except Exception as exc:  # pragma: no cover - database errors are runtime issues
            log.warning("[storage] Database error for '%s': %s", collection, exc)
            return False

        if not success:
            log.warning("[storage] Database handler for '%s' returned failure", collection)
        return bool(success)


_manager = StorageManager()


def init_storage() -> None:
    _manager.init()


def close_storage() -> None:
    _manager.close()


def store_data(collection: str, rows: Iterable[Dict[str, Any]], out_file: Optional[str] = None) -> None:
    _manager.store(collection, rows, out_file)
