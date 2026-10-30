"""댓글 초안을 만들어 텔레그램 승인 버튼과 함께 보내고, 버튼/답장 응답을 처리한다."""
import json
import re
import time
from datetime import datetime, timezone

import httpx

from . import db, digest
from .extract import Extracted, Extractor, fit_comment
from .rank import parse_deadline


def proposable(ex: Extracted) -> bool:
    """댓글이 응모 조건에 들어 있으면 초안을 만든다(폼 제출 등 다른 조건이 함께 있어도)."""
    return "comment" in ex.entry_methods


def _buttons(event_id: int) -> list[tuple[str, str]]:
    return [("✅ 게시", f"post:{event_id}"), ("⏭ 건너뛰기", f"skip:{event_id}"),
            ("🚫 관심없음", f"dislike:{event_id}")]


def action_buttons(entries: list[tuple[int, str]]) -> list[list[tuple[str, str]]]:
    """알림 묶음 아래에 붙이는 이벤트별 버튼 줄: 직접 응모했다고 기록 / 관심없음. entries: [(event_id, 짧은 이름)]"""
    return [[(f"✅ {i}) {name[:14]} 응모함", f"entered:{eid}"), (f"🚫 {i}) 관심없음", f"dislike:{eid}")]
            for i, (eid, name) in enumerate(entries, 1)]


def do_entered(conn, event_id: int) -> str:
    row = db.get_event(conn, event_id)
    if row is None:
        return "이벤트를 찾을 수 없습니다"
    fresh = db.mark_entered(conn, event_id)
    when = row["announce_at"] or "미정"
    return (f"📝 응모 기록: {row['title'][:60]}\n결과 발표: {when}" if fresh
            else f"이미 응모로 기록된 이벤트입니다 (결과 발표: {when})")


def do_dislike(conn, event_id: int) -> str:
    """이 이벤트를 닫고, 제품 분류 단어를 차단 목록에 올려 관련 이벤트가 다시 알림에 나오지 않게 한다."""
    row = db.get_event(conn, event_id)
    if row is None:
        return "이벤트를 찾을 수 없습니다"
    if row["status"] != "entered":
        db.update_event(conn, row["source_url"], status="skipped")
    specific = f"{row['product'] or ''} {row['prize'] or ''}"
    words = digest.topic_words(specific) or digest.topic_words(row["title"])
    if not words and len((row["product"] or "").strip()) >= digest.TOPIC_MIN_LEN:
        words = [row["product"].strip().lower()]
    if not words:
        return "🚫 이 이벤트만 제외했어요 (관련 단어를 찾지 못해 다른 이벤트는 막지 않았습니다)"
    db.set_blocked_topics(conn, db.blocked_topics(conn) + words)
    return (f"🚫 '{', '.join(words)}' 관련 이벤트는 앞으로 알리지 않을게요.\n"
            f"되돌리려면 '차단해제 {words[0]}' 라고 보내세요. (현재 목록: '차단목록')")


def _handle_block_command(conn, tg, text: str) -> bool:
    if text.startswith("차단목록"):
        words = db.blocked_topics(conn)
        tg.send("🚫 관심없음으로 막은 단어: " + (", ".join(words) if words else "없음"))
        return True
    if text.startswith("차단해제"):
        word = text[len("차단해제"):].strip().lower()
        words = db.blocked_topics(conn)
        if word and word in [w.lower() for w in words]:
            db.set_blocked_topics(conn, [w for w in words if w.lower() != word])
            tg.send(f"'{word}' 차단을 풀었어요.")
        else:
            tg.send("풀 단어를 정확히 적어 주세요. 예) 차단해제 헤드셋\n현재 목록: " + (", ".join(words) or "없음"))
        return True
    return False


