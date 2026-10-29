# CLAUDE.md

## Project Overview

giveaway-hunter — 국내 경품·사은품 이벤트를 자동으로 수집하고 응모하는 도구.
1순위 소스는 IT 유튜버(+보겸TV/보겸S) 댓글·구독 이벤트, 2순위는 이벤트 모음 사이트·커뮤니티.
알림은 텔레그램, 실행은 GitHub Actions.

## Source of Truth

- `docs/PLAN.md` — 확정된 결정 사항, 설계, 구현 단계(Phase 0~5). 구현 전에 반드시 읽을 것.

## Rules

- 범위는 국내 이벤트만.
- 자동화 수준: 자동 가능한 것은 완전 자동, **공개 게시(댓글 등)와 개인정보 폼 제출은 텔레그램 승인 후**.
- 유의사항에 매크로 금지가 있거나 로그인·본인인증·캡차가 필요한 응모는 자동화하지 않고 알림만 보낸다.
- 토큰·비밀번호·개인정보는 절대 커밋하지 않는다. GitHub Secrets / `.env`만 사용.
- 레포가 public이므로 상태 DB는 암호화해서 `state` 브랜치에만 저장한다.

## Conventions

- Python 3.12, 소스는 `src/giveaway/`, 설정은 `config/`, 테스트는 `tests/`.
- 수집기는 저장된 HTML/JSON 픽스처 기반 파서 테스트를 함께 작성한다.
- 한국어 커밋 메시지 (`feat:`, `fix:`, `docs:` 접두사).
