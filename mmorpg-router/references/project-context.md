# 프로젝트 컨텍스트

스킬들이 공유하는 결정 사항이다. 결정이 바뀌면 이 파일을 먼저 고친다.

## 정해진 것

| 항목 | 값 |
|---|---|
| 장르 | MMORPG |
| 엔진 | Unreal Engine 5.8 |
| 플랫폼 | Windows |
| 목표 프레임 | 60fps 이상 (프레임 예산 16.67ms) |

## 미정 (결정되면 채울 것)

| 항목 | 값 | 영향받는 스킬 |
|---|---|---|
| 최소/권장 PC 사양 | 미정 | `ue-perf-budget-check` (측정 기준 PC) |
| 목표 해상도와 그래픽 프리셋 | 미정 | `ue-perf-budget-check` |
| 목표 동시 접속 (전체 / 월드 / 한 장소) | 미정 | `mmo-server-capacity` |
| 월드 구성 (서버군 분리 / 존 분할 / 단일 월드) | 미정 | `mmo-server-capacity`, `mmo-netcode-review` |
| 게임 서버 (언리얼 데디케이티드 서버 / 자체 서버) | 미정 | `mmo-netcode-review`, `mmo-server-capacity` |
| 복제 시스템 (기본 / Replication Graph / Iris) | 미정 | `mmo-netcode-review` |
| 대규모 전투 목표 인원 | 미정 | `mmo-server-capacity`, `ue-perf-budget-check` |
| 전투 방식 (타겟팅 / 논타겟팅 액션) | 미정 | `mmo-netcode-review` |
| 기획 데이터 형식과 위치 | 미정 | `mmo-data-check` |
| 아트 스타일 (실사 / 스타일라이즈드) | 미정 | `ue-asset-spec-check` |

## 임시값으로 들어가 있는 것

아래 파일의 수치는 프로젝트 기준이 아니라 시작점이다. 기준이 정해지면 교체한다.

- `ue-asset-spec-check/references/asset-spec.json`
- `ue-perf-budget-check/references/perf-budget.json`
- `mmo-data-check/references/data-schema.json`
- `mmo-server-capacity/references/scenario.json`
- `mmo-netcode-review/references/lint-config.json`