def _drop_event_buttons(tg, cb: dict, event_id: int) -> None:
    """눌린 이벤트의 버튼 줄만 지우고, 같은 메시지의 다른 이벤트 버튼은 남긴다."""
    msg = cb["message"]
    rows = (msg.get("reply_markup") or {}).get("inline_keyboard") or []
    left = [r for r in rows if not any(b.get("callback_data", "").endswith(f":{event_id}") for b in r)]
    if left and len(left) < len(rows):
        tg.set_keyboard(msg["message_id"], left)
    else:
        tg.clear_buttons(msg["message_id"])


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
            ex: Extracted, manual: str = "") -> bool:
    """초안 생성 실패 시 False(알림만 간 상태 유지). manual이 있으면 API로 게시할 수 없는 경우라
    버튼 없이 초안만 보낸다(복사해서 직접 작성). 이 초안에 '검수 ...'로 답장하면 이미 쓴 댓글을 검토해 준다."""
    try:
        text = extractor.draft_comment(title, description, ex)
    except Exception:  # noqa: BLE001
        return False
    notes = _notes(ex)
    if manual or ex.macro_banned:  # 자동 게시하지 않고 초안만 보낸다
        notes = "\n".join(p for p in (manual, notes) if p)
        msg_id = tg.send(_draft_message(title, text, notes, can_post=False)
                         + "\n\n이미 직접 댓글을 쓰셨다면 이 메시지에 '검수' + 쓰신 댓글로 답장하세요. 양식을 확인해 드립니다.")
        db.set_draft(conn, event_id, text, msg_id)
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
    keywords = parsed.get("required_keywords", [])
    min_lines = int(parsed.get("comment_min_lines") or 0)
    req = json.loads(row["requirements"] or "{}")
    req.update({"keywords": keywords, "min_lines": min_lines, "entry_format": parsed.get("entry_format", text)})
    db.update_event(conn, row["source_url"], requirements=json.dumps(req, ensure_ascii=False))
    ex = _ex_from_row(row, keywords=keywords, min_lines=min_lines,
                      entry_format=parsed.get("entry_format", text))
    if not propose(conn, tg, extractor, event_id, row["title"], row["raw_text"] or "", ex):
        tg.send("댓글 초안을 만들지 못했습니다. 잠시 후 양식을 다시 답장해 주세요.")
        db.update_event(conn, row["source_url"], status="awaiting_format")
        return
    db.set_meta(conn, f"last_format:{row['host']}", text)


REVIEW_PREFIX = re.compile(r"^\s*(검수|확인|리뷰)\s*[:：]?\s*")


def review_comment(comment: str, keywords: list[str], min_lines: int) -> dict:
    """이미 쓴 댓글이 이벤트 양식(필수 키워드·최소 줄 수)에 맞는지 검토하고, 틀리면 수정안을 만든다."""
    lines = [ln for ln in comment.split("\n") if ln.strip()]
    missing = [k for k in keywords if k not in comment]
    short = min_lines > 1 and len(lines) < min_lines
    fixed = comment
    if missing or short:
        fixed = fit_comment(comment, Extracted(required_keywords=keywords, comment_min_lines=min_lines))
    return {"ok": not (missing or short), "missing": missing, "lines": len(lines),
            "min_lines": min_lines, "fixed": fixed.strip()}


