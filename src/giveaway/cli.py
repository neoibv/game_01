import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

import json

from . import approval, auth, db, state
from .collectors import sites as sites_mod
from .collectors.youtube import YouTubeClient
from .detect import detect, load_filters
from .extract import Extracted, Extractor
from .rank import parse_deadline, score
from .telegram_bot import Telegram

ROOT = Path(__file__).resolve().parents[2]
LOOKBACK_FIRST_RUN_DAYS = 30
MAX_NOTIFY_PER_RUN = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def format_alert(video, matched: list[str]) -> str:
    """AI 추출 없이 보내는 기본 알림."""
    snippet = video.pinned_comment or video.description
    return (
        f"🎁 [{video.channel_name}] 이벤트 후보\n{video.title}\n"
        f"키워드: {', '.join(matched)}\n\n{snippet[:300]}\n\n{video.url}"
    )


METHOD_KO = {"comment": "댓글", "subscribe": "구독", "like": "좋아요", "google_form": "구글폼",
             "form": "폼", "click": "클릭", "sns_share": "SNS 공유", "other": "기타"}


def format_extracted_alert(video, ex: Extracted, sc: int) -> str:
    lines = [f"🎁 [{video.channel_name}] {video.title}", f"점수 {sc}/100"]
    if ex.prize:
        value = f" (약 {ex.prize_value_est:,}원)" if ex.prize_value_est else ""
        lines.append(f"경품: {ex.prize}{value}")
    if ex.entry_methods:
        lines.append("응모: " + " + ".join(METHOD_KO.get(m, m) for m in ex.entry_methods))
    if ex.comment_prompt:
        lines.append(f"댓글 주제: {ex.comment_prompt}")
    if ex.required_keywords:
        lines.append("필수 문구: " + ", ".join(ex.required_keywords))
    if ex.form_url:
        lines.append(f"폼: {ex.form_url}")
    lines.append(f"마감: {ex.deadline or '미상'}")
    if ex.announce_at or ex.announce_where:
        lines.append(f"발표: {ex.announce_at} {ex.announce_where}".strip())
    if ex.macro_banned:
        lines.append("⚠️ 매크로/부정 참여 금지 문구 있음 — 직접 응모 권장")
    if ex.needs_login_or_captcha:
        lines.append("⚠️ 외부 로그인/본인인증 필요")
    lines.append(video.url)
    return "\n".join(lines)


def _extract(extractor: Extractor | None, video) -> Extracted | None:
    """추출 실패 시 None → 기본 알림으로 대체해 이벤트를 놓치지 않는다."""
    if extractor is None:
        return None
    try:
        return extractor.extract(video.text, title=video.title,
                                 published_at=video.published_at, today=_now().date().isoformat())
    except Exception as e:  # noqa: BLE001 — 네트워크/스키마 오류 모두 폴백
        print(f"extract 실패, 기본 알림으로 대체: {e}", file=sys.stderr)
        return None


SOURCE_TAGS = {"danawa": ["it"]}  # 다나와 이벤트는 IT/가전 위주


def format_site_alert(item, ex: Extracted | None, sc: int | None) -> str:
    lines = [f"🎁 [{item.source}] {item.title}"]
    if ex is None:
        lines += [item.text, item.url]
        return "\n".join(lines)
    lines.append(f"점수 {sc}/100")
    if ex.prize or item.prize:
        value = f" (약 {ex.prize_value_est:,}원)" if ex.prize_value_est else ""
        lines.append(f"경품: {ex.prize or item.prize}{value}")
    if ex.entry_methods:
        lines.append("응모: " + " + ".join(METHOD_KO.get(m, m) for m in ex.entry_methods))
    lines.append(f"마감: {ex.deadline or item.deadline or '미상'}")
    if ex.macro_banned:
        lines.append("⚠️ 매크로/부정 참여 금지 문구 있음")
    if ex.needs_login_or_captcha:
        lines.append("⚠️ 외부 로그인/본인인증 필요 — 직접 응모")
    lines.append(item.url)
    return "\n".join(lines)


