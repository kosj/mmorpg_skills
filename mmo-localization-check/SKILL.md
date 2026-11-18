---
name: mmo-localization-check
description: Validates the localization string table (CSV) for the MMORPG - duplicate or empty keys, missing translations, placeholders and rich-text tags that differ from the source text, unbalanced braces or tags, text wider than its UI limit or far longer than the source (counting Korean, Japanese and Chinese characters as double width), strings left identical to the source, stray whitespace, and keys the game uses that are missing from the table. Use when strings or translations are added or changed, before a build that ships a new language, or when asked about 현지화, 번역 검사, 문자열 테이블, 자리표시자, 텍스트 잘림, 다국어.
---

# 현지화 문자열 검사

문자열 표(CSV)의 형식 문제를 찾는다. 번역이 자연스러운지는 보지 않는다.
판정은 전부 `scripts/check_strings.py`가 한다.

## 구성

- `scripts/check_strings.py`: 순수 Python. 형식 검사와 언어별 번역률.
- `references/localization-guide.md`: 표 형식, 규칙 설명, 폭 계산, 한계, 문자열 작성 원칙.
- `references/loc-config.json`: 원문 언어, 필수/선택 언어, 폭 기준.
- `references/example/`: 예시 문자열 표와 사용 키 목록.

## 절차

1. **설정을 맞춘다.** `references/loc-config.json`의 원문 언어(`source_language`), 필수 언어, 선택 언어,
   열 이름이 프로젝트의 표와 맞는지 머리글 행으로 확인한다.
2. **검사한다.**

   ```
   python scripts/check_strings.py <strings.csv> --config references/loc-config.json \
       --used-keys <게임이 쓰는 키 목록> --out report.json --md report.md
   ```

   `--used-keys`는 없어도 된다. 주면 표에 없는 키(`LOC008`)와 쓰이지 않는 키 수를 알려 준다.
3. **error부터 처리한다.** `LOC003`(자리표시자 불일치)과 `LOC007`(닫히지 않은 괄호)은 게임에서 값이
   비거나 글자가 깨져 보이게 한다. 서식 문자열을 쓰는 코드에 따라 크래시가 날 수도 있다.
4. **보고한다.** 언어별 번역률, error 수, 규칙별 개수, 대표 사례 순으로 전한다.
5. **번역문은 고치지 않는다.** 자리표시자 오타처럼 답이 분명한 것만 수정을 제안하고, 문장을 줄이거나
   다시 쓰는 일은 번역 담당자에게 넘긴다. 요청받으면 대안 문장을 제안할 수 있다.

## 주의

- 폭은 글자 수로 어림한 값이다. 실제 폰트와 UI에서 잘리는지는 화면으로 확인해야 한다.
- 원문과 같은 번역(`LOC005`)은 고유명사나 약어(HP, PvP)에서 정상이다. 오탐이 많으면
  `same_as_source_ok_pattern`을 조정한다.
- 게임이 쓰는 키 목록을 뽑는 방법은 프로젝트마다 다르다(코드와 데이터에서 키 문자열 수집).
  목록이 불완전하면 "쓰이지 않는 키" 수는 믿지 않는다.
