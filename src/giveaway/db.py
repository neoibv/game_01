import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    host TEXT,
    matched TEXT,
    raw_text TEXT,
    first_seen_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'new'
);
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def add_event(conn: sqlite3.Connection, *, source: str, source_url: str, title: str,
              host: str, matched: list[str], raw_text: str) -> bool:
    """새 이벤트면 True, 이미 있으면 False."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO events(source, source_url, title, host, matched, raw_text) "
        "VALUES(?, ?, ?, ?, ?, ?)",
        (source, source_url, title, host, ",".join(matched), raw_text),
    )
    conn.commit()
    return cur.rowcount == 1


def mark_notified(conn: sqlite3.Connection, source_url: str) -> None:
    conn.execute("UPDATE events SET status = 'notified' WHERE source_url = ?", (source_url,))
    conn.commit()
