# 프로젝트 컨텍스트

스킬들이 공유하는 결정 사항이다. 결정이 바뀌면 이 파일을 먼저 고친다.

## 정해진 것

| 항목 | 값 |
|---|---|
| 장르 | MMORPG |
| 엔진 | Unreal Engine 5.8 (클라이언트) |
| 플랫폼 | Windows |
| 목표 프레임 | 60fps 이상 (프레임 예산 16.67ms) |
| 게임 서버 | 자체 서버. 언리얼 데디케이티드 서버를 쓰지 않는다 |
| 서버 언어 | C++ |
| 프로토콜 형식 | FlatBuffers. 클라이언트와 서버가 같은 `.fbs`에서 코드를 생성한다 |
| 이동 컴포넌트 | Character Movement Component (CMC). 게임 코드는 자체 이동 인터페이스를 거친다. Mover는 UE6 이전 시 다시 평가한다 |
| 플레이어 스켈레톤 | 1개 (공용 휴머노이드). 성별과 체형 차이는 스켈레톤을 늘리지 않고 메시 변형과 비율 조정으로 만든다 |
| 탈것 스켈레톤 | 네발 계열 1개. 모든 탈것이 네발 스켈레톤과 애니메이션 세트를 공유한다. 날개 본을 처음부터 포함하고, 날개 달린 탈것만 비행 모드를 갖는다 (권장안 적용. 반대 의견이 있으면 바꾼다) |
| 전투 방식 | 타겟팅. 클라이언트는 스킬 ID와 대상 ID를 보내고, 명중과 피해는 서버가 판정한다 |
| 복제 시스템 | 해당 없음. 게임플레이 동기화에 언리얼 복제(Replicated, RPC, Iris, Replication Graph)를 쓰지 않는다 |

## 자체 서버 결정이 뜻하는 것

- 언리얼은 클라이언트 역할만 한다. 서버와의 통신은 자체 프로토콜로 한다.
- 이동, 전투 판정, AI는 서버 코드가 한다. 서버는 언리얼의 월드를 모르므로 충돌/내비게이션 데이터를 언리얼에서 내보내 서버에 줘야 한다.
- 언리얼의 네트워크 기능(캐릭터 이동 동기화, 어빌리티 복제 등)을 그대로 쓸 수 없다. 클라이언트 쪽 보간과 예측을 직접 만든다.
- 자세한 내용은 `mmo-netcode-review/references/custom-server-guide.md`.

## 미정 (결정되면 채울 것)

| 항목 | 값 | 영향받는 스킬 |
|---|---|---|
| 목표 동시 접속 (전체 / 월드 / 한 장소) | 나중에 결정 | `mmo-server-capacity` |
| 서버 네트워크 라이브러리 (Boost.Asio / 자체 IOCP 등) | 미정 | `mmo-netcode-review` |
| `.fbs` 스키마 폴더 위치와 패킷 번호 대역 | 미정 | `mmo-protocol-check` |
| 전송 방식 (TCP / UDP 기반 / 혼용) | 미정 | `mmo-netcode-review`, `mmo-server-capacity` |
| 서버 내비메시 방식 (내보낸 OBJ를 서버에서 다시 빌드 / 엔진의 내비메시를 직접 저장) | 미정. 권장은 서버에서 다시 빌드 | `ue-server-data-export` |
| 월드 구성 (서버군 분리 / 존 분할 / 단일 월드) | 미정 | `mmo-server-capacity` |
| 지형 (Landscape / Mesh Terrain) | 미정. Mesh Terrain은 5.8에서 Experimental | `ue-environment-worldbuilding` |
| 체형 변형의 범위 (키와 비율을 어디까지 허용하는가) | 미정 | `ue-character-parts`, `ue-animation-ik` |
| 규약 데이터 폴더 위치, 이동 모드와 상태 이름 | 미정. 예시 값 사용 중 | `ue-client-contract` |
| 최소/권장 PC 사양 | 미정 | `ue-perf-budget-check` (측정 기준 PC) |
| 목표 해상도와 그래픽 프리셋 | 미정 | `ue-perf-budget-check` |
| 대규모 전투 목표 인원 | 미정 | `mmo-server-capacity`, `ue-perf-budget-check` |
| 기획 데이터 형식과 위치 | 미정 | `mmo-data-check`, `mmo-combat-skill` |
| 직업 목록, 전역 쿨다운, 서버 틱 주기 | 미정. 예시 값 사용 중 | `mmo-combat-skill` |
| 아트 스타일 (실사 / 스타일라이즈드) | 미정 | `ue-asset-spec-check` |

## 임시값으로 들어가 있는 것

아래 파일의 수치는 프로젝트 기준이 아니라 시작점이다. 기준이 정해지면 교체한다.

- `ue-asset-spec-check/references/asset-spec.json`
- `ue-perf-budget-check/references/perf-budget.json`
- `mmo-data-check/references/data-schema.json`
- `mmo-server-capacity/references/scenario.json` (동시 접속과 서버 정원은 결정 전까지 가정값)
- `mmo-netcode-review/references/lint-config.json`
- `mmo-protocol-check/references/protocol-config.json`
- `mmo-combat-skill/references/combat-config.json` (전역 쿨다운, 서버 틱, 최대 사거리, 기준 능력치)
- `ue-client-contract/references/example/contract.json` (예산, 상태 이름, 소켓 이름 모두 예시.
  구조는 프로젝트 결정대로 플레이어 스켈레톤 1개, 네발 탈것 스켈레톤 1개다)

## 기술 선택 원칙

- 최신 기능을 우선 검토하되, 본 제작의 전제로 삼는 것은 5.8에서 Production-Ready인 것으로 한다
  (Mutable, Motion Matching, MegaLights, Iris 등). Experimental인 것(Mover, UAF, Mesh Terrain,
  Procedural Vegetation Editor, MetaHuman Crowd)은 평가 대상으로 두고 교체 가능한 구조로 감싼다.
- UE 5.8은 UE5의 마지막 주요 버전으로 예고되었다. 데이터(규약, 기획 데이터, 프로토콜)를 엔진 기능과
  분리해 두는 것이 UE6 이전 대비책이다.
