"""Opt-in disk cache for LLM, search, and fetch calls.

Off by default. The eval harness calls enable() so every call is paid for once and
reruns replay from disk.
"""

import hashlib
import json
import sqlite3
from pathlib import Path

_conn: sqlite3.Connection | None = None


def enable(path: Path) -> None:
    global _conn
    path.parent.mkdir(parents=True, exist_ok=True)
    _conn = sqlite3.connect(path)
    _conn.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT)")


def make_key(*parts: object) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def get(key: str) -> object | None:
    if _conn is None:
        return None
    row = _conn.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
    return json.loads(row[0]) if row else None


def put(key: str, value: object) -> None:
    if _conn is None:
        return
    _conn.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)", (key, json.dumps(value)))
    _conn.commit()
