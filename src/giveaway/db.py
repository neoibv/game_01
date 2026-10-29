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
CREATE TABLE IF NOT EXISTS drafts (
    event_id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    message_id INTEGER
);
CREATE TABLE IF NOT EXISTS entries (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL,
    method TEXT NOT NULL,
    payload TEXT,
    entered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    result TEXT NOT NULL DEFAULT 'pending',
    UNIQUE(event_id, method)
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
    "video_id": "TEXT",
    "channel_id": "TEXT",
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


def get_event(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM events WHERE id = ?", (event_id,)).fetchone()


def event_id_by_url(conn: sqlite3.Connection, source_url: str) -> int:
    return conn.execute("SELECT id FROM events WHERE source_url = ?", (source_url,)).fetchone()["id"]


def set_draft(conn: sqlite3.Connection, event_id: int, text: str, message_id: int | None) -> None:
    conn.execute(
        "INSERT INTO drafts(event_id, text, message_id) VALUES(?, ?, ?) "
        "ON CONFLICT(event_id) DO UPDATE SET text = excluded.text, message_id = excluded.message_id",
        (event_id, text, message_id),
    )
    conn.commit()


def get_draft(conn: sqlite3.Connection, event_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM drafts WHERE event_id = ?", (event_id,)).fetchone()


def event_id_by_draft_message(conn: sqlite3.Connection, message_id: int) -> int | None:
    row = conn.execute("SELECT event_id FROM drafts WHERE message_id = ?", (message_id,)).fetchone()
    return row["event_id"] if row else None


def add_entry(conn: sqlite3.Connection, event_id: int, method: str, payload: str) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO entries(event_id, method, payload) VALUES(?, ?, ?)",
        (event_id, method, payload),
    )
    conn.commit()
    return cur.rowcount == 1


def has_entry(conn: sqlite3.Connection, event_id: int, method: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM entries WHERE event_id = ? AND method = ?", (event_id, method)
    ).fetchone() is not None


def normalize_title(title: str) -> str:
    return "".join(ch for ch in title.lower() if ch.isalnum())


def title_exists(conn: sqlite3.Connection, title: str) -> bool:
    """다른 사이트가 같은 이벤트를 중복으로 올린 경우 거르기 위함."""
    key = normalize_title(title)
    if not key:
        return False
    return any(normalize_title(r["title"]) == key for r in conn.execute("SELECT title FROM events"))


def url_exists(conn: sqlite3.Connection, source_url: str) -> bool:
    return conn.execute("SELECT 1 FROM events WHERE source_url = ?", (source_url,)).fetchone() is not None
