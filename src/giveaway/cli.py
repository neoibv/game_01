import argparse
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import json

import yaml

from . import approval, auth, db, digest, state, winners
from .collectors import sites as sites_mod
from .collectors.youtube import YouTubeClient
from .detect import detect, load_filters
from .extract import Extracted, Extractor
from .rank import parse_deadline, score
from .telegram_bot import Telegram

ROOT = Path(__file__).resolve().parents[2]
LOOKBACK_FIRST_RUN_DAYS = 30
MAX_NOTIFY_PER_RUN = 20
PENDING_HOURS = 72  # 응모 근거가 아직 없는 영상을 다시 확인해 주는 기간
EXTERNAL_LINK = re.compile(r"https?://(?!(?:www\.|m\.)?(?:youtube\.com|youtu\.be))[^\s)]+")
SOURCE_TAGS = {"danawa": ["it"]}  # 다나와 이벤트는 IT/가전 위주


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _deliver_batch(conn, urls: list[str], notify, text: str, keep_pending: set[str] = frozenset()) -> None:
    """묶음 메시지 전송. 실패하면 저장한 이벤트를 되돌려 다음 실행에서 다시 시도한다(조용히 유실 방지)."""
    try:
        for chunk in digest.split_message(text):
            notify(chunk)
    except Exception:
        for url in urls:
            if url in keep_pending:
                db.update_event(conn, url, status="pending")
            else:
                db.delete_event(conn, url)
        raise
    for url in urls:
        db.mark_notified(conn, url)


def _decide(ex: Extracted | None, text: str) -> str:
    """confirmed | pending | skipped. AI가 없으면 외부 응모 링크가 있는 것만 확정."""
    if ex is None:
        return "confirmed" if EXTERNAL_LINK.search(text) else "skipped"
    if ex.is_real_event:
        return "confirmed"
    return "pending" if ex.undecided else "skipped"


def _extract_text(extractor: Extractor | None, item) -> Extracted | None:
    if extractor is None:
        return None
    try:
        return extractor.extract(item.text, title=item.title, published_at="",
                                 today=_now().date().isoformat())
    except Exception as e:  # noqa: BLE001
        print(f"extract 실패({item.url}), 키워드 분류로 대체: {e}", file=sys.stderr)
        return None


def collect_sites(conn, items: list, filters: dict, notify,
                  extractor: Extractor | None = None) -> dict:
    """모음 사이트 항목을 분류(IT > 아기·출산 > 기프티콘·여행·기타)해 한 번에 묶어 보낸다.
    한도에 닿으면 나머지는 저장하지 않고 다음 실행으로 미룬다."""
    stats = {"seen": len(items), "new": 0, "skipped": 0}
    entries: list[digest.SiteEntry] = []
    for item in items:
        if db.url_exists(conn, item.url) or db.title_exists(conn, item.title):
            continue
        if len(entries) >= MAX_NOTIFY_PER_RUN:
            break
        ex = _extract_text(extractor, item)
        db.add_event(conn, source=item.source, source_url=item.url, title=item.title,
                     host=item.host, matched=[], raw_text=item.text)
        # AI가 없으면 키워드/경품 정보가 있는 항목만 후보로 본다
        no_ai_reject = extractor is None and not (item.prize or detect(item.text, filters).is_candidate)
        if no_ai_reject or (ex is not None and (not ex.is_giveaway or ex.is_ended)):
            db.update_event(conn, item.url, status="skipped")
            stats["skipped"] += 1
            continue
        category = ex.category if ex else digest.classify(item.text)
        if category == "other" and item.source == "danawa":
            category = "it"
        deadline = (ex.deadline if ex else "") or item.deadline
        sc = score(tags=SOURCE_TAGS.get(item.source, []), prize_value_est=ex.prize_value_est if ex else 0,
                   entry_methods=ex.entry_methods if ex else [], deadline=deadline, now=_now())
        prize = (ex.prize if ex else "") or item.prize
        db.update_event(conn, item.url, prize=prize, deadline=deadline, category=category, score=sc,
                        prize_value_est=ex.prize_value_est if ex else 0,
                        entry_methods=",".join(ex.entry_methods) if ex else "",
                        macro_banned=int(bool(ex and ex.macro_banned)))
        entries.append(digest.SiteEntry(
            source=item.source, title=item.title, prize=prize, deadline=deadline, url=item.url,
            category=category, score=sc,
            manual=bool(ex and (ex.macro_banned or ex.needs_login_or_captcha))))
        stats["new"] += 1
    if entries:
        _deliver_batch(conn, [e.url for e in entries], notify, digest.format_sites(entries))
    return stats


