# 📋 Plan: City Runner — Stage 1 구현 계획 (의사 3D 전방 시점)

---

## 1. 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 장르 | 의사 3D 전방 시점 자동 러너 (스테이지 기반) |
| 레퍼런스 | Antarctic Adventure (Konami, 1983) |
| 시점 | 의사 3D — 캐릭터 뒤에서 전방을 바라보며 도로가 소실점으로 수렴 |
| 플랫폼 | 웹 브라우저 (1차), Steam via Electron (2차) |
| 엔진 | Phaser 3 (Graphics API 기반 커스텀 렌더링) |
| 해상도 | 1280×720 (16:9), FIT 스케일 모드 |
| 테마 | 서울 도심 |
| 목표 | 브라우저에서 즉시 플레이 가능한 Stage 1 완성 |

---

## 2. 기술 스택

```
Phaser 3.x          - 게임 엔진 (씬 관리, 입력, 타이머)
Vite                - 번들러 및 개발 서버
JavaScript (ES6+)   - 언어
localStorage        - 최고기록 저장
Web Audio API       - 코드 생성 SFX (외부 파일 없음)
```

**핵심 결정:**
- **Arcade Physics 미사용** — 의사 3D는 Z좌표 기반이므로 커스텀 충돌 판정 구현
- **Graphics API 매 프레임 렌더링** — 도로, 장애물, 플레이어 모두 코드로 그리기

---

## 3. 씬(Scene) 구조

```
BootScene
  └── 로딩 화면
  └── → MenuScene

MenuScene
  └── 게임 제목, Start 버튼, 최고기록, 조작법
  └── → GameScene

GameScene  ★ 핵심
  └── 의사 3D 도로 렌더링 + 게임 루프
  └── UIScene (병렬 실행, HUD)
  └── → GameOverScene (실패) / StageClearScene (클리어)

GameOverScene
  └── 점수, 진행률, 사유 표시 + Retry/Menu
  └── → GameScene / MenuScene

StageClearScene
  └── 점수 분해 (거리 + 타임보너스 + 생명보너스)
  └── → MenuScene (추후 Stage 2 연결)
```

---

## 4. 의사 3D 렌더링 엔진 (Road.js)

### 4-1. 원근 투영

```js
// 설정값
horizonY      = 화면 높이 × 0.35   // 수평선
playerScreenY = 화면 높이 × 0.82   // 플레이어 고정 Y
roadWidth     = 800                // 가장 가까운 도로 폭 (px)
vanishingX    = 화면 너비 / 2      // 소실점 X

// Z → 화면좌표 변환
scale(z) = 1 / (1 + z × perspectiveFactor)
screenY(z) = horizonY + (playerScreenY - horizonY) × scale(z)
screenX(worldX, z) = vanishingX + (worldX + curveOffset(z)) × scale(z)
```

### 4-2. 도로 렌더링 (매 프레임)

- ~180개 수평 스트립을 horizonY → playerScreenY 까지 그리기
- 각 스트립: Z 깊이에 따라 도로 폭 계산, 중앙에 배치
- 교차 색상 (밝은 회색/어두운 회색) — 절대 Z 기준으로 스크롤 착시
- 중앙 노란 점선, 흰색 가장자리 선도 Z에 따라 스케일
- 도로 커브: 스트립별 중심 X에 사인파 오프셋 적용

### 4-3. 배경 레이어

```
하늘: 그라디언트 (#87CEEB → #FDB97D) — 고정
스카이라인: 수평선 위 회색 빌딩 실루엣 — 고정
안개: Z > fogStart 영역에 하늘색 반투명 오버레이
```

---

## 5. 플레이어(Player) 사양

### 5-1. 조작
| 입력 | 동작 |
|------|------|
| `←` / `A` | 왼쪽 이동 (도로 내 좌우) |
| `→` / `D` | 오른쪽 이동 |
| `↑` / `W` / `Space` | 점프 |
| 모바일 좌측 탭 | 왼쪽 이동 |
| 모바일 우측 탭 | 오른쪽 이동 |
| 모바일 더블탭 | 점프 |

### 5-2. 물리 속성
```js
moveSpeed: 400       // 좌우 이동 속도 (world units/s)
jumpHeight: 120      // 최대 점프 높이 (화면 px)
jumpDuration: 0.5    // 점프 포물선 시간 (초)
halfWidth: 40        // 충돌 판정 반폭 (world X)
```

### 5-3. 위치 모델
- `worldX`: 도로 중심 기준 좌우 오프셋 (-roadHalf ~ +roadHalf)
- `jumpHeight`: 현재 지면 위 높이 (0 = 지면, 사인 곡선 점프)
- 화면 위치: `road.project(worldX, 0)` 로 계산 (Z=0 = 플레이어 깊이)
- 점프 시 화면 Y만 올라가고, 지면에 그림자 표시

### 5-4. 상태
```
running → jumping → running (착지)
    ↓
   hit → (무적 1.5초) → running
    ↓
   dead → GameOver
```

---

## 6. 장애물 시스템

### 6-1. 장애물 클래스

