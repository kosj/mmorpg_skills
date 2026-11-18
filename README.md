# MMORPG 제작 스킬 팩 (Unreal Engine 5.8)

MMORPG 제작에 필요한 기준과 검사를 Agent Skills 형식(SKILL.md + 스크립트)으로 묶은 것이다.
판정은 스크립트가 하고, 기준값은 JSON에 있다.

## 스킬 목록

| 스킬 | 하는 일 | 실행 환경 |
|---|---|---|
| `mmorpg-router` | 프로젝트 컨텍스트 관리, 작업을 맞는 스킬로 안내 | 문서만 |
| `ue-asset-spec-check` | 에셋 네이밍, 텍스처, 스태틱 메시 규격 검사 | 수집은 언리얼 에디터, 판정은 Python |
| `ue-perf-budget-check` | CSV Profiler 캡처를 60fps 예산과 비교 | Python |
| `mmo-data-check` | 기획 데이터(CSV) 정합성 검사 | Python |
| `mmo-netcode-review` | 복제/RPC 정적 검사와 넷코드 체크리스트 | Python |
| `mmo-server-capacity` | 대역폭, 서버 수 어림 계산과 서버 구조 가이드 | Python |

## 설치

- **언리얼 MCP에서 쓸 때:** 각 스킬 폴더를 `<Project>/Skills/` 아래에 복사한다.
- **Claude Code 등 코딩 에이전트에서 쓸 때:** 각 스킬 폴더를 `<Project>/.claude/skills/` 아래에 복사한다.
- 두 곳 모두에서 쓰려면 한쪽을 원본으로 두고 다른 쪽은 링크하거나 빌드 스크립트로 복사한다.

Python 3.9 이상이면 된다. 외부 패키지는 쓰지 않는다.

## 처음 할 일

1. `mmorpg-router/references/project-context.md`의 미정 항목을 채운다.
2. 각 스킬 `references/`의 JSON 기준값을 프로젝트 기준으로 바꾼다. 현재 값은 전부 임시값이다.
3. 작은 범위로 한 번씩 돌려 본다.

## 테스트

```
python run_tests.py
```

각 스킬의 판정 로직 단위 테스트를 모두 실행한다.

## 검증 상태

- 판정 로직(순수 Python)은 단위 테스트를 통과했다.
- `ue-asset-spec-check/scripts/collect_assets.py`와 `run_check.py`는 언리얼 에디터 안에서만 실행된다.
  에디터에서 실행해 검증하지 않았다. 처음 실행할 때 `GEN001`이 많이 나오면 5.8의 Python API 이름에
  맞게 고쳐야 한다.
- `ue-perf-budget-check`는 CSV Profiler 형식을 본뜬 가상 데이터로 테스트했다. 실제 5.8 캡처로는
  확인하지 않았다. 열 이름이 다르면 `GEN001`로 알려 주며, `perf-budget.json`의 `columns`에 추가하면 된다.
- `mmo-netcode-review`의 검사기는 정규식 기반이다. 실제 프로젝트 코드에서 오탐과 누락이 있을 수 있다.
