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


# 기존 DB에 없는 컬럼은 connect 시 추가한다.
EXTRA_COLUMNS = {
    "prize": "TEXT",
    "prize_value_est": "INTEGER DEFAULT 0",
    "entry_methods": "TEXT",
    "requirements": "TEXT",
    "macro_banned": "INTEGER DEFAULT 0",
    "auto_enterable": "INTEGER DEFAULT 0",
    "deadline": "TEXT",
    "announce_at": "TEXT",
    "announce_where": "TEXT",
    "score": "INTEGER DEFAULT 0",
    "reminded": "INTEGER DEFAULT 0",
}


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    have = {r["name"] for r in conn.execute("PRAGMA table_info(events)")}
    for col, decl in EXTRA_COLUMNS.items():
        if col not in have:
            conn.execute(f"ALTER TABLE events ADD COLUMN {col} {decl}")
    conn.commit()
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


UPDATABLE = set(EXTRA_COLUMNS) | {"status"}


def update_event(conn: sqlite3.Connection, source_url: str, **fields) -> None:
    bad = set(fields) - UPDATABLE
    if bad:
        raise ValueError(f"updatable 아님: {bad}")
    if not fields:
        return
    sets = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE events SET {sets} WHERE source_url = ?", (*fields.values(), source_url))
    conn.commit()


def open_events(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    """마감 처리 대상: 알림은 갔고 아직 끝나지 않은 이벤트."""
    return conn.execute(
        "SELECT * FROM events WHERE status IN ('notified', 'entered', 'awaiting_approval')"
    ).fetchall()
