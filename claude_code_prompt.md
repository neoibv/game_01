# Claude Code 프롬프트: City Runner Game — Stage 1

---

## 📌 프로젝트 지시

아래의 research.md와 plan.md를 먼저 정독한 후, plan.md에 정의된 구현 순서(Phase 1 → Phase 4)를 순서대로 완전히 구현해 주세요. 구현 중 설계 결정이 필요한 경우 plan.md의 원칙을 기준으로 판단하세요.

---

## 🎮 게임 개요

**장르**: 사이드스크롤 자동 러너 (스테이지 기반)
**레퍼런스**: Antarctic Adventure / Penguin Adventure (Konami, 1983/1986)
**플랫폼**: 웹 브라우저 (이후 Steam/Electron 확장 예정)
**테마**: 서울 도심을 질주하는 캐릭터 — 싱크홀, 자동차, 바리케이드 등 장애물 회피

---

## 🛠️ 기술 스택

- **Phaser 3** (최신 안정 버전) — 게임 엔진, Arcade Physics 사용
- **Vite** — 번들러 및 개발 서버
- **JavaScript ES6+** — 언어
- **localStorage** — 최고기록 저장

---

## 📂 요구 파일 구조

프로젝트를 다음 구조로 생성하세요:

```
city-runner/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── main.js
│   ├── scenes/
│   │   ├── BootScene.js
│   │   ├── MenuScene.js
│   │   ├── GameScene.js
│   │   ├── UIScene.js
│   │   ├── GameOverScene.js
│   │   └── StageClearScene.js
│   ├── objects/
│   │   ├── Player.js
│   │   ├── obstacles/
│   │   │   ├── Obstacle.js       (기반 클래스)
│   │   │   ├── Sinkhole.js
│   │   │   ├── Car.js
│   │   │   ├── Barrier.js
│   │   │   └── Trashcan.js
│   │   └── ObstaclePool.js
│   └── config/
│       ├── gameConfig.js
│       └── stage1.js
└── assets/
    └── (빈 폴더, MVP는 코드로 도형 생성)
```

---

## ⚙️ 핵심 구현 요구사항

### 1. 게임 설정값 (gameConfig.js)
```js
export const GAME_CONFIG = {
  width: 1280,
  height: 720,
  groundY: 620,
  worldWidth: 40000,
  player: {
    speed: 300,
    jumpVelocity: -550,
    gravity: 800,
    lives: 3,
    invincibleDuration: 500,  // ms
  },
  scroll: {
    baseSpeed: 200,
    maxSpeed: 400,
    speedIncrement: 30,
    incrementInterval: 0.2,  // 월드 진행 비율
  },
  score: {
    distanceMultiplier: 10,
    nearMissBonus: 50,
    lifeBonusPerLife: 500,
  }
};
```

### 2. 플레이어 조작
- `←` `→` `A` `D` — 좌우 이동
- `↑` `W` `Space` — 점프 (지면 위에서만, 더블점프 없음)
- 화면 탭(모바일) — 점프
- 플레이어는 화면 좌측 25% 고정 추적 (카메라 lerp)
- 뒤로 이동 불가 (최소 X 강제)

### 3. 패럴랙스 배경 (TileSprite 사용)
```
하늘:        scrollFactorX: 0   (고정)
먼 빌딩:     scrollFactorX: 0.3
중거리 빌딩:  scrollFactorX: 0.6
가까운 빌딩:  scrollFactorX: 0.8
지면/도로:   scrollFactorX: 1.0
```
MVP에서는 `Graphics` 객체로 색상 사각형/실루엣 생성.

### 4. 장애물 시스템
- 오브젝트 풀링으로 구현 (장애물 생성/삭제 대신 재사용)
- stage1.js 데이터로 x좌표 기반 스폰
- 장애물 종류:
  - `Sinkhole`: 지면에 검은 구멍. 빠지면 즉사
  - `Car`: 지면 이동 장애물, 충돌 시 생명 -1
  - `Barrier`: 공사 바리케이드, 충돌 시 생명 -1
  - `Trashcan`: 낮은 장애물, 충돌 시 생명 -1