def remind_and_expire(conn, notify, now: datetime | None = None) -> dict:
    """마감 24시간 이내 리마인더(한 메시지로 묶음) 1회, 마감 지난 건 expired 처리."""
    now = now or _now()
    out = {"reminded": 0, "expired": 0}
    due = []
    for row in db.open_events(conn):
        if row["status"] == "entered":  # 응모 완료 건은 winners.check가 관리
            continue
        dl = parse_deadline(row["deadline"] or "")
        if not dl:
            continue
        if dl < now:
            db.update_event(conn, row["source_url"], status="expired")
            out["expired"] += 1
        elif (dl - now) <= timedelta(hours=24) and not row["reminded"]:
            due.append(row)
    if due:
        lines = [f"⏰ 마감 임박 ({len(due)}건)"]
        for row in due:
            lines.append(f"• {row['title']} (~{row['deadline']})\n  {row['source_url']}")
        notify("\n\n".join([lines[0], "\n".join(lines[1:])]))
        for row in due:
            db.update_event(conn, row["source_url"], reminded=1)
        out["reminded"] = len(due)
    return out


@dataclass
class _Confirmed:
    entry: digest.YtEntry
    ex: Extracted | None
    title: str
    description: str
    from_pending: bool = False


def _confirm(conn, url: str, ex: Extracted | None, *, title: str, channel: str, text: str,
             tags: list[str], channel_id: str, video_id: str) -> digest.YtEntry:
    link = ""
    if ex is None:
        m = EXTERNAL_LINK.search(text)
        link = m.group(0) if m else ""
        entry = digest.YtEntry(channel=channel, title=title, product="", deadline="", url=url,
                               apply_link=link)
        db.update_event(conn, url, video_id=video_id, channel_id=channel_id)
        return entry
    sc = score(tags=tags, prize_value_est=ex.prize_value_est, entry_methods=ex.entry_methods,
               deadline=ex.deadline, now=_now())
    product = ex.product or ex.prize
    db.update_event(
        conn, url, prize=ex.prize, product=product, category=ex.category,
        prize_value_est=ex.prize_value_est, entry_methods=",".join(ex.entry_methods),
        requirements=json.dumps({"keywords": ex.required_keywords, "comment_prompt": ex.comment_prompt,
                                 "form_url": ex.form_url}, ensure_ascii=False),
        macro_banned=int(ex.macro_banned), auto_enterable=int(ex.auto_enterable),
        deadline=ex.deadline, announce_at=ex.announce_at, announce_where=ex.announce_where,
        score=sc, video_id=video_id, channel_id=channel_id)
    return digest.YtEntry(channel=channel, title=title, product=product, deadline=ex.deadline,
                          url=url, apply_link=ex.form_url, score=sc)


