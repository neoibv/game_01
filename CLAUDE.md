# CLAUDE.md

## Project Overview

giveaway-hunter — 국내 경품·사은품 이벤트를 자동으로 수집하고 응모를 돕는 도구. 알림은 **텔레그램**, 실행은 **GitHub Actions**(PC 불필요).
소스: IT 유튜버(설정 채널 + **검색으로 발견한 소규모 채널**), 보겸TV/보겸S **커뮤니티 게시물**.

설계 원문은 `docs/PLAN.md`(초기 계획 — 구현은 이후 크게 확장됨, 아래와 README가 현재 기준), 사용자 설정 안내는 `docs/SETUP.md`.

## Quick Start (개발)

```bash
python3 -m venv .venv && .venv/bin/pip install -e . pytest respx pyflakes
.venv/bin/python -m pytest -q          # 120개, 네트워크 없이 respx 모킹
.venv/bin/python -m pyflakes src tests
```
Python ≥ 3.12 (워크플로는 3.12). 사용자 PC는 3.10이라 `python -m giveaway.cli auth`를 `PYTHONPATH=src`로 직접 실행해 OAuth 토큰만 발급한다.

## Architecture

```
src/giveaway/
├── cli.py            # collect(유튜브·발견·커뮤니티) / poll / watch / auth / state 명령, 판정(_decide, analyze_video)
├── extract.py        # Claude(Haiku 5.5) tool use: 이벤트 구조화(Extracted), 댓글 초안, 양식 해석(parse_format), fit_comment
├── approval.py       # 텔레그램 초안·[게시] 버튼·양식 요청/답장·'검수' 댓글 검토·do_post/do_fix
├── digest.py         # 알림 형식(유튜브 묶음 + 하단 '응모한 이벤트·결과 발표일' 기록), 분야 분류·차단어 키워드, 메시지 분할
├── discover.py       # 설정 밖 채널 발견(검색 → IT 키워드·구독자 필터 → 구독자 적은 순)
├── detect.py         # 이벤트 키워드, 제외 분야(excluded_topic)
├── rank.py           # 점수(IT·경품가치·난이도·마감·댓글 수), 마감 파싱
├── winners.py        # 응모 후 당첨 발표 감시(채널 주인 답글, 핸들 언급)
├── ghapi.py          # GitHub Actions dispatch / ensure_watcher
├── db.py, state.py   # SQLite(+자동 마이그레이션), Fernet 암호화 후 state 브랜치에 저장
├── telegram_bot.py   # send / peek_updates(롱폴링, 소비 안 함) / get_updates / answer_callback
├── collectors/       # youtube.py(API), community.py(게시물 페이지 파싱)
└── enter/youtube.py  # OAuth 댓글·구독·좋아요·댓글 수정
config/               # channels.yaml, discovery.yaml, filters.yaml(exclude_topics 포함)
.github/workflows/    # collect(하루 1회+보조 2회) / poll / watch
```

## Rules

- 범위는 국내 이벤트. 자동 가능한 것은 자동, **공개 게시(댓글)와 개인정보 폼 제출은 텔레그램 승인 후**.
- 매크로 금지 문구가 있거나 외부 로그인·본인인증이 필요한 응모는 자동화하지 않고 알림/초안만.
- **차단/제한은 우회하지 않는다**(Cloudflare 봇 차단 사이트, YouTube의 GitHub IP 자막 차단, 쿼터). 실패는 텔레그램으로 알린다.
- 토큰·비밀번호·개인정보는 커밋 금지(GitHub Secrets). 레포가 public이라 상태 DB는 암호화해 `state` 브랜치에만.
- 사용자 선호: IT·전자기기 1순위 / 아기·출산 2순위 / 기프티콘·여행 3순위, **키보드 제외**(`filters.yaml: exclude_topics`), 가입·구매 조건 이벤트 제외, 마감 지난 이벤트 제외.
- 커밋은 한국어(`feat:`/`fix:`/`docs:`), 모든 변경은 작업 브랜치 → PR → squash merge.

## Hard-won facts (실제 데이터로 확인한 것 — 가정하지 말 것)

- **GitHub `schedule`은 몇 시간씩 늦어진다**(poll `*/15`가 실제 4~5시간 간격, 예약된 collect가 누락되기도 함). 그래서 collect는 보조 시각 2개+20시간 skip 가드, 버튼 응답은 `watch.yml`(텔레그램 롱폴링 → poll 즉시 dispatch)로 처리. `workflow_dispatch`는 GITHUB_TOKEN으로 가능하지만 이 개발 세션의 GitHub 도구는 dispatch 권한이 없다(403) — 진단은 **작업 브랜치 push로 트리거되는 임시 probe 워크플로**로 했다(끝나면 삭제, main엔 두지 않음).
- **YouTube**: 자막(`youtube-transcript-api`)은 GitHub IP에서 `IpBlocked`. 커뮤니티 게시물 페이지(`/channel/<id>/posts`)는 읽힘(postId·본문·상대시각·링크 URL). 게시글 댓글 작성 API 없음 → 초안만 제공. 검색(`search.list`)은 **모든 단어 AND 매칭**이라 쿼리는 1~3단어, 쿼리당 100 unit(하루 10,000, 태평양시 자정 초기화). 429는 쿼터 소진.
- **Anthropic Haiku 5.5**: thinking이 max_tokens를 먹어 초안이 잘리거나 비는 일이 있었다 → max_tokens 넉넉히 + `stop_reason == max_tokens`는 오류 처리. AI가 빈 값을 `""`/'명시되지 않음'으로 채우는 경우를 `_clean`으로 보정. API 400은 본문을 오류 메시지에 담는다(크레딧 부족이 흔한 원인).
- 보겸: 이벤트의 진짜 출처는 **커뮤니티 게시물**(+거기 링크된 영상). 게시물 본문에 키워드·줄 수 양식이 적혀 있고, 링크된 영상의 양식은 영상 말미 음성 안내라 사용자가 답장으로 알려줘야 한다(`format_in_video`). 멤버십은 대개 별도 당첨 풀(필수 아님).
- 이벤트 판정 기준(유튜브): 진행 중 + (응모 링크 or 다수 시청자의 같은 양식 댓글 or 주인 공식 게시물) 일 때만 확정, 근거 없으면 72시간 보류 재확인. 알림 전송 실패 시 DB에서 지워 재시도(조용한 유실 방지).
- 이벤트 모음 사이트(이벤트 코리아·줍줍·다나와) 수집은 의미가 없어 제거했다. 다시 붙이지 말 것.
- 알림마다 이벤트별 [응모함]/[관심없음] 버튼. 응모함 → `entries`에 `manual`로 기록(status `entered`), 알림 하단에 응모 목록과 결과 발표일(`announce_at`). 관심없음 → 이벤트 종료 + 제품 분류 어휘(`digest.KEYWORDS`, 3자 이상)를 meta `blocked_topics`에 저장해 제목·제품·경품에 걸리면 제외('차단해제 단어'·'차단목록' 메시지로 관리).

## Testing conventions

- 파서는 저장된 HTML/JSON 픽스처(`tests/fixtures/`)로, API는 respx로 모킹. 실제 형태는 임시 probe 워크플로로 확인한 뒤 픽스처화.
- 새 외부 소스를 붙일 때: ① probe로 실제 응답 확인 ② 파서+테스트 ③ 실패 시 우회 없이 텔레그램 경고.
