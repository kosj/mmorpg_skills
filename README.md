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
| `mmo-combat-skill` | 타겟팅 전투 스킬 데이터 검사, 직업별 DPS 어림 계산 | Python |
| `mmo-protocol-check` | FlatBuffers 패킷 정의 검사, 버전 호환 검사, C++ 헤더 생성 | Python |
| `mmo-netcode-review` | 자체 서버용 넷코드 체크리스트, 언리얼 복제 문법 유입 검사 | Python |
| `mmo-server-capacity` | 대역폭, 서버 수 어림 계산과 서버 구조 가이드 | Python |
| `mmo-ci-pipeline` | 바뀐 파일에 맞는 검사를 한 번에 실행, 함께 바뀌어야 하는 파일 규칙, 통합 보고서 | Python |
| `ue-server-data-export` | 서버용 맵 데이터(내비 지오메트리, 스폰, 볼륨) 묶음 생성과 검사, 클라이언트와의 맵 버전 일치 확인 | 수집은 언리얼 에디터, 묶기와 검사는 Python |
| `ue-client-contract` | 파츠·탈것·이동 모드·애니메이션·IK·이펙트·날씨·바이옴의 연결 검사와 확장 시 필요한 것 계산 | Python |
| `ue-character-parts` | 파츠 조립 (Mutable, 소켓 부착), 다수 캐릭터 대응 | 문서 + 규약 검사 |
| `ue-animation-ik` | Motion Matching, 애니메이션 세트, 리타기팅, 발/손 IK | 문서 + 규약 검사 |
| `ue-mount-flight` | 탈것, 탑승, 활공, 비행, 이동 모드 설계 | 문서 + 규약 검사 |
| `ue-vfx-niagara` | 이펙트 분류와 예산, 확장성, 부착 규칙 | 문서 + 규약 검사 |
| `ue-weather` | 날씨 상태와 파라미터, 구성 요소, 게임플레이 연결 | 문서 + 규약 검사 |
| `ue-environment-worldbuilding` | 지형, 식생, PCG 배치, 스트리밍, 서버 데이터 동기화 | 문서 + 규약 검사 |

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
- `ue-server-data-export/scripts/collect_level_data.py`는 언리얼 에디터 안에서만 실행된다. 에디터에서 실행해
  검증하지 않았다. 내비 지오메트리는 콘솔 명령으로 따로 내보내야 한다.
- `ue-client-contract`는 규약 데이터끼리의 일치만 본다. 규약에 적힌 소켓이나 애니메이션이 에셋에 실제로
  있는지는 확인하지 않는다.
- 클라이언트 분야 스킬 6개의 가이드는 2026년 11월 기준 공개 자료로 조사한 5.8의 기능 상태를 담고 있다.
  엔진에서 직접 실행해 확인한 내용이 아니다.
- `mmo-protocol-check`는 FlatBuffers 문법의 일부만 해석한다. 예시 스키마(`game.fbs`)는 flatc로 컴파일해
  확인하지 않았다. 생성되는 C++ 헤더는 g++(C++17)로 컴파일되는 것을 테스트에서 확인한다.
