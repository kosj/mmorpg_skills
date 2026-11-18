---
name: mmorpg-router
description: Entry point for work on this Unreal Engine 5.8 MMORPG project. Holds the project context (platform, frame target, decided and undecided architecture choices) and routes a task to the right project skill - asset spec check, performance budget, game data validation, netcode review, server capacity. Use at the start of any task in this project, when unsure which skill applies, when a task spans several areas, or when asked about project standards, 프로젝트 기준, 어떤 스킬, 제작 파이프라인, 체크리스트.
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
| 복제 액터, RPC, 전투/인벤토리 네트워크 코드를 작성하거나 리뷰한다 | `mmo-netcode-review` |
| 서버 구조, 동시 접속, 존 서버 수, 대역폭, 밀집 상황을 논의한다 | `mmo-server-capacity` |
| 에디터를 직접 조작한다(액터 배치, 블루프린트 편집 등) | Epic의 `unreal-mcp` 스킬 |

## 여러 영역에 걸친 작업

작업 하나가 여러 스킬에 해당하면 아래 순서로 돌린다. 앞 단계의 실패가 뒤 단계 결과를 무의미하게 만들기 때문이다.

1. `mmo-data-check`: 데이터가 깨져 있으면 나머지 검증이 의미 없다.
2. `mmo-netcode-review`: 코드 변경이 있을 때.
3. `ue-asset-spec-check`: 콘텐츠 변경이 있을 때.
4. `ue-perf-budget-check`: 위가 통과한 빌드로 측정한다.

예: "새 던전 추가"는 몬스터/드롭 데이터(1), 보스 패턴 RPC(2), 던전 에셋(3), 던전 내 프레임(4)을 모두 본다.

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
