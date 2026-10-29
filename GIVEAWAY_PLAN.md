# 경품·사은품 이벤트 자동 수집/응모 시스템 — 실행 계획

> 작성일: 2026-10-29 · 범위: **국내 이벤트만** · 1차 우선순위: **IT 유튜버 댓글/구독 이벤트**
>
> 이 문서는 다음 모델이 그대로 따라 구현할 수 있도록 작성한 계획서다. 아직 기존 게임 코드는 지우지 않았다(Phase 0에서 수행).

---

## 1. 목표 정의

| 단계 | 내용 | 자동화 수준 |
|---|---|---|
| 수집 | 이벤트 모음 사이트·커뮤니티·유튜브에서 새 이벤트를 주기적으로 찾음 | 완전 자동 |
| 정규화 | 경품, 응모 방법, 마감일, 발표일, 조건을 구조화 | 완전 자동 (규칙 + LLM 추출) |
| 필터/랭킹 | 관심 분야(IT), 경쟁률 추정, 응모 난이도, 마감 임박 순 | 완전 자동 |
| 알림 | 새 이벤트/마감 임박을 텔레그램(또는 디스코드)으로 푸시 | 완전 자동 |
| 응모 | 댓글 초안 생성 → **사용자 승인 1클릭** → 게시/제출 | 반자동 (기본값) |
| 사후관리 | 응모 이력, 당첨 발표 확인, 당첨 시 알림 | 자동 |

### "완전 자동 응모"를 기본값으로 하지 않는 이유 (중요)
- **YouTube 스팸 정책**: 자동화된 반복·일반적 댓글은 스팸으로 분류돼 숨김 처리되거나 계정 제재 위험. 같은 문구 반복은 바로 걸린다.
- **이벤트 유의사항**: 국내 기업 이벤트 대부분이 "매크로/부정 참여 시 당첨 취소"를 명시. 성의 없는 댓글은 추첨 대상에서 제외하는 유튜버도 많다.
- **개인정보 입력형 폼**(이름/전화/주소)은 사이트마다 구조가 다르고 캡차·본인인증이 붙는다.
- 따라서 **기본은 "AI가 영상 내용 기반 댓글 초안 작성 → 사용자가 텔레그램 버튼으로 승인 → API로 게시"**. 단순 클릭형 이벤트만 설정으로 자동 응모를 켤 수 있게 옵션화한다.

---

## 2. 조사 결과: 정보 소스

### 2-1. 이벤트 모음 사이트 / 앱 (국내)
| 소스 | 성격 | 주요 정보 | 수집 방식(예정) |
|---|---|---|---|
| 슈퍼투데이 (suto.co.kr, 앱) | 국내 최대급 이벤트·공모전 모음. 하루 100~200건 신규 | 이벤트명, 주최, 경품, 응모기간, 발표일, 응모 링크, 응모 유형(SNS/댓글/퀴즈 등) | 웹 목록 페이지 스크래핑 |
| 이벤트 코리아 (events.kr) | 카톡·인스타 이벤트, 기업 공모전, 체험단 통합 | 위와 유사 + 카테고리 | 스크래핑 |
| 줍줍 (jupjup.app) | "클릭 몇 번이면 끝나는" 무료 응모만 큐레이션 (~300건) | 간단 응모형 위주 → **자동 응모 후보군** | 스크래핑 |
| 이벤트유 (eventu.co.kr) | 이벤트 모음 + 앱테크 | 이벤트 목록 | 스크래핑 (2순위) |
| 다나와 이벤트 (event.danawa.com) | IT/가전 브랜드 이벤트·체험단 | 브랜드, 경품, 기간 | 스크래핑 (IT 관련도 높음) |
| 씽유 (thinkyou.co.kr/eventThink) | 공모전·이벤트 | 기간, 주최 | 스크래핑 (2순위) |

### 2-2. 커뮤니티 이벤트 게시판
| 소스 | 특징 |
|---|---|
| 퀘이사존 이벤트 게시판 (`quasarzone.com/bbs/qe_event`) | **IT/PC 하드웨어 경품 중심**(GPU, 메인보드 등). 글마다 응모기간·당첨방식·인원·필요 포인트가 정형화돼 있어 파싱 쉬움. 응모는 회원 포인트 차감 방식 |
| 뽐뿌 이벤트 게시판 (`ppomppu.co.kr/zboard/zboard.php?id=event`) | 사용자들이 각종 기업 이벤트를 공유. 제목에 [마감일]·경품이 들어가는 경우 많음 |
| 클리앙 / 루리웹 / 디시 이벤트 관련 게시판 | 3순위. 필요 시 추가 |

