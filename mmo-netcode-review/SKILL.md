---
name: mmo-netcode-review
description: Reviews Unreal Engine 5.8 C++ networking code for an MMORPG - runs a static linter for replication and RPC mistakes (Replicated property not registered with DOREPLIFETIME, missing OnRep function, Reliable NetMulticast, Server RPCs that trust client-sent damage/gold/exp values, replicated TArray) and applies an MMO netcode checklist (server authority, relevancy, Iris vs Replication Graph). Use when writing or reviewing replicated actors, RPCs, combat or inventory networking, or when asked about 리플리케이션, RPC, 넷코드 리뷰, 서버 권한, 핵 방지, 동기화.
---

# MMORPG 넷코드 리뷰

네트워크 코드를 두 단계로 본다. 먼저 스크립트로 기계적인 실수를 잡고, 그다음 체크리스트로
설계를 본다. 스크립트가 잡는 항목은 눈으로 다시 찾지 않는다.

## 구성

- `scripts/lint_replication.py`: 순수 Python 정적 검사기. 에디터나 컴파일 없이 실행된다.
- `references/lint-config.json`: 심각도, 의심 단어 목록.
- `references/rules.md`: 규칙별 의미, 수정 방법, 오탐 처리, 검사기가 보지 못하는 것.
- `references/netcode-guide.md`: MMO 넷코드 원칙과 체크리스트, 5.8의 복제 시스템 선택.

## 절차

1. **검사기를 돌린다.**

   ```
   python scripts/lint_replication.py <Project>/Source --config references/lint-config.json \
       --out report.json --md report.md
   ```

   변경된 파일만 보고 싶어도 `Source` 전체를 준다. 등록(`DOREPLIFETIME`)이 다른 파일에 있기 때문이다.
   보고할 때 변경 파일에 해당하는 것만 추린다.
2. **error부터 처리한다.** `NET001`, `NET002`는 복제가 동작하지 않는 버그다.
3. **`NET005`는 하나씩 구현부를 읽는다.** 인자 이름만 보고 낸 경고다. 서버가 그 값을 그대로
   쓰는지, 검증하고 쓰는지 확인하고 결과를 구분해 보고한다.
4. **체크리스트로 설계를 본다.** `references/netcode-guide.md`의 3절(프로퍼티)과 4절(RPC)을 읽고,
   리뷰 대상 코드에 해당하는 항목만 확인한다.
5. **보고한다.** 버그(error), 보안(NET005 확인 결과), 비용(NET003, NET006, 체크리스트) 순으로 전한다.
   각 항목에 파일과 줄 번호를 붙인다.

## 새 코드를 작성할 때

작성 전에 `references/netcode-guide.md`의 1절(원칙)을 읽는다. 작성 후 검사기를 돌려
자기 코드에서 error가 없음을 확인한 뒤 전달한다.

## 주의

- 검사기는 정규식 기반이다. 지적이 틀렸다고 판단되면 고치지 말고 `netlint:ignore`와 이유를
  제안한다(`references/rules.md`의 오탐 처리).
- 블루프린트 RPC, Tick에서의 호출 빈도, 관련성 설정은 검사기가 보지 못한다. "검사기 통과"를
  "넷코드 문제 없음"으로 보고하지 않는다.
- 복제 시스템(기본, Replication Graph, Iris) 선택에 따라 기준이 달라진다. 프로젝트가 무엇을
  쓰는지는 `mmorpg-router/references/project-context.md`에서 확인하고, 미정이면 미정이라고 밝힌다.
