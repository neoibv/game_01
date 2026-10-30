"""댓글 초안을 만들어 텔레그램 승인 버튼과 함께 보내고, 버튼/답장 응답을 처리한다."""
import time
from datetime import datetime, timezone

import httpx

from . import db
from .extract import Extracted, Extractor
from .rank import parse_deadline


def proposable(ex: Extracted) -> bool:
    """댓글이 응모 조건에 들어 있으면 초안을 만든다(폼 제출 등 다른 조건이 함께 있어도)."""
    return "comment" in ex.entry_methods


def _buttons(event_id: int) -> list[tuple[str, str]]:
    return [("✅ 게시", f"post:{event_id}"), ("⏭ 건너뛰기", f"skip:{event_id}")]


def _notes(ex: Extracted) -> str:
    """초안과 함께 보여줄 주의사항: 직접 해야 할 남은 단계, 양식 추정 경고."""
    lines = []
    if ex.format_confidence == "low":
        lines.append("⚠️ 응모양식은 시청자 댓글 패턴으로 추정한 것입니다. 영상 마지막의 안내를 확인하고 양식이 다르면 "
                     "[게시] 대신 답장으로 고쳐 쓰세요(양식이 틀리면 당첨이 취소될 수 있음).")
    manual = [m for m in ex.entry_methods if m in ("google_form", "form", "sns_share", "other")]
    if manual:
        lines.append("📝 댓글 외에 직접 해야 할 것: " + (" → ".join(ex.entry_steps) if ex.entry_steps else ", ".join(manual))
                     + (f"\n   {ex.form_url}" if ex.form_url else ""))
    if ex.membership != "none":
        lines.append("💳 채널 멤버십(유료) " + ("가입이 필수 조건입니다" if ex.membership == "required" else "가입이 우대/권장 조건입니다")
                     + " — 자동 처리하지 않으니 원하면 직접 가입하세요.")
    if "알림" in " ".join(ex.entry_steps):
        lines.append("🔔 알림 설정(종 아이콘)은 API로 못 해서 직접 해야 합니다.")
    if ex.macro_banned:
        lines.append("🚫 자동 응모 금지 문구가 있어 [게시] 버튼을 달지 않았습니다. 위 내용을 복사해 직접 작성하세요.")
    if {"subscribe", "like"} & set(ex.entry_methods) and not ex.macro_banned:
        lines.append("ℹ️ [게시]를 누르면 구독·좋아요도 함께 처리됩니다.")
    return "\n".join(lines)


def _draft_message(title: str, text: str, notes: str = "", can_post: bool = True) -> str:
    tail = "수정하려면 이 메시지에 답장(reply)으로 새 댓글을 보내세요." if can_post else ""
    return "\n\n".join(p for p in (f"✍️ 댓글 초안 — {title}", text, notes, tail) if p)


def propose(conn, tg, extractor: Extractor, event_id: int, title: str, description: str,
            ex: Extracted) -> bool:
    """초안 생성 실패 시 False(알림만 간 상태 유지)."""
    try:
        text = extractor.draft_comment(title, description, ex)
    except Exception:  # noqa: BLE001
        return False
    notes = _notes(ex)
    if ex.macro_banned:  # 자동 게시하지 않고 초안만 보낸다
        tg.send(_draft_message(title, text, notes, can_post=False))
        return True
    msg_id = tg.send(_draft_message(title, text, notes), buttons=_buttons(event_id))
    db.set_draft(conn, event_id, text, msg_id)
    db.set_meta(conn, f"draft_notes:{event_id}", notes)
    row = db.get_event(conn, event_id)
    db.update_event(conn, row["source_url"], status="awaiting_approval")
    return True


SAME_AS_LAST = {"같음", "동일", "같아", "같아요", "same", "그대로"}


def request_format(conn, tg, event_id: int, title: str, url: str, last_format: str = "") -> int:
    """응모 양식을 영상에서만 안내하는 채널: 사용자가 영상 말미를 보고 답장으로 알려주면 초안을 만든다."""
    lines = [f"🎬 {title}",
             "이 채널은 댓글 응모 양식을 영상 말미에서 말로 안내합니다. 영상 끝부분을 확인하고 "
             "이 메시지에 **답장**으로 양식을 알려주세요.",
             "예) 보겸, 아이폰듀오 두 키워드 포함 2줄 이상"]
    if last_format:
        lines.append(f"지난번 양식: {last_format}\n(같으면 '같음'이라고 답장)")
    lines.append(url)
    msg_id = tg.send("\n\n".join(lines), buttons=[("⏭ 건너뛰기", f"skip:{event_id}")])
    db.set_meta(conn, f"format_req:{msg_id}", str(event_id))
    row = db.get_event(conn, event_id)
    db.update_event(conn, row["source_url"], status="awaiting_format")
    return msg_id


def _ex_from_row(row, *, keywords: list[str], min_lines: int, entry_format: str) -> Extracted:
    import json
    req = json.loads(row["requirements"] or "{}")
    return Extracted(
        is_giveaway=True, entry_methods=_entry_methods(row), entry_steps=req.get("steps", []),
        form_url=req.get("form_url", ""), comment_prompt=req.get("comment_prompt", ""),
        required_keywords=keywords, comment_min_lines=min_lines, entry_format=entry_format,
        format_confidence="high", macro_banned=bool(row["macro_banned"]),
        membership=req.get("membership", "none"), deadline=row["deadline"] or "")


def _handle_format_reply(conn, tg, extractor, event_id: int, text: str) -> None:
    row = db.get_event(conn, event_id)
    if not row or row["status"] != "awaiting_format":
        tg.send("이미 처리된 이벤트라 양식을 받을 수 없습니다")
        return
    if extractor is None:
        tg.send("AI 키(ANTHROPIC_API_KEY)가 poll 워크플로에 없어 양식을 해석하지 못했습니다.")
        return
    last = db.get_meta(conn, f"last_format:{row['host']}") or ""
    if text.strip().lower() in SAME_AS_LAST and last:
        text = last
    try:
        parsed = extractor.parse_format(text)
    except Exception as e:  # noqa: BLE001
        tg.send(f"양식을 해석하지 못했습니다({str(e)[:120]}). 다시 답장해 주세요.")
        return
    ex = _ex_from_row(row, keywords=parsed.get("required_keywords", []),
                      min_lines=int(parsed.get("comment_min_lines") or 0),
                      entry_format=parsed.get("entry_format", text))
    if not propose(conn, tg, extractor, event_id, row["title"], row["raw_text"] or "", ex):
        tg.send("댓글 초안을 만들지 못했습니다. 잠시 후 양식을 다시 답장해 주세요.")
        db.update_event(conn, row["source_url"], status="awaiting_format")
        return
    db.set_meta(conn, f"last_format:{row['host']}", text)


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
                  sleep=time.sleep, extractor=None) -> None:
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
            if row and row["status"] in ("awaiting_approval", "awaiting_format"):
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
    format_event = db.get_meta(conn, f"format_req:{reply['message_id']}")
    if format_event:
        _handle_format_reply(conn, tg, extractor, int(format_event), text)
        return
    event_id = db.event_id_by_draft_message(conn, reply["message_id"])
    if event_id is None:
        return
    row = db.get_event(conn, event_id)
    if not row or row["status"] != "awaiting_approval":
        tg.send("이미 처리된 이벤트라 수정할 수 없습니다")
        return
    old = db.get_draft(conn, event_id)
    notes = db.get_meta(conn, f"draft_notes:{event_id}") or ""
    new_id = tg.send(_draft_message(row["title"], text, notes), buttons=_buttons(event_id))
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