```
ObstacleManager — 전체 장애물/수집물 관리
├── 장애물 (obstacles 배열)
│   ├── sinkhole  — 도로 위 구멍, 즉사
│   ├── car       — 이동 장애물 (좌우 왕복), 생명 -1
│   ├── barrier   — 고정 장애물, 생명 -1
│   └── trashcan  — 고정 장애물, 생명 -1
└── 수집물 (collectibles 배열)
    ├── coin      — 100점
    └── food      — 300점 (떡볶이/붕어빵)
```

### 6-2. Z 기반 위치 시스템

- 모든 장애물은 `worldZ` (절대 스테이지 Z좌표) + `worldX` (도로 내 좌우 오프셋)
- `relativeZ = worldZ - cameraZ` 로 현재 카메라 기준 상대 깊이 계산
- relativeZ > drawDistance → 아직 안 보임
- relativeZ < -threshold → 지나감, 비활성화
- 렌더링: `road.project(worldX, relativeZ)` → 화면 좌표 + 스케일

### 6-3. 충돌 판정 (커스텀)

```js
// 매 프레임 활성 장애물마다:
relZ = obstacle.worldZ - cameraZ

// 1. Z 근접 체크
if (|relZ| > zThreshold) → 충돌 없음

// 2. X 겹침 체크
if (player.xMax < obstacle.xMin || player.xMin > obstacle.xMax) → 충돌 없음

// 3. 점프 회피 체크
if (player.jumpHeight > jumpSafeHeight) → 점프로 회피 성공

// 위 3가지 모두 통과 → 충돌 발생
```

### 6-4. 생명 시스템
- 기본 생명: 3개
- 충돌 후 1.5초 무적 (깜빡임 효과)
- 싱크홀: 즉사 (생명 전체 소진)
- 생명 0 → GameOverScene

---

## 7. 점수 및 진행 시스템

### 7-1. 점수 계산
```
이동 거리 기반 점수 = (cameraZ / totalDistance) × totalDistance × 10 / 100
수집 아이템: 코인 +100, 음식 +300
스테이지 클리어 보너스:
  - 타임 보너스 = 남은 시간(초) × 100
  - 생명 보너스 = 남은 생명 × 500
```

### 7-2. 타이머 시스템
```
stageTimeLimit: 120초 (카운트다운)
체크포인트 도달 시: +15초 보너스
시간 초과: 즉시 게임오버 (생명 관계없이)
남은 시간이 많을수록 높은 타임 보너스 → 빠른 클리어 유도
```

### 7-3. 속도 증가
```js
baseSpeed: 80 Z/s → maxSpeed: 160 Z/s
진행 20% 마다 +12 Z/s 증가
최고 속도 도달 후 유지
```

---

## 8. 스테이지 1 데이터 형식 (stage1.js)

```js
{
  id: 1,
  name: 'STAGE 1 — SEOUL',
  totalDistance: 4000,       // Z 단위
  timeLimit: 120,            // 초
  checkpointZ: 2000,

  obstacles: [
    // z: 절대 Z좌표, x: 도로 중심 기준 정규화 오프셋 (-1.0 ~ 1.0)
    { type: 'barrier',  z: 180,  x: 0.3 },
    { type: 'sinkhole', z: 860,  x: 0.0, width: 0.5 },
    { type: 'car',      z: 960,  x: -0.4, speed: 0.015 },
    // ... 60+ 장애물
  ],

  collectibles: [
    { type: 'coin', z: 130, x: 0.0 },
    { type: 'food', z: 520, x: 0.0 },
    // ... 30+ 수집물
  ],

  curves: [
    // 도로 커브 구간
    { zStart: 600, zEnd: 900, direction: 1, intensity: 0.2 },
    // ...
  ]
}
```

---

## 9. HUD (UIScene)

UIScene은 GameScene과 병렬 실행되는 별도 씬.

```
┌─────────────────────────────────┐
│ ❤❤❤    TIME: 1:23    SCORE: 4500│
│                       DIST: 1.2km│
└─────────────────────────────────┘
```

- 좌상단: ❤ × 생명 수
- 중앙 상단: TIME 카운트다운 (15초 이하 빨간색 점멸)
- 우상단: SCORE, DIST(km)
- 체크포인트: 화면 중앙 "CHECKPOINT! +15s" 팝업
- 클리어: 화면 중앙 "STAGE CLEAR!!" 팝업

---

## 10. 시각 요소 (코드 생성 MVP)