def collect(conn, yt: YouTubeClient, channels: list[dict], filters: dict,
            notify, extractor: Extractor | None = None, tg: Telegram | None = None) -> dict:
    """유튜브 이벤트를 한 메시지로 묶어 보낸다.
    확정 기준: 진행 중인 경품 이벤트이면서 (응모 링크가 있거나 여러 시청자가 같은 양식으로 댓글 참여).
    근거가 아직 없는 영상은 pending으로 두고 PENDING_HOURS 동안 다시 확인한다.
    tg가 있으면 확정된 댓글 이벤트에 한해 초안+승인 버튼을 추가로 보낸다."""
    last_run = db.get_meta(conn, "last_collect_at")
    published_after = last_run or _iso(_now() - timedelta(days=LOOKBACK_FIRST_RUN_DAYS))
    stats = {"channels": 0, "videos": 0, "new": 0, "skipped": 0, "pending": 0, "errors": 0,
             "unresolved": []}
    confirmed: list[_Confirmed] = []
    tags_by_name = {c["name"]: c.get("tags", []) for c in channels}

    # 1) 이전에 근거가 부족했던 영상 재확인
    if extractor:
        for row in db.pending_events(conn):
            url = row["source_url"]
            age = _now() - datetime.strptime(row["first_seen_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
            if age > timedelta(hours=PENDING_HOURS) or not row["video_id"]:
                db.update_event(conn, url, status="skipped")
                continue
            try:
                _, others = yt.comments(row["video_id"], row["channel_id"])
                ex = extractor.extract(row["raw_text"], title=row["title"], published_at="",
                                       today=_now().date().isoformat(), comments=others)
            except Exception as e:  # noqa: BLE001
                print(f"보류 건 재확인 실패({url}): {e}", file=sys.stderr)
                continue
            decision = _decide(ex, row["raw_text"])
            if decision == "skipped":
                db.update_event(conn, url, status="skipped")
            elif decision == "confirmed" and len(confirmed) < MAX_NOTIFY_PER_RUN:
                entry = _confirm(conn, url, ex, title=row["title"], channel=row["host"],
                                 text=row["raw_text"], tags=tags_by_name.get(row["host"], []),
                                 channel_id=row["channel_id"], video_id=row["video_id"])
                confirmed.append(_Confirmed(entry, ex, row["title"], row["raw_text"], True))
                stats["new"] += 1

    # 2) 새 영상
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
            if len(confirmed) >= MAX_NOTIFY_PER_RUN:
                break
            det = detect(video.text, filters)
            pinned, others = "", []
            fetched = False
            if not det.is_candidate:
                pinned, others = yt.comments(video.video_id, channel_id)
                fetched = True
                video.pinned_comment = pinned
                det = detect(video.text, filters)
            if not det.is_candidate:
                continue
            if db.url_exists(conn, video.url):
                continue
            if not fetched:
                pinned, others = yt.comments(video.video_id, channel_id)
                video.pinned_comment = pinned
            db.add_event(conn, source="youtube", source_url=video.url, title=video.title,
                         host=video.channel_name, matched=det.matched, raw_text=video.text)
            db.update_event(conn, video.url, video_id=video.video_id, channel_id=channel_id)
            ex = None
            if extractor:
                try:
                    ex = extractor.extract(video.text, title=video.title, published_at=video.published_at,
                                           today=_now().date().isoformat(), comments=others)
                except Exception as e:  # noqa: BLE001 — 지우고 다음 실행에서 재시도
                    print(f"extract 실패({video.url}), 다음 실행에서 재시도: {e}", file=sys.stderr)
                    db.delete_event(conn, video.url)
                    stats["errors"] += 1
                    continue
            decision = _decide(ex, video.text)
            if decision == "skipped":
                db.update_event(conn, video.url, status="skipped")
                stats["skipped"] += 1
            elif decision == "pending":
                db.update_event(conn, video.url, status="pending")
                stats["pending"] += 1
            else:
                entry = _confirm(conn, video.url, ex, title=video.title, channel=video.channel_name,
                                 text=video.text, tags=ch.get("tags", []), channel_id=channel_id,
                                 video_id=video.video_id)
                confirmed.append(_Confirmed(entry, ex, video.title, video.description))
                stats["new"] += 1

    # 3) 묶음 전송 후 승인 요청
    if confirmed:
        _deliver_batch(conn, [c.entry.url for c in confirmed], notify,
                       digest.format_youtube([c.entry for c in confirmed]),
                       keep_pending={c.entry.url for c in confirmed if c.from_pending})
        if tg and extractor:
            for c in confirmed:
                if c.ex is not None and approval.proposable(c.ex):
                    approval.propose(conn, tg, extractor, db.event_id_by_url(conn, c.entry.url),
                                     c.title, c.description, c.ex)

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
    if args.reset_events:
        print("알림 기록 초기화:", db.reset_events(conn), "건 삭제")
    if args.skip_if_ran_within_hours:
        last = db.get_meta(conn, "last_collect_at")
        if last and _now() - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=timezone.utc) < timedelta(hours=args.skip_if_ran_within_hours):
            print(f"최근 {args.skip_if_ran_within_hours}시간 안에 이미 실행됨 — 건너뜀 ({last})")
            return
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
    win = {}
    if can_enter:
        from .enter.youtube import YouTubeUser
        user = YouTubeUser(os.environ["YOUTUBE_CLIENT_ID"], os.environ["YOUTUBE_CLIENT_SECRET"],
                           os.environ["YOUTUBE_REFRESH_TOKEN"])
        try:
            win = winners.check(conn, YouTubeClient(_env("YOUTUBE_API_KEY")), user, notify)
        except Exception as e:  # noqa: BLE001 — 당첨 확인 실패가 수집을 막지 않게
            print(f"당첨 확인 실패: {e}", file=sys.stderr)
    # AI 분석이 실패하면 로그를 안 봐도 알 수 있게 텔레그램으로 알린다(같은 원인은 반복 알림 안 함)
    if extractor and extractor.errors:
        msg = f"⚠️ AI 분석 {extractor.errors}건 실패 — 키워드로 대체했거나 다음 실행에서 재시도합니다.\n{extractor.last_error}"
        if db.get_meta(conn, "ai_error") != extractor.last_error:
            notify(msg)
        db.set_meta(conn, "ai_error", extractor.last_error)
    elif extractor:
        db.set_meta(conn, "ai_error", "")
    print(stats, site_stats, remind_and_expire(conn, notify), win)


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
    c.add_argument("--skip-if-ran-within-hours", type=float, default=0,
                   help="마지막 수집이 이 시간 안이면 건너뛴다(예약 보조 실행용)")
    c.add_argument("--reset-events", action="store_true",
                   help="이전 알림 기록을 지우고 최근 30일을 새 형식으로 다시 받는다")
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
