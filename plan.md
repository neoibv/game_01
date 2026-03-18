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

### 4-3. 도로변 건물 렌더링 (Road.js)

도로 양쪽에 건물을 Z 깊이에 따라 원근 투영하여 도시 주행감 극대화.

```
렌더링 방식:
- 도로 스트립 렌더링 시 양쪽 인도 바깥에 건물 그리기
- 건물은 Z 기반 의사 랜덤(LCG)으로 결정 (스크롤해도 일관성 유지)
- 각 스트립에서: 인도 끝 X좌표 ~ 화면 끝까지 건물 외벽 색상 채우기
- 건물 경계선(수직선)을 일정 Z 간격으로 그려 개별 건물 구분
- 층수 표현: 수평선 위로 건물 상단이 돌출되는 높이를 Z/건물별로 다르게
- 창문: 건물 면에 밝은 노란 점을 규칙적으로 배치

시각 구성:
┌──────────────────────────────────────────┐
│     하늘 그라디언트                         │
│  ┌─┐┌──┐┌─┐   스카이라인   ┌──┐┌─┐┌──┐   │
│  │ ││  ││ │ ←수평선 위→   │  ││ ││  │   │
├──┤건││건││건├──도로──────┤건││건││건├──┤
│  │물││물││물│  (스트립)    │물││물││물│  │
│  │  ││  ││  │             │  ││  ││  │  │
│  └─┘└──┘└─┘  플레이어     └──┘└─┘└──┘  │
└──────────────────────────────────────────┘

건물 파라미터 (gameConfig.js):
  buildingSegmentLength: 30    // Z 단위당 한 건물
  buildingMinHeight: 40        // 최소 건물 높이 (px, 가장 가까운 기준)
  buildingMaxHeight: 150       // 최대 건물 높이
  buildingColors: [0x556677, 0x667788, 0x445566, 0x5A6A7A, 0x4A5A6A]
  windowColor: 0xFFFF88        // 창문 색상
  windowSpacingX: 12           // 창문 가로 간격 (px)
  windowSpacingY: 14           // 창문 세로 간격 (px)
```

### 4-4. 배경 레이어

```
하늘: 그라디언트 (#87CEEB → #FDB97D) — 고정
스카이라인: 수평선 위 회색 빌딩 실루엣 — 고정 (원거리 배경)
도로변 건물: 도로 양쪽 — Z 스크롤과 함께 이동 (근거리 입체감)
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
moveSpeed: 550       // 좌우 이동 속도 (world units/s)
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
│   ├── sinkhole       — 도로 위 구멍, 즉사
│   ├── car            — 반대편 차량 (전면 뷰, 좌우 왕복), 생명 -1
│   ├── zombie         — 서 있는 좀비 (팔 벌림), 생명 -1
│   └── zombie_crawler — 기어가는 좀비, 생명 -1
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

### 7-3. 속도 증가 (시간 기반 연속 가속)
```js
baseSpeed: 140 Z/s → maxSpeed: 350 Z/s
방식: 경과 시간(elapsed)에 비례하여 연속 가속
공식: scrollSpeed = baseSpeed + (maxSpeed - baseSpeed) × min(1, elapsed / rampDuration)
rampDuration: 90초 (90초에 걸쳐 최고 속도까지 선형 증가)

효과:
- 게임 시작 직후: 140 Z/s (여유 있음)
- 30초 경과: ~210 Z/s
- 60초 경과: ~280 Z/s
- 90초 이후: 350 Z/s (최고 속도, 극한 난이도)
- 오래 살수록 더 빨라져서 자연스럽게 난이도 상승
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
    { type: 'zombie',         z: 180,  x: 0.3 },
    { type: 'zombie_crawler', z: 280,  x: -0.2 },
    { type: 'sinkhole',       z: 860,  x: 0.0, width: 0.5 },
    { type: 'car',            z: 960,  x: -0.4, speed: 0.015 },
    // ... 50+ 장애물
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

## 10. 시각 요소 (향상된 프로시저럴 그래픽)

### 10-1. 렌더링 방식: generateTexture 기반

모든 게임 오브젝트를 `TextureFactory.js`에서 Phaser Graphics API로 상세 그린 후 `generateTexture()`로 텍스처 베이킹.
매 프레임 fillRect 호출 대신 사전 생성된 Image를 `setScale(proj.scale)`로 의사3D 스케일링.

