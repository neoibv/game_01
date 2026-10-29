# 경품·사은품 이벤트 자동 수집/응모 시스템 — 실행 계획 (v2)

> 작성일: 2026-10-29 · 범위: **국내 이벤트만** · 1차 우선순위: **IT 유튜버 + 보겸TV/보겸S 댓글·구독 이벤트**
>
> 다음 모델이 이 문서만 보고 구현할 수 있도록 작성했다. 결정 사항은 §1에 확정돼 있으니 다시 묻지 말고 진행한다.

---

## 1. 확정된 결정 사항

| 항목 | 결정 |
|---|---|
| 알림 | **텔레그램 봇** (무료) |
| 실행 위치 | **GitHub Actions** (PC 꺼져 있어도 동작) |
| 감시 유튜버 | 잇섭, 언더케이지, 테크몽, 주연 ZUYONI, 디에디트, 가전주부, 뻘짓연구소, 1분미만, **보겸TV, 보겸S** |
| 자동화 수준 | **자동 가능한 것은 완전 자동. 공개 게시(댓글 등)는 텔레그램 승인 후 게시** |
| 기존 게임 | 소스 전부 삭제 + **GitHub Pages 배포 삭제** (`gh-pages` 브랜치 삭제) |
| 레포 공개 여부 | 현재 **public** 유지 (Actions 무료 무제한). 대신 상태 DB는 암호화해서 저장 (§5) |

### 자동화 범위 상세
| 동작 | 처리 |
|---|---|
| 이벤트 수집·분류·정리·랭킹 | 완전 자동 |
| 새 이벤트 / 마감 D-1 / 당첨 발표 알림 | 완전 자동 |
| 클릭형 응모 (개인정보·로그인·캡차 없음, 유의사항에 매크로 금지 문구 없음) | 완전 자동 |
| 유튜브 **댓글 게시** | AI 초안 → 텔레그램 [게시][수정][건너뛰기] → 승인 시 게시 |
| 유튜브 **구독 / 좋아요** (응모 조건일 때) | 댓글 승인 시 함께 자동 처리 (공개 게시물이 아니므로 별도 승인 없음) |
| 개인정보 입력 폼 (이름·전화·주소), 구글폼 | 승인 후 제출. 값은 GitHub Secrets에서 주입 |
| 로그인·본인인증·캡차가 필요한 사이트 응모 | 자동화하지 않음 → 링크와 함께 "직접 응모" 알림 |

> 유의사항에 "매크로/자동 응모 금지"가 있는 이벤트는 클릭형이어도 자동 응모하지 않고 알림만 보낸다 (LLM 추출 단계에서 `macro_banned` 플래그 판정).

---

## 2. 정보 소스

### 2-1. 유튜브 (1순위)
- 이벤트 노출 위치: ① 영상 설명란 ② 채널 주인이 쓴 고정 댓글 ③ 커뮤니티 탭 게시물 ④ 제목("증정", "이벤트", "추첨")
- 응모 방식: 구독 + 좋아요 + 댓글(질문 답변, 특정 키워드 포함), 커뮤니티 게시물 댓글, 구글폼
- 당첨 발표: 커뮤니티 게시물/고정 댓글에 `@핸들` 나열 → 구글폼으로 연락처 수집 (기한 내 미제출 시 취소)
- 추첨은 댓글 추첨기(중복 제거, 키워드 필터, 구독 여부 확인)를 많이 씀 → **이벤트당 1댓글, 키워드 준수, 구독 필수**