def _handle_review(conn, tg, event_id: int, comment: str) -> None:
    row = db.get_event(conn, event_id)
    if row is None:
        return
    req = json.loads(row["requirements"] or "{}")
    keywords, min_lines = req.get("keywords", []), int(req.get("min_lines") or 0)
    if not comment.strip():
        tg.send("검수할 댓글을 '검수' 뒤에 붙여서 답장해 주세요.\n예) 검수\n보겸 선물 받고 싶어요\n아이폰듀오 가즈아")
        return
    if not keywords and min_lines <= 1:
        tg.send("이 이벤트의 댓글 양식(필수 키워드·줄 수)을 아직 몰라 검수할 수 없어요. "
                "영상 말미의 양식을 먼저 답장으로 알려주세요.")
        return
    res = review_comment(comment, keywords, min_lines)
    rule = " · ".join(p for p in ("키워드 " + ", ".join(keywords) if keywords else "",
                                  f"{min_lines}줄 이상" if min_lines > 1 else "") if p)
    if res["ok"]:
        tg.send(f"✅ 양식에 맞습니다 ({rule}) — {res['lines']}줄.\n※ 키워드·줄 수만 확인했어요. 같은 문구를 복사해 "
                "여러 번 쓴 댓글은 자동 필터에 걸릴 수 있습니다.")
        return
    problems = []
    if res["missing"]:
        problems.append("빠진 키워드: " + ", ".join(res["missing"]))
    if res["min_lines"] > 1 and res["lines"] < res["min_lines"]:
        problems.append(f"줄 수 부족: {res['lines']}줄 (필요 {res['min_lines']}줄 이상)")
    entry = conn.execute("SELECT payload FROM entries WHERE event_id = ? AND method = 'comment'",
                         (event_id,)).fetchone()
    buttons = None
    note = "기존 댓글의 ⋮ → 수정에서 위 내용으로 바꿔 주세요(글을 지우고 새로 쓰면 중복 응모가 될 수 있어요)."
    if entry:  # 봇이 게시한 댓글이면 버튼으로 바로 수정
        db.set_meta(conn, f"fix_text:{event_id}", res["fixed"])
        buttons = [("✏️ 수정 적용", f"fix:{event_id}")]
        note = "봇이 올린 댓글이라 아래 버튼으로 바로 수정할 수 있어요."
    tg.send(f"❌ 양식이 맞지 않아요 ({rule})\n- " + "\n- ".join(problems)
            + f"\n\n수정 제안:\n{res['fixed']}\n\n{note}", buttons=buttons)


def do_fix(conn, yt_user, event_id: int) -> str:
    text = db.get_meta(conn, f"fix_text:{event_id}")
    entry = conn.execute("SELECT payload FROM entries WHERE event_id = ? AND method = 'comment'",
                         (event_id,)).fetchone()
    if not text or not entry:
        return "수정할 댓글 정보가 없습니다"
    try:
        yt_user.update_comment(entry["payload"], text)
    except httpx.HTTPStatusError as e:
        return f"❌ 수정 실패 ({e.response.status_code}): {e.response.text[:200]}"
    db.set_draft(conn, event_id, text, None)
    return "✅ 댓글을 수정했습니다"


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
            req = json.loads(row["requirements"] or "{}")
            targets = list(dict.fromkeys([row["channel_id"], *req.get("subscribe_channels", [])]))
            results = [yt_user.subscribe(cid) for cid in targets]
            done.append(f"구독 {len(targets)}개 채널" if any(results) else "이미 구독 중")
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
        elif action == "fix":
            result = do_fix(conn, yt_user, event_id)
            tg.answer_callback(cb["id"], result.splitlines()[0])
            tg.send(result)
            if result.startswith("✅"):
                tg.clear_buttons(msg_id)
        elif action in ("entered", "dislike"):
            result = (do_entered if action == "entered" else do_dislike)(conn, event_id)
            tg.answer_callback(cb["id"], result.splitlines()[0])
            tg.send(result)
            _drop_event_buttons(tg, cb, event_id)
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
    if text and not reply and _handle_block_command(conn, tg, text):
        return
    if not reply or not text:
        return
    format_event = db.get_meta(conn, f"format_req:{reply['message_id']}")
    review = REVIEW_PREFIX.match(text)
    if review:  # '검수 <내가 쓴 댓글>' — 초안/양식요청 메시지에 답장
        target = int(format_event) if format_event else db.event_id_by_draft_message(conn, reply["message_id"])
        if target is not None:
            _handle_review(conn, tg, target, text[review.end():])
            return
    if format_event:
        _handle_format_reply(conn, tg, extractor, int(format_event), text)
        return
    event_id = db.event_id_by_draft_message(conn, reply["message_id"])
    if event_id is None:
        return
    row = db.get_event(conn, event_id)
    if not row or row["status"] != "awaiting_approval":
        tg.send("이 초안은 버튼 없이 직접 작성하는 용도거나 이미 처리된 이벤트예요. 이미 쓰신 댓글을 확인하려면 "
                "'검수' 뒤에 댓글을 붙여 답장하세요.")
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
