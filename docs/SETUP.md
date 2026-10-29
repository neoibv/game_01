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
Actions 탭 → **collect** → Run workflow. 이후 3시간마다 자동 실행.
첫 실행은 최근 30일 영상을 훑고(최대 20건 알림), 채널 확정 결과를 텔레그램으로 보냄. 채널이 틀렸으면 `config/channels.yaml`에 `handle`을 적어 수정.