### 10-2. 시각 요소 목록

| 요소 | 렌더링 방식 |
|------|-----------|
| 하늘 | 그라디언트 (#87CEEB → #FDB97D) + 태양 (발광 원) + 구름 (반투명 타원 5개) |
| 스카이라인 | 회색 빌딩 실루엣 + 안테나/첨탑 + 빨간 항공등 + 남산타워 실루엣 |
| 도로 | 회색 스트립 + 이중 노란 중앙선 + 흰 가장자리 + 인도 + 횡단보도 |
| 플레이어 | 달리는 남자 뒷모습 (48×64, 후방 시점 — 아래 10-4 상세) |
| 싱크홀 | 타원형 균열 텍스처 (방사형 크랙 + 깊이 셰이딩) |
| 반대편 차량 | 전면 뷰 (100×52, 전방 시점 전용 그래픽 — 아래 10-4 상세) |
| 도로변 건물 | Road.js에서 도로 스트립과 함께 원근 렌더링 (스크롤 연동) |
| 좀비 (서기) | 녹색 피부, 팔 벌림, 빨간 눈, 찢어진 옷, 피 묻음 (48×56) |
| 좀비 (기기) | 바닥에 엎드려 기어가는 좀비, 손톱/발톱 (44×36) |
| 코인 | 4프레임 회전 애니메이션 (원→타원→선→타원) + ₩ 기호 + 빛반사 |
| 음식 | 떡볶이 형상 (떡 막대 + 빨간 소스 + 파 장식) |
| 그림자 | 장애물/플레이어 아래 검정 반투명 타원 |
| 안개 | 먼 거리에 하늘색 반투명 오버레이 |
| 파티클 | 코인 수집 시 노란 스파크, 달리기 먼지 트레일, 피격 빨간 플래시 |

### 10-4. 플레이어 그래픽 설계 — 달리는 남자 뒷모습 (48×64px)

**핵심 원칙**: 의사 3D 전방 시점이므로 플레이어를 **뒤에서** 바라봄.
뒷머리, 어깨, 등, 팔/다리 흔들림이 보여야 함. 눈/얼굴은 안 보임.

```
텍스처 구성 (48×64px, 후방 시점):
┌────────── 48px ──────────┐
│      ┌── 머리 ──┐        │  ← 뒷머리: 어두운 갈색, 둥근 사각형
│      │ (뒷모습)  │        │     머리카락 질감 (상단 어둡게)
│      └────┬─────┘        │
│     ┌─────┴─────┐        │  ← 목: 살색 짧은 직사각형
│  ┌──┤  어깨/등   ├──┐     │  ← 상체: 파란 티셔츠
│  │팔│  (티셔츠)  │팔│     │     등 중앙에 주름선
│  │  │           │  │     │     팔: run_1은 좌팔 앞+우팔 뒤
│  └──┤           ├──┘     │          run_2는 반대
│     └─────┬─────┘        │
│     ┌─────┴─────┐        │  ← 하체: 검정 바지
│  ┌──┤  허리/엉덩이├──┐    │     다리: run_1은 좌다리 앞+우다리 뒤
│  │다│           │다│     │          run_2는 반대
│  │리│           │리│     │
│  └─┬┘           └┬─┘     │
│  ┌─┴─┐         ┌─┴─┐     │  ← 신발: 흰색 운동화
│  │신발│         │신발│     │
│  └───┘         └───┘     │
└──────────────────────────┘

상태별 텍스처:
- player_run_1: 좌팔 앞 + 우다리 앞 (달리기 프레임 1)
- player_run_2: 우팔 앞 + 좌다리 앞 (달리기 프레임 2)
- player_jump: 팔 위로 들어올림, 다리 모음 (점프)
- player_hit: 전체 빨간색 플래시

색상 팔레트:
- 머리카락: 0x3B2517 (어두운 갈색)
- 피부(목): 0xE8B87A (살색)
- 티셔츠: 0x2266CC (파란색)
- 바지: 0x222233 (어두운 남색)
- 신발: 0xEEEEEE (흰색)
```

#### 반대편 차량 — 전면 뷰 유지 (100×52px)
기존 Phase 8 설계 유지 (접지면 바퀴, 헤드라이트/그릴 전면 뷰)

### 10-5. 그래픽 방법론 결정

6가지 무료 그래픽 방법을 평가한 결과, **향상된 프로시저럴 + generateTexture + Phaser 파티클** 채택:
- 외부 에셋/도구 불필요, 코드베이스 내 완결
- 의사3D `proj.scale` 스케일링과 완벽 호환
- `generateTexture()`로 매 프레임 draw 제거 → 성능 향상
- 무료 에셋 사이트의 도시/차량 스프라이트는 대부분 탑다운/횡스크롤 시점으로 부적합

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

Phase 6: 그래픽 업그레이드
  ✅ TextureFactory.js 생성 (모든 오브젝트 텍스처 프로시저럴 베이킹)
  ✅ BootScene에서 TextureFactory 호출
  ✅ Player.js: Graphics → Image 렌더링 전환 (2프레임 달리기 애니메이션)
  ✅ ObstacleManager.js: 공유 Graphics → 개별 Image 전환
  ✅ Road.js: 인도, 횡단보도, 이중 중앙선 추가
  ✅ GameScene.js: 남산타워, 구름, 태양, 안테나 추가
  ✅ 파티클 시스템 (코인 스파크, 먼지 트레일, 피격 플래시)
  ✅ gameConfig.js: visual 설정 섹션 추가

Phase 7: 캐릭터/장애물 리디자인 + 속도 개선
  ✅ 플레이어: 사람 캐릭터 → 자동차 뒷모습 (64×40px) 변경
  ✅ 장애물: barrier/trashcan → zombie/zombie_crawler 변경
  ✅ 장애물: car → oncoming_car (전면 뷰) 변경
  ✅ 속도: baseSpeed 80→140, maxSpeed 160→280, increment 12→22
  ✅ 좌우 이동속도: 400→550 (속도 증가에 맞춘 조작성 보정)
  ✅ stage1.js: 장애물 타입명 전체 업데이트

Phase 8: 차량 시점 교정 + 도로변 건물 + 플레이어 크기 증가
  □ TextureFactory.js: 플레이어 자동차 크기 64×40 → 96×60 확대
  □ TextureFactory.js: 플레이어/반대편 차량 바퀴를 후방/전방 시점에 맞게 교정
    - 원형/타원 바퀴 → 넓고 납작한 직사각형 (접지면 뷰)
    - 배기구: 원형 → 가로 타원/직사각형 (후면 뷰)
  □ TextureFactory.js: 반대편 차량 크기 80×44 → 100×52 확대
  □ Player.js: drawW/drawH를 96×60으로 업데이트
  □ ObstacleManager.js: car 크기를 100×52로 업데이트
  □ Road.js: 도로변 건물 렌더링 시스템 추가
    - 도로 스트립 렌더링 시 인도 바깥에 건물 외벽 채우기
    - Z 기반 의사 랜덤(LCG)으로 건물 색상/높이 결정
    - 건물 경계선(수직선)으로 개별 건물 구분
    - 창문 (밝은 노란 점) 규칙적 배치
  ✅ gameConfig.js: building 관련 설정값 추가

Phase 9: 플레이어 남자 캐릭터 전환 + 시간 기반 가속
  □ TextureFactory.js: 자동차 뒷모습 텍스처 → 달리는 남자 뒷모습 (48×64px)
    - 4개 텍스처: run_1, run_2 (달리기 2프레임), jump, hit
    - 뒷머리/어깨/등/팔다리 흔들림, 얼굴 안 보임
  □ Player.js: drawW/drawH → 48×64, 달리기 프레임 애니메이션 복원
  □ gameConfig.js: 속도 시스템 변경
    - scroll.speedMode: 'time' (시간 기반)
    - scroll.rampDuration: 90 (90초에 걸쳐 최고 속도까지)
    - scroll.maxSpeed: 350
  □ GameScene.js: 속도 계산 로직 변경
    - 기존: progress(거리) 기반 계단식 증가
    - 변경: elapsed(경과 시간) 기반 선형 증가
    - scrollSpeed = baseSpeed + (maxSpeed - baseSpeed) × min(1, elapsed / rampDuration)
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
│   │   ├── Player.js              # 플레이어 (Image 기반 렌더링 + 달리기 애니메이션)
│   │   ├── ObstacleManager.js     # 장애물/수집물 관리 (Image 기반) + 충돌 판정
│   │   └── TextureFactory.js      # ★ 프로시저럴 텍스처 생성 팩토리
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
