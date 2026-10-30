# 초기 설정 (Phase 1)

## 1. 텔레그램 봇
1. 텔레그램에서 **@BotFather** → `/newbot` → 이름/아이디 입력 → **토큰** 받기
2. 만든 봇에게 아무 메시지나 보내기
3. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates` 열기 → `"chat":{"id":숫자}` 의 숫자가 **chat id**

## 2. YouTube API 키
1. https://console.cloud.google.com → 새 프로젝트
2. "API 및 서비스 → 라이브러리"에서 **YouTube Data API v3** 사용 설정
3. "사용자 인증 정보 → 사용자 인증 정보 만들기 → API 키" (Phase 3에서 OAuth 추가 예정)

## 3. GitHub Secrets
레포 → Settings → Secrets and variables → Actions → New repository secret

| 이름 | 값 |
|---|---|
| `YOUTUBE_API_KEY` | 위 2번 키 |
| `TELEGRAM_BOT_TOKEN` | 위 1번 토큰 |
| `TELEGRAM_CHAT_ID` | 위 1번 chat id |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com 에서 발급 (없으면 AI 정리 없이 기본 알림만 감) |
| `STATE_KEY` | 길고 임의의 문자열 (예: 비밀번호 생성기로 40자). 분실하면 저장된 상태를 복구할 수 없음 |

## 4. 실행
Actions 탭 → **collect** → Run workflow. 이후 매일 08시(KST)쯤 자동 실행.
첫 실행은 최근 30일 영상을 훑고(최대 20건 알림), 채널 확정 결과를 텔레그램으로 보냄. 채널이 틀렸으면 `config/channels.yaml`에 `handle`을 적어 수정.

## 5. 댓글 응모 승인 기능 (Phase 3) — YouTube OAuth
댓글/구독/좋아요를 **내 계정으로** 게시하려면 한 번만 로그인 승인이 필요하다.

1. Google Cloud 콘솔 → "API 및 서비스 → OAuth 동의 화면": 사용자 유형 **외부**, 앱 이름 아무거나, 본인 이메일 입력
2. **"앱 게시" 눌러 '프로덕션'으로 전환** (테스트 상태면 refresh token이 7일 뒤 만료됨). "확인되지 않은 앱" 경고가 뜨지만 본인 전용이라 무시해도 됨
3. "사용자 인증 정보 → 사용자 인증 정보 만들기 → OAuth 클라이언트 ID" → 유형 **데스크톱 앱** → Client ID / Secret 복사
4. PC에서 (Python 3.12+):
   ```bash
   git clone https://github.com/neoibv/game_01 && cd game_01 && pip install -e .
   YOUTUBE_CLIENT_ID=... YOUTUBE_CLIENT_SECRET=... giveaway auth
   ```
   브라우저에서 응모에 쓸 Google 계정으로 로그인 → 출력된 토큰 복사
5. GitHub Secrets에 `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` 등록

이후 댓글 이벤트가 잡히면 텔레그램에 **댓글 초안 + [게시] [건너뛰기]** 버튼이 온다.
- 초안을 고치려면 그 메시지에 **답장(reply)** 으로 새 댓글을 보내면 됨
- 버튼을 누르면 `poll` 워크플로(15분마다)가 처리하므로 실제 게시는 최대 15~30분 뒤
- 매크로 금지 문구가 있거나 외부 로그인이 필요한 이벤트는 초안/버튼 없이 알림만 옴

## 6. 알림 형식
- **유튜브:** `<유튜브> 이벤트 확정` 한 메시지에 영상제목/제품/이벤트 기한/링크를 묶어서 보낸다. 응모 링크가 있거나 여러 시청자가 같은 양식으로 댓글을 단 영상만 "확정"이고, 근거가 아직 없는 영상은 72시간 동안 다시 확인한다.
- **사이트 이벤트:** 한 메시지에 1순위(IT·전자기기) → 2순위(아기·출산용품) → 3순위(기프티콘·여행·기타) 순으로 묶는다.
- 예전 형식의 알림 기록을 지우고 새 형식으로 다시 받으려면 Actions → collect → Run workflow에서 **reset_events**를 체크하고 실행한다. (응모 완료/승인 대기 건은 보존됨)

## 7. 유튜브 판정 기준과 보겸TV/보겸S
- **응모 방법은 빠짐없이:** 구독·좋아요·댓글·구글폼 등 필요한 행동을 모두 `응모 방법:`에 순서대로 적는다. 댓글이 하나라도 포함되면 댓글 초안과 [게시] 버튼이 온다(구글폼 등 직접 해야 할 것은 초안 메시지에 링크와 함께 표시).
- **제외되는 것:** 마감일이 지난 이벤트, 외부 서비스 회원가입·상품 구매·앱 설치·통신사 가입 같은 조건이 있는 이벤트(`config/filters.yaml`의 `exclude_signup_required`를 `false`로 바꾸면 `⚠️ 조건:` 표시와 함께 알림).
- **보겸TV/보겸S (응모 방법을 영상 말미에서 말로 안내하는 채널):** `config/channels.yaml`의 `format_in_video: true` 채널은 키워드가 없어도 새 영상을 분석한다.
  - **이벤트인지:** 채널 주인의 고정댓글에 "응모양식", "응모 방법", "당첨이 취소" 같은 문구가 있거나, 다수 시청자 댓글이 같은 양식으로 달려 있으면 이벤트로 본다. 마감일을 모르면 게시 후 14일(`max_age_days`)이 지나면 종료로 본다.
  - **통상 조건:** 구독·좋아요는 [게시] 승인 시 자동 처리하고 알림 설정(종)은 안내만 한다(`usual_methods`/`usual_steps`). 멤버십 가입 여부는 영상마다 달라 "영상 말미에서 확인" 줄로 안내한다.
  - **댓글 양식은 사용자가 알려준다:** 자막은 YouTube가 GitHub 서버 IP를 차단해 받을 수 없고(진단으로 확인), 시청자 댓글만으로는 정확한 양식을 알 수 없다(예: 2줄 이상 + 키워드 2개 양식을 지킨 댓글이 상위 98개 중 2개뿐). 그래서 이벤트가 확정되면 텔레그램으로 "영상 말미를 보고 양식을 답장해 주세요" 메시지가 오고, 답장하면(예: `보겸, 아이폰듀오 두 키워드 포함 2줄 이상`) AI가 해석해 그 양식에 맞는 댓글 초안과 [게시] 버튼을 보낸다. 지난번 양식이 메시지에 표시되며 같으면 `같음`이라고만 답장하면 된다. 초안에는 필수 키워드와 최소 줄 수가 코드로 보장된다.
  - 이 답장은 `poll` 워크플로(15분 간격)가 처리하므로 초안은 답장 후 최대 15~30분 뒤에 온다. poll에도 `ANTHROPIC_API_KEY` Secret이 쓰인다.