| 요소 | 렌더링 방식 |
|------|-----------|
| 하늘 | 그라디언트 (#87CEEB → #FDB97D) |
| 스카이라인 | 수평선 위 회색 빌딩 실루엣 (다양한 높이) |
| 도로 | 회색 사다리꼴 스트립, 노란 중앙선, 흰 가장자리 |
| 플레이어 | 파란 사각형 (32×48), 점프 시 하늘색, 피격 시 빨강, 눈 표시 |
| 싱크홀 | 도로 위 검정 사각형 (폭 가변, Z에 따라 스케일) |
| 자동차 | 빨강 사각형 (80×44 기준, 스케일 적용) |
| 바리케이드 | 주황 사각형 (52×56 기준) |
| 쓰레기통 | 녹색 사각형 (36×44 기준) |
| 코인 | 노란 원 + 빛반사, 위아래 부유 애니메이션 |
| 음식 | 주황 원 + 빛반사, 부유 애니메이션 |
| 그림자 | 장애물/플레이어 아래 검정 반투명 타원 |
| 안개 | 먼 거리에 하늘색 반투명 오버레이 |

---

## 11. 단계별 구현 순서

```
Phase 1: 의사 3D 렌더링 엔진
  ✅ gameConfig.js 업데이트 (perspective, timer, collision 설정)
  ✅ Road.js 생성 (도로 스트립 렌더링, 원근 투영, 커브)
  ✅ GameScene.js 재작성 (하늘, 스카이라인, Road 렌더링)

Phase 2: 플레이어
  ✅ Player.js 재작성 (worldX 좌우, 점프 포물선, 화면 하단 고정)
  ✅ 입력 바인딩 (키보드 + 모바일)
  ✅ 플레이어 렌더링 (본체 + 눈 + 그림자)

Phase 3: 장애물 시스템
  ✅ ObstacleManager.js (Z 기반 스폰/디스폰, 렌더링, 충돌 판정)
  ✅ stage1.js 재작성 (Z 기반 60+ 장애물, 30+ 수집물, 커브 데이터)
  ✅ 커스텀 충돌 판정 (Z 근접 + X 겹침 + 점프 회피)
  ✅ 생명 시스템 (3개, 무적, 싱크홀 즉사)

Phase 4: 수집물 + 타이머 + 점수
  ✅ 수집 아이템 (코인/음식, 부유 애니메이션)
  ✅ 타이머 카운트다운 + 체크포인트 보너스
  ✅ 점수 계산 (거리 + 수집물 + 타임보너스 + 생명보너스)
  ✅ localStorage 최고기록

Phase 5: UI + 씬 전환 + 폴리싱
  ✅ UIScene 업데이트 (타이머 HUD, 체크포인트 팝업)
  ✅ GameOverScene (사유 표시: 생명/싱크홀/시간초과)
  ✅ StageClearScene (타임보너스 + 생명보너스 분해 표시)
  ✅ Web Audio SFX (점프, 피격, 코인)
  ✅ 속도 증가 곡선
```

---

## 12. 파일 구조

```
city-runner/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── main.js                    # Phaser 초기화 (물리 엔진 미사용)
│   ├── scenes/
│   │   ├── BootScene.js           # 로딩 화면
│   │   ├── MenuScene.js           # 메인 메뉴
│   │   ├── GameScene.js           # ★ 핵심 게임 루프 + 렌더링
│   │   ├── UIScene.js             # HUD (생명/타이머/점수/거리)
│   │   ├── GameOverScene.js       # 게임오버 (사유별 메시지)
│   │   └── StageClearScene.js     # 클리어 (점수 분해)
│   ├── objects/
│   │   ├── Road.js                # ★ 의사 3D 도로 렌더링 엔진
│   │   ├── Player.js              # 플레이어 (worldX + 점프)
│   │   └── ObstacleManager.js     # 장애물/수집물 관리 + 충돌 판정
│   └── config/
│       ├── gameConfig.js          # 전역 설정 (perspective/timer/score/collision)
│       └── stage1.js              # 스테이지 1 데이터 (Z 기반)
└── assets/                        # (빈 폴더, MVP는 코드 생성)
```

---

## 13. 확장성 설계 원칙

- **스테이지 추가**: `stage2.js` 생성 + `GameScene`의 `STAGE_MAP`에 등록
- **장애물 추가**: `ObstacleManager`의 SIZES/COLORS에 새 타입 추가
- **수집물 추가**: `COLLECTIBLE_COLORS`에 새 타입 추가
- **캐릭터 교체**: `Player.js`의 `render()` 메서드 수정
- **Steam 전환**: Phaser 빌드 → Electron 래핑 → `electron-builder` 패키징

---

## 14. 검증 체크리스트

- [ ] `npm install && npm run dev` 로 브라우저에서 즉시 실행
- [ ] 의사 3D 도로가 소실점으로 수렴하며 스크롤됨
- [ ] 플레이어 좌우 이동 + 점프 정상 동작
- [ ] 장애물이 먼 곳(작게) → 가까이(크게) 렌더링
- [ ] 싱크홀 즉사, 기타 장애물 생명 -1
- [ ] 수집 아이템 획득 시 점수 증가
- [ ] 타이머 카운트다운 + 시간초과 = 게임오버
- [ ] 체크포인트 도달 시 +15초 보너스
- [ ] 스테이지 클리어 시 타임보너스 + 생명보너스
- [ ] 도로 커브 구간 시각 효과
- [ ] HUD (생명, 타이머, 점수, 거리) 실시간 표시
- [ ] 최고기록 localStorage 저장 및 메뉴 표시
- [ ] `npm run build` 로 dist 폴더 정상 생성