### 5. 생명/충돌 시스템
- 기본 생명: 3개
- 충돌 후 0.5초 무적 + 깜빡임 효과
- 생명 0 → GameOverScene 전환
- 싱크홀 낙하 → 즉사 (생명 전체 소진)

### 6. 점수 시스템
- 이동 거리 × 10 = 점수
- localStorage에 최고기록 저장/불러오기
- 스테이지 클리어 시 남은 생명 × 500 보너스

### 7. 스테이지 1 구성 (stage1.js)
- 총 길이: worldWidth 40000px
- 장애물 최소 60개 이상 배치
- 난이도 구간:
  - 0~8000: 튜토리얼 (Barrier, Trashcan 위주)
  - 8000~24000: 본 게임 (Car, Sinkhole 추가)
  - 24000~36000: 심화 (장애물 간격 좁아짐)
  - 36000~40000: 클라이막스 (최고 속도, 복합 장애물)
- 20000 지점: 체크포인트 (HUD에 "CHECKPOINT!" 표시)

### 8. HUD (UIScene)
- 좌상단: ❤️ × 생명 수
- 우상단: SCORE 숫자
- 우상단 아래: DIST (km 단위, 소수점 1자리)
- 체크포인트/클리어 시 화면 중앙 팝업 텍스트

### 9. 씬 전환 흐름
```
BootScene → MenuScene → GameScene + UIScene(병렬) → GameOverScene 또는 StageClearScene → MenuScene
```

### 10. 스케일 설정
```js
scale: {
  mode: Phaser.Scale.FIT,
  autoCenter: Phaser.Scale.CENTER_BOTH,
}
```

---

## 🎨 MVP 아트 (코드로 생성, 외부 이미지 파일 없이)

- **플레이어**: 32×48 파란 직사각형 (상태별 색 변경: 점프=하늘색, hit=빨강)
- **지면**: 회색(#888888) 사각형, 도로 느낌의 노란 중앙선 추가
- **싱크홀**: 검정 사각형 구멍
- **자동차**: 빨강 사각형
- **바리케이드**: 주황 사각형
- **쓰레기통**: 녹색 사각형
- **배경 빌딩**: 회색 계열 사각형 실루엣 다양한 높이로 배치
- **하늘**: #87CEEB 그라디언트

---

## ✅ 완료 기준

다음 항목이 모두 동작해야 합니다:

- [ ] `npm install && npm run dev` 로 브라우저에서 즉시 실행
- [ ] 메뉴 → 게임 → 게임오버/클리어 → 메뉴 씬 전환
- [ ] 좌우 이동 + 점프 정상 동작
- [ ] 패럴랙스 배경 3단계 이상 스크롤
- [ ] 장애물 4종 스폰 및 충돌 처리
- [ ] 생명 3개, 충돌 시 감소, 0 시 게임오버
- [ ] 점수/거리 실시간 HUD 표시
- [ ] 최고기록 localStorage 저장 및 메뉴 표시
- [ ] worldWidth 도달 시 스테이지 클리어
- [ ] `npm run build` 로 dist 폴더 생성 (정적 배포 가능)

---

## 📎 참고 문서

- `research.md` — 레퍼런스 게임 분석, 기술 스택 비교, 장애물 설계
- `plan.md` — 상세 설계, 물리 수치, 씬 구조, 확장성 원칙

---

## ⚠️ 주의사항

1. **외부 이미지 에셋 불필요** — Phaser `Graphics` API로 모든 시각 요소 코드 생성
2. **스테이지 확장성 최우선** — stage1.js 구조가 stage2.js, stage3.js에 그대로 적용될 수 있어야 함
3. **오브젝트 풀링 필수** — 장애물 직접 생성/삭제 금지
4. **Arcade Physics만 사용** — Matter.js, Impact 사용 금지
5. **UIScene 분리 필수** — HUD는 GameScene과 분리된 씬으로 구현
6. 구현 완료 후 **실행 방법, 조작법, 파일 구조를 README.md에 작성**
