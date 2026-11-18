---
name: mmo-data-check
description: Validates MMORPG game data tables exported as CSV (items, monsters, drop tables, level curves, quests, skills) against a JSON schema - types, ranges, duplicate IDs, broken references between tables, drop probability sums, economy exploits such as sell price above buy price, and non-increasing level curves. Use when game data is added or changed, before submitting data to source control, or when asked about 데이터 검증, 테이블 검사, 드롭 확률, 밸런스 데이터, 참조 오류.
---

# MMORPG 게임 데이터 검사

기획 데이터(CSV)가 스키마를 지키는지 검사한다. MMORPG에서 데이터 오류는 서버 오류나
경제 붕괴로 이어지므로, 데이터가 바뀔 때마다 돌린다.
판정은 전부 `scripts/check_data.py`가 한다. 표를 눈으로 읽고 판단하지 않는다.

## 구성

- `scripts/check_data.py`: 순수 Python. 스키마대로 검사하고 보고서를 만든다.
- `references/data-schema.json`: 테이블 정의. 검사 내용을 바꾸려면 이 파일만 고친다.
- `references/rules.md`: 규칙별 의미, 스키마 작성법. 위반을 설명하거나 테이블을 추가할 때 읽는다.

## 절차

1. **데이터 폴더를 찾는다.** 사용자가 말한 경로를 쓴다. DataTable 에셋만 있고 CSV가 없으면
   에디터에서 CSV로 내보내야 한다(`references/rules.md`의 마지막 절).
2. **스키마가 데이터와 맞는지 본다.** 기본 `data-schema.json`은 예시다. 프로젝트 테이블 이름과
   열 이름이 다르면 CSV의 머리글 행만 읽어 스키마를 먼저 맞춘다. 스키마에 없는 테이블은 검사되지
   않으므로, 빠진 테이블이 있으면 보고할 때 알린다.
3. **검사한다.**

   ```
   python scripts/check_data.py <데이터 폴더> --schema references/data-schema.json \
       --out report.json --md report.md
   ```

4. **보고한다.** error 개수, 테이블별 개수, 대표 위반 순으로 짧게 전한다.
   `DATA007`(끊어진 참조)과 `DATA010`(경제 관련 대소 관계)은 개수가 적어도 따로 언급한다.
5. **수정은 요청받았을 때만 한다.** 오타처럼 답이 분명한 것만 고치고, 수치 밸런스에 해당하는
   값(가격, 확률, 경험치)은 고칠 값을 제안만 하고 기획자 확인을 받는다.

## 주의

- 이 검사는 형식과 정합성만 본다. 밸런스가 재미있는지는 판단하지 않는다.
- 새 규칙이 필요하면 먼저 스키마 옵션으로 표현되는지 본다. 안 되면 `check_data.py`에
  `_chk_<이름>` 메서드를 추가하고 테스트를 하나 붙인다.
