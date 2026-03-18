# CLAUDE.md

## Project Overview

City Runner — 서울 도심 배경 의사 3D 전방 시점 러너 게임 (Antarctic Adventure 스타일).
Phaser 3 + Vite + vanilla JavaScript. 외부 에셋 없이 코드로 모든 그래픽/SFX 생성.

## Quick Start

```bash
cd city-runner
npm install
npm run dev       # http://localhost:3000
npm run build     # dist/ 생성
```

## Architecture

- **의사 3D 렌더링**: Arcade Physics 미사용. Graphics API로 매 프레임 도로/장애물/플레이어를 직접 그림
- **충돌 판정**: Z좌표 근접 + X 겹침 기반 커스텀 로직
- **SFX**: Web Audio API로 코드 생성 (외부 사운드 파일 없음)
- **텍스처**: `TextureFactory.js`의 `generateTexture`로 프로시저럴 생성

## Key Files

```
city-runner/
├── src/
│   ├── main.js                    # Phaser 초기화 (1280×720, FIT 스케일)
│   ├── scenes/
│   │   ├── BootScene.js           # 로딩
│   │   ├── MenuScene.js           # 메인 메뉴
│   │   ├── GameScene.js           # 핵심 게임 루프 + 렌더링
│   │   ├── UIScene.js             # HUD (생명/타이머/점수/거리)
│   │   ├── GameOverScene.js       # 게임오버
│   │   └── StageClearScene.js     # 클리어
│   ├── objects/
│   │   ├── Road.js                # 의사 3D 도로 렌더링 엔진
│   │   ├── Player.js              # 플레이어 캐릭터
│   │   ├── ObstacleManager.js     # 장애물/수집물 관리 + 충돌
│   │   └── TextureFactory.js      # 프로시저럴 텍스처 생성
│   └── config/
│       ├── gameConfig.js          # 전역 설정 상수
│       └── stage1.js              # 스테이지 1 데이터 (Z 기반 장애물 배치)
├── vite.config.js
└── package.json
```

## Conventions

- ES6 모듈 (`import`/`export`), `"type": "module"`
- 씬은 `src/scenes/`에, 게임 오브젝트는 `src/objects/`에, 설정은 `src/config/`에 배치
- 스테이지 추가: `src/config/stageN.js` 생성 → `GameScene.js`의 `STAGE_MAP`에 등록
- 모든 그래픽은 코드로 생성 — 외부 이미지 파일 사용하지 않음

## Deployment

- GitHub Pages: `gh-pages` 브랜치에 `dist/` 빌드 결과물 배포
- 배포 URL: https://neoibv.github.io/game_01/
- `dist/`는 `.gitignore`에 포함 — main 브랜치에는 소스만 커밋

## Design Docs

- `plan.md` — 상세 설계 (원근 투영 수학, 클래스 구조, 구현 순서)
- `research.md` — 레퍼런스 분석, 기술 스택 선정 근거