### 2-3. 유튜브 (1차 핵심)
- 이벤트가 노출되는 위치: **① 영상 설명란, ② 고정 댓글(채널 주인 작성), ③ 커뮤니티 탭 게시물, ④ 영상 제목/썸네일 ("증정", "이벤트")**.
- 흔한 응모 방식: 구독 + 좋아요 + 댓글(질문에 답하기, 특정 키워드 포함), 커뮤니티 게시물 댓글, 구글폼 제출.
- 당첨 발표: 커뮤니티 게시물 또는 고정 댓글로 `@핸들` 공지 → 구글폼으로 연락처 수집 (기한 내 미제출 시 취소). → **당첨 발표 모니터링 + 내 핸들 검색**이 필요.
- 추첨 도구로 댓글 추첨기(유니피커, pickja 등)를 쓰는 경우가 많고, 중복 댓글 제거·키워드 조건·구독 여부 필터를 사용함 → **중복 댓글 금지, 키워드 조건 준수**가 중요.

#### IT 유튜버 후보 목록 (채널 ID는 구현 시 API로 확인·확정)
잇섭(ITSub), 언더케이지, 테크몽, 주연 ZUYONI, 디에디트, 가전주부, 뻘짓연구소, 1분미만, UNDERkg 계열, 기타 PC 하드웨어 채널.
→ `config/channels.yaml`로 관리. 사용자가 추가/삭제 가능하게.

---

## 3. 기술 설계

### 3-1. 스택
- **Python 3.12** (스크래핑·스케줄링 생태계가 가장 좋음)
- `httpx` + `selectolax`(또는 BeautifulSoup) — 정적 페이지
- `playwright` — JS 렌더링 필요한 사이트, 커뮤니티 탭
- **YouTube Data API v3** — 업로드 목록/설명/댓글 (커뮤니티 탭은 공식 API 없음 → Playwright로 보조)
- **SQLite** (`data/giveaways.db`) — 이벤트·응모 이력
- **Claude API (Haiku 계열)** — 설명란/게시글에서 구조화 정보 추출 + 댓글 초안 생성
- **텔레그램 봇** — 알림 + 인라인 버튼 승인(응모/건너뛰기)
- 스케줄러: **GitHub Actions cron** (기본) 또는 사용자 PC/NAS의 cron

### 3-2. 디렉터리 구조
```
giveaway-hunter/
├── pyproject.toml
├── config/
│   ├── channels.yaml        # 감시할 유튜브 채널
│   ├── sources.yaml         # 사이트/커뮤니티 소스 on/off, 주기
│   └── filters.yaml         # 관심 키워드, 제외 키워드, 최소 경품가치
├── src/giveaway/
│   ├── models.py            # Event, Entry dataclass
│   ├── db.py                # SQLite 스키마/쿼리
│   ├── collectors/
│   │   ├── base.py          # Collector 인터페이스: fetch() -> list[RawItem]
│   │   ├── youtube.py       # 업로드/설명란/고정댓글
│   │   ├── youtube_community.py  # 커뮤니티 탭 (Playwright)
│   │   ├── suto.py, eventskr.py, jupjup.py, danawa.py
│   │   └── quasarzone.py, ppomppu.py
│   ├── detect.py            # 키워드 1차 필터 (이벤트/증정/추첨/댓글/구독/당첨/경품/기프티콘/선물)
│   ├── extract.py           # LLM으로 구조화 (응모방법, 마감, 경품, 조건, 발표방식)
│   ├── rank.py              # 점수화
│   ├── notify/telegram.py   # 알림 + 승인 버튼
│   ├── enter/
│   │   ├── youtube_comment.py  # OAuth, commentThreads.insert (승인 후)
│   │   └── simple_form.py      # 단순 클릭형만 (옵트인)
│   ├── winners.py           # 당첨 발표 감시(내 핸들/닉네임 검색)
│   └── cli.py               # `giveaway collect | notify | enter | winners`
├── tests/                   # 수집기별 HTML/JSON 픽스처 기반 파서 테스트
└── .github/workflows/collect.yml
```

### 3-3. 데이터 모델 (요약)
```
events(id, source, source_url, title, host, prize, prize_value_est,
       entry_method[comment|subscribe|form|quiz|sns_share|click|points],
       entry_requirements(json), start_at, deadline, announce_at, announce_where,
       category, score, raw_text, first_seen_at, status[new|notified|entered|skipped|expired])
entries(id, event_id, entered_at, method, payload(댓글 내용 등), result[pending|won|lost], note)
```
- 중복 제거 키: `source_url` 정규화 + (유튜브는 videoId/postId).