def collect_sites(conn, items: list, filters: dict, notify,
                  extractor: Extractor | None = None) -> dict:
    """모음 사이트 항목 처리. 알림 한도에 닿으면 나머지는 저장하지 않고 다음 실행으로 미룬다."""
    stats = {"seen": len(items), "new": 0, "skipped": 0}
    notified = 0
    for item in items:
        if db.url_exists(conn, item.url) or db.title_exists(conn, item.title):
            continue
        if notified >= MAX_NOTIFY_PER_RUN:
            break
        ex = _extract_text(extractor, item)
        # AI가 없으면 키워드/경품 정보가 있는 항목만 후보로 본다
        if extractor is None and not (item.prize or detect(item.text, filters).is_candidate):
            db.add_event(conn, source=item.source, source_url=item.url, title=item.title,
                         host=item.host, matched=[], raw_text=item.text)
            db.update_event(conn, item.url, status="skipped")
            stats["skipped"] += 1
            continue
        db.add_event(conn, source=item.source, source_url=item.url, title=item.title,
                     host=item.host, matched=[], raw_text=item.text)
        if ex is not None and (not ex.is_giveaway or ex.is_ended):
            db.update_event(conn, item.url, status="skipped")
            stats["skipped"] += 1
            continue
        sc = None
        if ex is not None:
            deadline = ex.deadline or item.deadline
            sc = score(tags=SOURCE_TAGS.get(item.source, []), prize_value_est=ex.prize_value_est,
                       entry_methods=ex.entry_methods, deadline=deadline, now=_now())
            db.update_event(conn, item.url, prize=ex.prize or item.prize,
                            prize_value_est=ex.prize_value_est,
                            entry_methods=",".join(ex.entry_methods), deadline=deadline,
                            macro_banned=int(ex.macro_banned), score=sc)
        else:
            db.update_event(conn, item.url, prize=item.prize, deadline=item.deadline)
        notify(format_site_alert(item, ex, sc))
        db.mark_notified(conn, item.url)
        notified += 1
        stats["new"] += 1
    return stats


def _extract_text(extractor: Extractor | None, item) -> Extracted | None:
    if extractor is None:
        return None
    try:
        return extractor.extract(item.text, title=item.title, published_at="",
                                 today=_now().date().isoformat())
    except Exception as e:  # noqa: BLE001
        print(f"extract 실패({item.url}), 기본 알림으로 대체: {e}", file=sys.stderr)
        return None


def remind_and_expire(conn, notify, now: datetime | None = None) -> dict:
    """마감 24시간 이내 리마인더 1회, 마감 지난 건 expired 처리."""
    now = now or _now()
    out = {"reminded": 0, "expired": 0}
    for row in db.open_events(conn):
        dl = parse_deadline(row["deadline"] or "")
        if not dl:
            continue
        if dl < now:
            db.update_event(conn, row["source_url"], status="expired")
            out["expired"] += 1
        elif (dl - now) <= timedelta(hours=24) and not row["reminded"]:
            notify(f"⏰ 마감 임박 ({row['deadline']})\n{row['title']}\n{row['source_url']}")
            db.update_event(conn, row["source_url"], reminded=1)
            out["reminded"] += 1
    return out


def collect(conn, yt: YouTubeClient, channels: list[dict], filters: dict,
            notify, extractor: Extractor | None = None, tg: Telegram | None = None) -> dict:
    """tg가 있으면 댓글 이벤트에 한해 초안+승인 버튼을 추가로 보낸다."""
    last_run = db.get_meta(conn, "last_collect_at")
    published_after = last_run or _iso(_now() - timedelta(days=LOOKBACK_FIRST_RUN_DAYS))
    stats = {"channels": 0, "videos": 0, "new": 0, "skipped": 0, "unresolved": []}
    notified = 0

    for ch in channels:
        cached = db.get_meta(conn, f"channel:{ch['name']}")
        if cached:
            channel_id, uploads = cached.split("|")
        else:
            resolved = yt.resolve_channel(ch["name"], ch.get("handle", ""))
            if not resolved:
                stats["unresolved"].append(ch["name"])
                continue
            channel_id, uploads = resolved
            db.set_meta(conn, f"channel:{ch['name']}", f"{channel_id}|{uploads}")
            notify(f"📺 채널 확정: {ch['name']} → https://www.youtube.com/channel/{channel_id}\n"
                   "다른 채널이면 알려주세요.")
        stats["channels"] += 1

        ids = yt.recent_video_ids(uploads, published_after)
        for video in yt.videos(ids, ch["name"]):
            stats["videos"] += 1
            det = detect(video.text, filters)
            if not det.is_candidate:
                video.pinned_comment = yt.pinned_comment(video.video_id, channel_id)
                det = detect(video.text, filters)
            if not det.is_candidate:
                continue
            is_new = db.add_event(conn, source="youtube", source_url=video.url,
                                  title=video.title, host=video.channel_name,
                                  matched=det.matched, raw_text=video.text)
            if not is_new:
                continue
            ex = _extract(extractor, video)
            if ex is not None and (not ex.is_giveaway or ex.is_ended):
                db.update_event(conn, video.url, status="skipped")
                stats["skipped"] += 1
                continue
            stats["new"] += 1
            if ex is None:
                text = format_alert(video, det.matched)
            else:
                sc = score(tags=ch.get("tags", []), prize_value_est=ex.prize_value_est,
                           entry_methods=ex.entry_methods, deadline=ex.deadline, now=_now())
                db.update_event(
                    conn, video.url, prize=ex.prize, prize_value_est=ex.prize_value_est,
                    entry_methods=",".join(ex.entry_methods),
                    requirements=json.dumps({"keywords": ex.required_keywords,
                                             "comment_prompt": ex.comment_prompt,
                                             "form_url": ex.form_url}, ensure_ascii=False),
                    macro_banned=int(ex.macro_banned), auto_enterable=int(ex.auto_enterable),
                    deadline=ex.deadline, announce_at=ex.announce_at,
                    announce_where=ex.announce_where, score=sc)
                text = format_extracted_alert(video, ex, sc)
            db.update_event(conn, video.url, video_id=video.video_id, channel_id=channel_id)
            if notified < MAX_NOTIFY_PER_RUN:
                notify(text)
                db.mark_notified(conn, video.url)
                notified += 1
                if tg and ex is not None and approval.proposable(ex):
                    approval.propose(conn, tg, extractor, db.event_id_by_url(conn, video.url),
                                     video.title, video.description, ex)

    if stats["unresolved"]:
        notify("⚠️ 채널을 찾지 못함: " + ", ".join(stats["unresolved"]))
    db.set_meta(conn, "last_collect_at", _iso(_now()))
    return stats


