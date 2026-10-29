"""댓글 초안을 만들어 텔레그램 승인 버튼과 함께 보내고, 버튼/답장 응답을 처리한다."""
import time
from datetime import datetime, timezone

import httpx

from . import db
from .extract import Extracted, Extractor
from .rank import parse_deadline


def proposable(ex: Extracted) -> bool:
    return "comment" in ex.entry_methods and not ex.macro_banned and not ex.needs_login_or_captcha


def _buttons(event_id: int) -> list[tuple[str, str]]:
    return [("✅ 게시", f"post:{event_id}"), ("⏭ 건너뛰기", f"skip:{event_id}")]


def _draft_message(title: str, text: str) -> str:
    return (f"✍️ 댓글 초안 — {title}\n\n{text}\n\n"
            "수정하려면 이 메시지에 답장(reply)으로 새 댓글을 보내세요.")


def propose(conn, tg, extractor: Extractor, event_id: int, title: str, description: str,
            ex: Extracted) -> bool:
    """초안 생성 실패 시 False(알림만 간 상태 유지)."""
    try:
        text = extractor.draft_comment(title, description, ex)
    except Exception:  # noqa: BLE001
        return False
    msg_id = tg.send(_draft_message(title, text), buttons=_buttons(event_id))
    db.set_draft(conn, event_id, text, msg_id)
    row = db.get_event(conn, event_id)
    db.update_event(conn, row["source_url"], status="awaiting_approval")
    return True


def _entry_methods(row) -> list[str]:
    return [m for m in (row["entry_methods"] or "").split(",") if m]


def do_post(conn, yt_user, event_id: int, now: datetime | None = None) -> str:
    """승인된 응모 실행. 사용자에게 보낼 결과 문장을 반환."""
    now = now or datetime.now(timezone.utc)
    row = db.get_event(conn, event_id)
    if row is None:
        return "이벤트를 찾을 수 없습니다"
    if db.has_entry(conn, event_id, "comment") or row["status"] == "entered":
        return "이미 응모한 이벤트입니다"
    if row["status"] != "awaiting_approval":
        return f"처리할 수 없는 상태입니다 ({row['status']})"
    dl = parse_deadline(row["deadline"] or "")
    if dl and dl < now:
        db.update_event(conn, row["source_url"], status="expired")
        return "마감이 지나 게시하지 않았습니다"
    draft = db.get_draft(conn, event_id)
    if draft is None:
        return "댓글 초안이 없습니다"
    methods = _entry_methods(row)
    done = []
    try:
        if "subscribe" in methods and row["channel_id"]:
            done.append("구독" if yt_user.subscribe(row["channel_id"]) else "이미 구독 중")
        if "like" in methods and row["video_id"]:
            yt_user.like(row["video_id"])
            done.append("좋아요")
        comment_id = yt_user.comment(row["video_id"], draft["text"])
    except httpx.HTTPStatusError as e:
        detail = f"({e.response.status_code}): {e.response.text[:200]}"
        if done:
            return f"❌ 일부 실패 {detail}\n완료: {', '.join(done)}\n다시 시도하려면 [게시]를 다시 누르세요"
        return f"❌ 게시 실패 {detail}\n다시 시도하려면 [게시]를 다시 누르세요"
    db.add_entry(conn, event_id, "comment", comment_id)
    db.update_event(conn, row["source_url"], status="entered")
    done.append("댓글")
    return f"✅ 응모 완료: {', '.join(done)}\n{row['source_url']}"


def handle_update(conn, tg, yt_user, upd: dict, *, gap_state: dict, gap_seconds: float = 120,
                  sleep=time.sleep) -> None:
    cb = upd.get("callback_query")
    if cb:
        if str(cb["message"]["chat"]["id"]) != tg.chat_id:
            return  # 다른 채팅에서 온 입력은 무시
        action, _, raw_id = cb["data"].partition(":")
        if not raw_id.isdigit():
            tg.answer_callback(cb["id"])
            return
        event_id = int(raw_id)
        msg_id = cb["message"]["message_id"]
        if action == "post":
            if gap_state.get("posted") and gap_seconds:
                sleep(gap_seconds)  # 같은 실행에서 연속 게시 간격
            result = do_post(conn, yt_user, event_id)
            tg.answer_callback(cb["id"], result.splitlines()[0])
            tg.send(result)
            if result.startswith("✅"):
                gap_state["posted"] = True
            if not result.startswith("❌"):
                tg.clear_buttons(msg_id)
        elif action == "skip":
            row = db.get_event(conn, event_id)
            if row and row["status"] == "awaiting_approval":
                db.update_event(conn, row["source_url"], status="skipped")
            tg.answer_callback(cb["id"], "건너뜀")
            tg.clear_buttons(msg_id)
        else:
            tg.answer_callback(cb["id"])
        return

    msg = upd.get("message")
    if not msg or str(msg["chat"]["id"]) != tg.chat_id:
        return
    reply = msg.get("reply_to_message")
    text = (msg.get("text") or "").strip()
    if not reply or not text:
        return
    event_id = db.event_id_by_draft_message(conn, reply["message_id"])
    if event_id is None:
        return
    row = db.get_event(conn, event_id)
    if not row or row["status"] != "awaiting_approval":
        tg.send("이미 처리된 이벤트라 수정할 수 없습니다")
        return
    old = db.get_draft(conn, event_id)
    new_id = tg.send(_draft_message(row["title"], text), buttons=_buttons(event_id))
    db.set_draft(conn, event_id, text, new_id)
    if old and old["message_id"]:
        tg.clear_buttons(old["message_id"])


def poll(conn, tg, yt_user, **kw) -> int:
    offset_raw = db.get_meta(conn, "tg_offset")
    updates = tg.get_updates(int(offset_raw) if offset_raw else None)
    gap_state: dict = {}
    for upd in updates:
        handle_update(conn, tg, yt_user, upd, gap_state=gap_state, **kw)
        db.set_meta(conn, "tg_offset", str(upd["update_id"] + 1))
    return len(updates)
