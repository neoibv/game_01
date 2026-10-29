"""응모한 이벤트의 당첨 발표를 찾는다.

찾는 곳: ① 내 댓글에 달린 채널 주인의 답글 ② 채널의 이후 영상 설명란/고정 댓글에 내 @핸들 언급.
유튜브 커뮤니티 탭은 공식 API가 없어 확인하지 못한다.
"""
from datetime import datetime, timedelta, timezone

from . import db
from .detect import detect

ANNOUNCE_WORDS = {"include": ["당첨", "발표"], "exclude": []}
WATCH_DAYS = 30


def _iso(sqlite_ts: str) -> str:
    return sqlite_ts.replace(" ", "T") + "Z"


def _entered_rows(conn):
    return conn.execute(
        "SELECT e.*, n.payload AS thread_id, n.entered_at AS entered_at "
        "FROM events e JOIN entries n ON n.event_id = e.id AND n.method = 'comment' "
        "WHERE e.status = 'entered'").fetchall()


def check(conn, yt, user, notify, now: datetime | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    out = {"watching": 0, "replies": 0, "mentions": 0, "closed": 0}
    rows = _entered_rows(conn)
    if not rows:
        return out

    handle = db.get_meta(conn, "my_handle")
    if handle is None:
        _, handle = user.my_channel()
        db.set_meta(conn, "my_handle", handle or "-")
    needle = handle.lower() if handle and handle != "-" else ""

    for row in rows:
        started = datetime.fromisoformat(_iso(row["entered_at"]).replace("Z", "+00:00"))
        if now - started > timedelta(days=WATCH_DAYS):
            db.update_event(conn, row["source_url"], status="closed")
            out["closed"] += 1
            continue
        out["watching"] += 1

        # ① 채널 주인의 답글
        for rep in user.replies(row["thread_id"]):
            key = f"winner_seen:{rep['id']}"
            if rep["author_channel_id"] == row["channel_id"] and db.get_meta(conn, key) is None:
                db.set_meta(conn, key, "1")
                notify(f"🎉 채널 주인이 내 댓글에 답글을 남겼어요!\n{row['title']}\n"
                       f"\"{rep['text'][:200]}\"\n{row['source_url']}\n\n"
                       "당첨이면 안내된 기한 안에 연락처 제출(구글폼 등)을 꼭 확인하세요.")
                out["replies"] += 1

        # ② 이후 영상에서 내 핸들 언급
        cached = db.get_meta(conn, f"channel:{row['host']}")
        if not needle or not cached:
            continue
        _, uploads = cached.split("|")
        for video in yt.videos(yt.recent_video_ids(uploads, _iso(row["entered_at"])), row["host"]):
            video.pinned_comment = yt.pinned_comment(video.video_id, row["channel_id"])
            if needle not in video.text.lower() or not detect(video.text, ANNOUNCE_WORDS).is_candidate:
                continue
            key = f"winner_seen:{row['id']}:{video.video_id}"
            if db.get_meta(conn, key) is None:
                db.set_meta(conn, key, "1")
                notify(f"🏆 당첨자 발표에 내 핸들({handle})이 언급됐어요!\n"
                       f"이벤트: {row['title']}\n발표: {video.title}\n{video.url}\n\n"
                       "구글폼 등으로 연락처를 제출해야 하는 경우가 많으니 기한을 바로 확인하세요.")
                out["mentions"] += 1
    return out
