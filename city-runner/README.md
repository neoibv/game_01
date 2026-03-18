# City Runner

서울 도심을 질주하는 의사 3D 전방 시점 러너 게임.
Antarctic Adventure(1983) 스타일의 원근감 있는 도로 위에서 싱크홀, 자동차, 바리케이드를 피하고 아이템을 수집하며 스테이지를 클리어하세요.

## 실행 방법

```bash
cd city-runner
npm install
npm run dev       # 개발 서버 (http://localhost:3000)
npm run build     # 프로덕션 빌드 → dist/
npm run preview   # 빌드 결과 미리보기
```

## 조작법

| 키 | 동작 |
|---|---|
| `←` / `A` | 왼쪽 이동 |
| `→` / `D` | 오른쪽 이동 |
| `↑` / `W` / `Space` | 점프 |
| 모바일 좌측 탭 | 왼쪽 이동 |
| 모바일 우측 탭 | 오른쪽 이동 |
| 모바일 더블탭 | 점프 |

## 게임 규칙

- 생명 **3개**로 시작
- 자동차/바리케이드/쓰레기통 충돌 시 생명 -1 (1.5초 무적)
- **싱크홀**에 빠지면 즉사
- **점프**로 모든 장애물 회피 가능
- **코인** 수집 +100점, **음식** 수집 +300점
- 제한 시간 **120초** 내에 목표 거리 도달 → 스테이지 클리어
- 체크포인트(50% 지점) 도달 시 **+15초** 보너스
- 클리어 시: 남은 시간 × 100 + 남은 생명 × 500 보너스
- 최고기록 `localStorage` 자동 저장

## 스테이지 1 구성 (서울)

| 구간 | Z 범위 | 특징 |
|---|---|---|
| 튜토리얼 | 0 ~ 800 | 바리케이드, 쓰레기통만 |
| 본 게임 | 800 ~ 2,400 | 자동차, 싱크홀 추가 |
| 심화 | 2,400 ~ 3,600 | 장애물 간격 좁아짐 |
| 클라이막스 | 3,600 ~ 4,000 | 최고 속도, 복합 장애물 |

체크포인트: **Z 2,000** 지점 | 도로 커브 5구간

## 의사 3D 시점

Antarctic Adventure(1983) 레퍼런스:
- 캐릭터 뒤에서 전방을 바라보는 시점
- 도로가 소실점으로 수렴하며 원근감 표현
- 장애물이 먼 곳(작게) → 가까이(크게) 접근
- 도로 커브 구간에서 좌우로 휘어지는 효과

## 파일 구조

```
city-runner/
├── index.html
├── package.json
├── vite.config.js
├── src/
│   ├── main.js                    # Phaser 초기화
│   ├── scenes/
│   │   ├── BootScene.js           # 로딩
│   │   ├── MenuScene.js           # 메인 메뉴
│   │   ├── GameScene.js           # 핵심 게임 루프 + 렌더링
│   │   ├── UIScene.js             # HUD (생명/타이머/점수/거리)
│   │   ├── GameOverScene.js       # 게임오버
│   │   └── StageClearScene.js     # 클리어
│   ├── objects/
│   │   ├── Road.js                # 의사 3D 도로 렌더링 엔진
│   │   ├── Player.js              # 플레이어
│   │   └── ObstacleManager.js     # 장애물/수집물 관리 + 충돌
│   └── config/
│       ├── gameConfig.js          # 전역 설정
│       └── stage1.js              # 스테이지 1 데이터 (Z 기반)
└── assets/                        # (향후 스프라이트 추가)
```

## 기술 스택

- **Phaser 3** — 게임 엔진 (씬 관리, 입력, 타이머)
- **Vite** — 번들러
- **JavaScript ES6+**
- **커스텀 렌더링** — Graphics API로 의사 3D 도로/장애물 매 프레임 그리기
- **커스텀 충돌** — Z좌표 근접 + X 겹침 기반 (Arcade Physics 미사용)
- **Web Audio API** — 코드 생성 SFX (외부 파일 없음)
- **localStorage** — 최고기록 저장

## 스테이지 추가 방법

1. `src/config/stage2.js` 생성 (stage1.js 구조 복사, Z좌표 기반 장애물 배치)
2. `GameScene.js`의 `STAGE_MAP`에 `{ 2: STAGE2_DATA }` 추가
3. `StageClearScene`에서 다음 스테이지로 연결

## 설계문서

- `research.md` — 레퍼런스 분석, 기술 스택, 의사 3D 원리
- `plan.md` — 상세 설계, 원근 투영 수학, 클래스 구조, 구현 순서
