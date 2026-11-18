---
name: mmorpg-router
description: Entry point for work on this Unreal Engine 5.8 MMORPG project. Holds the project context (platform, frame target, decided and undecided architecture choices) and routes a task to the right project skill - asset spec check, performance budget, game data validation, combat skill data, economy and progression, protocol check, netcode review, server capacity, server world data export, the check pipeline, and the client skills (content contract, character parts, animation and IK, mounts and flight, VFX, weather, environment). Use at the start of any task in this project, when unsure which skill applies, when a task spans several areas, or when asked about project standards, 프로젝트 기준, 어떤 스킬, 제작 파이프라인, 체크리스트.
---

# MMORPG 프로젝트 라우터

이 프로젝트의 작업을 맞는 스킬로 보내고, 스킬들이 공유하는 프로젝트 결정 사항을 관리한다.

## 먼저 할 일

`references/project-context.md`를 읽는다. 플랫폼, 목표 프레임, 정해진 것과 미정인 것이 적혀 있다.
미정 항목에 의존하는 답을 할 때는 가정을 밝히고, 사용자가 결정을 말하면 그 파일에 기록하자고 제안한다.

## 어느 스킬을 쓰는가

| 작업 | 스킬 |
|---|---|
| 에셋을 추가/수정했다, 네이밍·텍스처·메시 규격을 확인한다 | `ue-asset-spec-check` |
| 프레임이 나오는지 확인한다, 캡처를 분석한다, 빌드 간 성능을 비교한다 | `ue-perf-budget-check` |
| 아이템·몬스터·드롭·레벨 등 기획 데이터를 추가/수정했다 | `mmo-data-check` |
| 스킬 데이터(사거리, 쿨다운, 계수, 비용)를 추가/수정했다. 직업 간 피해량을 비교한다 | `mmo-combat-skill` |
| 몬스터 보상, 드롭, 아이템 가격, 경험치 곡선을 바꿨다. 성장 속도와 골드 수급을 확인한다 | `mmo-economy-check` |
| 패킷 정의(`.fbs`)를 추가/수정했다, 패킷 번호나 버전 호환을 확인한다 | `mmo-protocol-check` |
| 패킷 핸들러, 클라이언트 네트워크 코드, 전투/인벤토리 동기화를 작성하거나 리뷰한다 | `mmo-netcode-review` |
| 서버 구조, 동시 접속, 존 서버 수, 대역폭, 밀집 상황을 논의한다 | `mmo-server-capacity` |
| 파츠, 탈것, 이동 모드, 애니메이션 세트, 부착 이펙트, 날씨, 바이옴을 추가/변경했다. 확장에 무엇이 더 필요한지 확인한다 | `ue-client-contract` |
| 캐릭터 커스터마이징, 장비 외형, 코스튬, 염색 | `ue-character-parts` |
| 이동 애니메이션, 애니메이션 세트, 리타기팅, 발/손 IK | `ue-animation-ik` |
| 탈것, 탑승, 활공, 비행, 이동 모드 전환 | `ue-mount-flight` |
| 스킬/피격/파츠/탈것 이펙트, 이펙트 최적화 | `ue-vfx-niagara` |
| 날씨, 비/눈/안개/바람, 젖은 표면 | `ue-weather` |
| 지형, 식생, 배경 에셋 제작과 배치, 바이옴 | `ue-environment-worldbuilding` |
| 지형, 충돌, 스폰 지점, 볼륨을 바꿨다. 서버용 맵 데이터를 내보내고 버전을 맞춘다 | `ue-server-data-export` |
| 변경을 올리기 전에 관련 검사를 한 번에 돌린다. 커밋 전 훅이나 야간 빌드를 설정한다 | `mmo-ci-pipeline` |
| 에디터를 직접 조작한다(액터 배치, 블루프린트 편집 등) | Epic의 `unreal-mcp` 스킬 |

## 여러 영역에 걸친 작업

검사를 한 번에 돌리려면 `mmo-ci-pipeline`을 쓴다. 바뀐 파일로 필요한 검사를 골라 준다.
손으로 하나씩 돌릴 때는 아래 순서를 따른다. 앞 단계의 실패가 뒤 단계 결과를 무의미하게 만들기 때문이다.

1. `mmo-data-check`: 데이터가 깨져 있으면 나머지 검증이 의미 없다. 스킬 데이터가 바뀌었으면 `mmo-combat-skill`,
   보상이나 가격이 바뀌었으면 `mmo-economy-check`도 함께 돌린다.
2. `mmo-protocol-check`: 패킷 정의 변경이 있을 때. 코드 생성 전에 돌린다.
3. `mmo-netcode-review`: 네트워크 코드 변경이 있을 때.
4. `ue-client-contract`: 파츠, 탈것, 이동 모드, 이펙트, 날씨, 바이옴 변경이 있을 때.
5. `ue-asset-spec-check`: 콘텐츠 변경이 있을 때.
6. `ue-server-data-export`: 맵의 지형, 충돌, 스폰, 볼륨이 바뀌었을 때.
7. `ue-perf-budget-check`: 위가 통과한 빌드로 측정한다.

예: "새 던전 추가"는 몬스터/드롭 데이터(1), 보스 패턴 패킷(2)과 핸들러(3), 던전 에셋(5), 던전 맵의 서버 데이터(6), 던전 내 프레임(7)을 모두 본다.

예: "새 비행 탈것 추가"는 탈것 아이템 데이터(1), 탑승/이착륙 패킷(2)과 핸들러(3), 규약의 탈것·세트·소켓(4),
탈것 메시(5), 비행 최고 속도에서의 스트리밍(7)을 본다. 만드는 방법은 `ue-mount-flight`, `ue-animation-ik`,
`ue-vfx-niagara`가 다룬다.

## 클라이언트 분야 스킬의 공통 규칙

- 5.8 기능의 상태(Production-Ready, Experimental)는 각 스킬의 가이드에 조사한 내용이 있다. Experimental
  기능을 본 제작의 전제로 삼는 제안을 할 때는 상태를 밝히고 안정된 대안을 함께 낸다.
- 분야끼리의 연결(소켓, 상태 이름, 이동 모드, 이펙트 ID, 날씨 ID)은 `ue-client-contract`의 데이터로
  적는다. 코드나 에셋에 다른 분야의 이름을 직접 적지 않는다.

결과는 스킬별로 한 줄씩(통과/실패, error 수) 요약한 뒤 실패 항목만 자세히 전한다.

## 해당 스킬이 없을 때

`references/roadmap.md`에 아직 만들지 않은 영역이 적혀 있다. 그 영역의 작업이면 스킬 없이
일반 지식으로 돕되, 프로젝트 기준이 아직 없다는 점을 밝힌다. 같은 종류의 작업이 반복되면
스킬로 만들자고 제안한다.

## 스킬을 새로 만들거나 고칠 때

이 팩의 스킬은 같은 구조를 따른다. 새 스킬도 맞춘다.

- `SKILL.md`: 언제 쓰는지, 절차, 주의. 수치를 적지 않는다.
- `scripts/`: 판정 로직. Unreal에 의존하는 수집 코드와 순수 Python 판정 코드를 분리한다.
- `references/`: 기준값(JSON)과 규칙 설명(`rules.md`). 수치는 여기에만 둔다.
- `tests/`: 판정 로직의 통과/위반 사례.
- 판정은 스크립트가 한다. 종료 코드는 0 통과, 1 error 있음, 2 입력 문제.
- 보고서는 `report.json`과 `report.md` 두 가지로 낸다.