def _env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        sys.exit(f"환경변수 {name} 가 필요합니다")
    return value


def cmd_collect(args) -> None:
    channels = yaml.safe_load((ROOT / "config/channels.yaml").read_text(encoding="utf-8"))["channels"]
    filters = load_filters(ROOT / "config/filters.yaml")
    token, chat = _env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID")
    conn = db.connect(Path(args.db))
    tg = Telegram(token, chat)
    notify = tg.send
    key = os.environ.get("ANTHROPIC_API_KEY")
    extractor = Extractor(key) if key else None
    if not extractor:
        print("ANTHROPIC_API_KEY 없음 → AI 추출 없이 기본 알림", file=sys.stderr)
    can_enter = all(os.environ.get(k) for k in
                    ("YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"))
    stats = collect(conn, YouTubeClient(_env("YOUTUBE_API_KEY")), channels, filters,
                    notify, extractor, tg if (extractor and can_enter) else None)
    enabled = yaml.safe_load((ROOT / "config/sources.yaml").read_text(encoding="utf-8"))["sites"]
    items, failed = sites_mod.fetch_all(_now().date(), enabled=enabled)
    site_stats = collect_sites(conn, items, filters, notify, extractor)
    prev_failed = db.get_meta(conn, "sites_failed") or ""
    now_failed = ",".join(failed)
    if failed and now_failed != prev_failed:  # 같은 실패를 3시간마다 반복 알림하지 않음
        notify("⚠️ 사이트 수집 실패: " + ", ".join(failed))
    db.set_meta(conn, "sites_failed", now_failed)
    print(stats, site_stats, remind_and_expire(conn, notify))


def cmd_poll(args) -> None:
    from .enter.youtube import YouTubeUser
    tg = Telegram(_env("TELEGRAM_BOT_TOKEN"), _env("TELEGRAM_CHAT_ID"))
    conn = db.connect(Path(args.db))
    user = YouTubeUser(_env("YOUTUBE_CLIENT_ID"), _env("YOUTUBE_CLIENT_SECRET"),
                       _env("YOUTUBE_REFRESH_TOKEN"))
    print("처리한 업데이트:", approval.poll(conn, tg, user))


def cmd_auth(args) -> None:
    token = auth.run(_env("YOUTUBE_CLIENT_ID"), _env("YOUTUBE_CLIENT_SECRET"))
    print("\nYOUTUBE_REFRESH_TOKEN 값 (GitHub Secrets에 등록, 타인에게 공유 금지):\n" + token)


def cmd_state(args) -> None:
    key = _env("STATE_KEY")
    src, dst = Path(args.src), Path(args.dst)
    (state.encrypt_file if args.action == "encrypt" else state.decrypt_file)(src, dst, key)


def main() -> None:
    p = argparse.ArgumentParser(prog="giveaway")
    sub = p.add_subparsers(required=True)
    c = sub.add_parser("collect")
    c.add_argument("--db", default="data/giveaways.db")
    c.set_defaults(func=cmd_collect)
    pl = sub.add_parser("poll")
    pl.add_argument("--db", default="data/giveaways.db")
    pl.set_defaults(func=cmd_poll)
    sub.add_parser("auth").set_defaults(func=cmd_auth)
    s = sub.add_parser("state")
    s.add_argument("action", choices=["encrypt", "decrypt"])
    s.add_argument("src")
    s.add_argument("dst")
    s.set_defaults(func=cmd_state)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