### 3-4. 유튜브 수집 로직 (쿼터 계산 포함)
1. `channels.list`로 각 채널의 uploads 플레이리스트 ID 1회 캐시.
2. 2~3시간마다 `playlistItems.list`(1 unit/채널) → 신규 videoId.
3. `videos.list`(50개당 1 unit)로 제목/설명 가져와 키워드 1차 필터.
4. 후보 영상만 `commentThreads.list order=relevance`(1 unit)로 **채널 주인이 쓴 고정 댓글** 확인.
5. 후보 텍스트 → LLM 추출 → 이벤트 확정 시 DB 저장 + 알림.
6. 커뮤니티 탭은 하루 2회 Playwright로 최근 게시물 텍스트만 읽음.
- 30채널 × 12회/일 ≈ 400~800 unit/일 → 기본 쿼터 10,000 내 여유.
- 댓글 게시(`commentThreads.insert`)는 50 unit, OAuth 필요.

### 3-5. 댓글 초안 생성 규칙
- 영상 내용(제목/설명/자막 일부)과 이벤트 질문을 반영한 **매번 다른 자연스러운 댓글**.
- 요구 키워드/해시태그가 있으면 반드시 포함. 이벤트당 1회만 응모(중복 금지).
- 승인 전까지 게시하지 않음. 텔레그램에서 [게시] [수정] [건너뛰기].

### 3-6. 점수화(rank) 기준
- IT 관련성(채널/키워드), 경품 추정 가치, 응모 난이도(클릭 < 댓글 < 폼 < 창작), 마감까지 남은 시간, 추정 경쟁률(조회수·댓글 수 대비 당첨 인원).

---

## 4. 구현 순서 (마일스톤)

### Phase 0 — 레포 정리
- `city-runner/`, `plan.md`, `research.md`, `claude_code_prompt.md` 삭제.
- `CLAUDE.md`를 새 프로젝트 기준으로 재작성, `.gitignore`에 `data/*.db`, `.env`, `secrets/` 추가.
- 기존 GitHub Pages(`gh-pages` 브랜치)는 사용자에게 유지 여부 확인 후 처리.
- 이 계획서를 `docs/PLAN.md`로 이동.

### Phase 1 — 유튜브 IT 채널 감시 + 알림 (MVP)
- channels.yaml, YouTube collector, 키워드 필터, SQLite, 텔레그램 알림.
- 완료 기준: 실제 채널에서 지난 30일 영상 중 이벤트 영상을 찾아 알림이 온다.

### Phase 2 — LLM 구조화 + 랭킹
- extract.py, rank.py, 마감 임박 리마인더(D-1).

### Phase 3 — 반자동 응모 (유튜브 댓글)
- OAuth 설정, 댓글 초안 → 텔레그램 승인 → 게시, entries 기록.

### Phase 4 — 이벤트 모음 사이트/커뮤니티 수집기
- 순서: 퀘이사존(IT, 정형화) → 다나와 이벤트 → 슈퍼투데이 → 줍줍 → 이벤트코리아 → 뽐뿌.
- 각 수집기마다 저장한 HTML 픽스처로 파서 테스트 작성. robots.txt 준수, 요청 간격 ≥ 2초.

### Phase 5 — 당첨 발표 감시
- 응모한 이벤트의 발표 시점에 커뮤니티 게시물/고정 댓글에서 내 핸들 검색 → 당첨 알림(구글폼 기한 강조).

### Phase 6 — (옵션) 단순 클릭형 자동 응모
- 줍줍 등 "클릭만" 이벤트에 한해, 유의사항에 매크로 금지가 없을 때만, 사용자 옵트인으로.

---

## 5. 실행 환경 / 비밀값
- `YOUTUBE_API_KEY` (수집), `YOUTUBE_OAUTH_*` (댓글 게시), `ANTHROPIC_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` → GitHub Actions Secrets / 로컬 `.env`.
- **주의**: 현재 이 클라우드 세션 네트워크는 국내 사이트(ppomppu, quasarzone, suto.co.kr, events.kr, jupjup.app, event.danawa.com 등) 접근이 차단돼 있다. `www.googleapis.com`은 접근 가능. 구현 세션에서 스크래퍼를 실제로 테스트하려면 환경 설정의 Network access에서 해당 도메인을 허용해야 한다.
- GitHub Actions 러너는 해외 IP라 일부 국내 사이트가 막을 수 있음 → 막히면 사용자 PC/NAS에서 cron 실행으로 전환.

---

## 6. 사용자에게 확인할 것 (구현 시작 전)
1. 알림 채널: 텔레그램 / 디스코드 / 카카오톡(나에게 보내기) 중?
2. 실행 위치: GitHub Actions / 개인 PC / NAS?
3. 감시할 유튜버 목록 확정 (위 후보 + 추가).
4. 응모 자동화 수준: 승인 후 게시(권장) / 단순 클릭형만 완전 자동 허용?
5. 기존 게임 GitHub Pages 배포 유지 여부.