`config/channels.yaml` (채널 ID는 구현 시 `channels.list?forHandle=` 로 조회해 채워 넣고 커밋):
```yaml
channels:
  - { name: 잇섭,        handle: "@ITSub",     tags: [it] }
  - { name: 언더케이지,  handle: "@underkg",   tags: [it] }
  - { name: 테크몽,      handle: "",           tags: [it] }
  - { name: 주연 ZUYONI, handle: "",           tags: [it] }
  - { name: 디에디트,    handle: "",           tags: [it] }
  - { name: 가전주부,    handle: "",           tags: [it] }
  - { name: 뻘짓연구소,  handle: "",           tags: [it] }
  - { name: 1분미만,     handle: "",           tags: [it] }
  - { name: 보겸TV,      handle: "",           tags: [entertainment] }
  - { name: 보겸S,       handle: "",           tags: [entertainment] }
```
> 핸들은 추정값이 섞여 있다. 구현 시 검색(`search.list type=channel`, 100 unit, 1회만)으로 정확한 채널을 찾아 확정하고, 확정 결과를 텔레그램으로 사용자에게 한 번 보여준다.

### 2-2. 이벤트 모음 사이트 / 커뮤니티 (2순위)
| 소스 | 특징 | 순서 |
|---|---|---|
| 퀘이사존 이벤트 게시판 `quasarzone.com/bbs/qe_event` | IT 경품, 글 형식 정형화(기간·인원·포인트). 응모는 로그인+포인트 → **알림만** | 1 |
| 다나와 이벤트 `event.danawa.com` | IT·가전 브랜드 이벤트 | 2 |
| 줍줍 `jupjup.app` | 클릭 몇 번이면 끝나는 무료 응모 큐레이션 → **자동 응모 후보** | 3 |
| 슈퍼투데이 `suto.co.kr` | 하루 100~200건, 가장 큼 | 4 |
| 이벤트코리아 `events.kr` | 카톡·인스타 이벤트, 체험단 | 5 |
| 뽐뿌 이벤트 게시판 | 사용자 공유 이벤트 | 6 |

---

## 3. 기술 설계

### 3-1. 스택
- Python 3.12, `httpx`, `selectolax`, `playwright`(커뮤니티 탭·JS 사이트·클릭형 응모)
- YouTube Data API v3 (API 키: 수집 / OAuth refresh token: 댓글·구독·좋아요)
- SQLite (암호화해서 `state` 브랜치에 저장, §5)
- Claude API (Haiku 계열) — 구조화 추출, `macro_banned` 판정, 댓글 초안
- 텔레그램 Bot API — 알림 + 인라인 버튼

### 3-2. 디렉터리 구조 (레포 루트에 바로 배치)
```
├── pyproject.toml
├── config/
│   ├── channels.yaml
│   ├── sources.yaml          # 소스별 on/off, 주기
│   └── filters.yaml          # 관심/제외 키워드
├── src/giveaway/
│   ├── models.py, db.py, state.py   # state.py: DB 암복호화 + state 브랜치 pull/push
│   ├── collectors/
│   │   ├── youtube.py               # 업로드·설명란·고정댓글
│   │   ├── youtube_community.py     # 커뮤니티 탭 (Playwright)
│   │   └── quasarzone.py, danawa.py, jupjup.py, suto.py, eventskr.py, ppomppu.py
│   ├── detect.py              # 키워드 1차 필터
│   ├── extract.py             # LLM 구조화
│   ├── rank.py
│   ├── telegram_bot.py        # 알림 전송 + getUpdates 폴링으로 버튼 응답 처리
│   ├── enter/
│   │   ├── youtube.py         # 댓글(승인 후) + 구독/좋아요
│   │   ├── click_form.py      # 클릭형 자동 응모 (Playwright)
│   │   └── google_form.py     # 승인 후 제출
│   ├── winners.py             # 당첨 발표 감시
│   └── cli.py                 # collect | poll | enter | remind | winners
├── tests/                     # 저장된 HTML/JSON 픽스처 기반 파서 테스트
└── .github/workflows/
    ├── collect.yml            # 수집 + 알림 + 자동 응모
    └── poll.yml               # 텔레그램 승인 처리
```

### 3-3. 데이터 모델
```
events(id, source, source_url, title, host, prize, prize_value_est,
       entry_method[comment|subscribe|like|form|google_form|click|quiz|sns_share|points],
       requirements(json: 키워드, 구독필수, 좋아요필수 등), macro_banned(bool),
       auto_enterable(bool), start_at, deadline, announce_at, announce_where,
       category, score, raw_text, first_seen_at,
       status[new|notified|awaiting_approval|entered|skipped|expired|failed])
entries(id, event_id, entered_at, method, payload, result[pending|won|lost], note)
tg_messages(message_id, event_id, kind)   # 버튼 응답 ↔ 이벤트 매핑
meta(key, value)                          # 텔레그램 update offset 등
```
중복 제거 키: 정규화된 `source_url` (유튜브는 videoId / postId).

### 3-4. 유튜브 수집 (쿼터)
1. uploads 플레이리스트 ID 캐시 → `playlistItems.list` (1 unit/채널)
2. 신규 영상 `videos.list` (50개당 1 unit) → 제목·설명 키워드 필터
3. 후보만 `commentThreads.list order=relevance` (1 unit) → 채널 주인 고정 댓글 확인
4. 커뮤니티 탭: 하루 2회 Playwright로 최근 게시물 텍스트
5. 후보 → LLM 추출 → DB → 텔레그램
- 10채널 × 하루 8회 ≈ 200 unit. 댓글 게시 50 unit, 구독 50 unit, 좋아요 50 unit. 기본 할당 10,000/일로 충분.

### 3-5. 텔레그램 승인 흐름 (서버 없이 Actions로)
- `poll.yml`이 **15분마다** `getUpdates(offset)` 호출 → 버튼 콜백 처리 → 승인 건 즉시 게시 → offset 저장.
- 승인 후 실제 게시까지 최대 15~30분 지연 (Actions cron 지연 포함). 마감 임박 이벤트는 알림에 "⚠️ 마감 N시간 전" 표시.
- 텔레그램 미처리 업데이트는 24시간 보관되므로 폴링 간격이 길어도 유실 없음.
- [수정] 버튼: 사용자가 답장으로 보낸 텍스트를 댓글 내용으로 사용.
- `TELEGRAM_CHAT_ID`가 아닌 곳에서 온 업데이트는 무시 (봇 오남용 방지).

### 3-6. 댓글 초안 규칙
- 영상 제목·설명·이벤트 질문 반영, 매번 다른 자연스러운 문장, 요구 키워드/해시태그 필수 포함.
- 이벤트당 1회만. 같은 채널에 짧은 간격 연속 게시 금지 (게시 간 최소 2분).

### 3-7. 랭킹
IT 관련성, 경품 추정 가치, 응모 난이도(클릭 < 댓글 < 폼 < 창작), 마감 임박도, 추정 경쟁률(조회수·댓글 수 대비 당첨 인원).

---

## 4. 워크플로 스케줄

| 워크플로 | 주기 (KST 기준 cron은 UTC로 변환) | 하는 일 |
|---|---|---|
| `collect.yml` | 3시간마다 | 유튜브 수집, 사이트 수집, 추출·랭킹, 알림, 클릭형 자동 응모, 마감 D-1 리마인더 |
| `poll.yml` | 15분마다 | 텔레그램 승인 처리 → 댓글·구독·좋아요·폼 제출 |
| `winners.yml` (Phase 5) | 하루 2회 | 응모한 이벤트 발표 확인, 내 핸들 검색 |

- 공통: `concurrency: state` 그룹으로 동시 실행 방지 (DB 충돌 방지).
- public 레포는 Actions 분 무제한 무료. 단 **60일간 레포 활동이 없으면 예약 워크플로가 자동 비활성화**되므로, 상태 커밋이 그 역할을 하는지 확인하고 아니면 월 1회 keepalive 커밋을 넣는다.

---

## 5. 비밀값·상태 저장

### GitHub Secrets
`YOUTUBE_API_KEY`, `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`,
`ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `STATE_KEY`(DB 암호화 키),
`PROFILE_NAME`, `PROFILE_PHONE`, `PROFILE_ADDRESS` (폼 제출용, 레포에 절대 커밋 금지)

### 상태 DB
- 레포가 public이므로 SQLite 파일을 `STATE_KEY`로 암호화(`age` 또는 `cryptography` Fernet)해서 별도 `state` 브랜치에 커밋.
- 실행 시작: state 브랜치에서 받아 복호화 → 실행 종료: 암호화해서 커밋/푸시.
- 로그에 개인정보·토큰이 찍히지 않도록 `::add-mask::` 사용.

### 사용자 준비물 (구현 세션에서 단계별 안내문 작성)
1. 텔레그램 @BotFather로 봇 생성 → 토큰, 봇에게 메시지 보낸 뒤 chat id 확인
2. Google Cloud 프로젝트 → YouTube Data API v3 활성화 → API 키 + OAuth 클라이언트(데스크톱)
3. 로컬에서 1회 `python -m giveaway.cli auth` 실행 → refresh token 발급 → Secrets 등록
   - OAuth 앱이 "테스트" 상태면 refresh token이 7일 만료 → **"프로덕션" 게시** 필요(본인만 사용하므로 검수 없이 경고 화면만 뜸)
4. Anthropic API 키

---

## 6. 구현 순서

### Phase 0 — 레포 정리
- `city-runner/`, `plan.md`, `research.md`, `claude_code_prompt.md` 삭제
- **`gh-pages` 브랜치 삭제** → 배포 중단 확인 (https://neoibv.github.io/game_01/ 404). Settings → Pages에서 소스가 비활성화됐는지 사용자에게 확인 요청
- `CLAUDE.md` 새 프로젝트 기준으로 재작성, `README.md` 작성, `.gitignore`(`.env`, `*.db`, `secrets/`, `__pycache__/`)
- 이 문서를 `docs/PLAN.md`로 이동
- (선택) 레포 이름 `game_01` → 예: `giveaway-hunter` 변경은 사용자가 Settings에서 직접

### Phase 1 — 유튜브 감시 + 텔레그램 알림 (MVP)
- channels.yaml 확정, youtube collector, detect, SQLite + 암호화 state, telegram 알림, `collect.yml`
- 완료 기준: 지난 30일 영상 중 이벤트 영상이 텔레그램으로 온다

### Phase 2 — LLM 구조화 + 랭킹 + 리마인더
- extract (`macro_banned`, `auto_enterable` 포함), rank, 마감 D-1 알림

### Phase 3 — 승인 후 유튜브 응모
- OAuth, `poll.yml`, 댓글 초안 + 버튼, 승인 시 댓글·구독·좋아요, entries 기록

### Phase 4 — 사이트·커뮤니티 수집 + 클릭형 완전 자동 응모
- 퀘이사존 → 다나와 → 줍줍(자동 응모) → 슈퍼투데이 → 이벤트코리아 → 뽐뿌
- 수집기마다 HTML 픽스처 테스트, 요청 간격 ≥ 2초, robots.txt 준수
- 국내 사이트가 해외 IP(GitHub Actions)를 막으면 해당 소스는 비활성화하고 사용자에게 보고

### Phase 5 — 당첨 발표 감시
- 발표 예정일 전후로 커뮤니티 탭/고정 댓글/사이트 발표 페이지에서 내 핸들·닉네임 검색 → 당첨 알림 (구글폼 제출 기한 강조, 승인 시 프로필로 자동 제출)

---

## 7. 개발 환경 주의
- 현재 클라우드 세션 네트워크는 국내 사이트(ppomppu, quasarzone, suto.co.kr, events.kr, jupjup.app, event.danawa.com, clien, ruliweb)를 차단 중. `www.googleapis.com`은 허용됨.
- Phase 4 파서 개발 시 해당 도메인을 환경 Network access에서 허용하거나, Actions에서 HTML을 받아 아티팩트로 저장한 뒤 픽스처로 사용.
- `api.telegram.org`, `api.anthropic.com` 접근 가능 여부도 구현 시작 시 확인.
