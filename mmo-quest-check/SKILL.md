---
name: mmo-quest-check
description: Validates quest data for the MMORPG - prerequisite cycles, missing or self-referencing prerequisites, prerequisites that need a higher level than the quest itself, kill and collect targets that do not exist, collect items that no monster drops and no vendor sells, collect quests that need far too many kills given drop rates, missing reward items, gaps and extra starting points in the main quest chain, and experience rewards that are too large for the level - and reports how much of each level's experience quests provide. Use when quests are added or changed, when drop rates or monsters used by quests change, or when asked about 퀘스트 검사, 선행 퀘스트, 퀘스트 보상, 메인 퀘스트 흐름, 수집 퀘스트.
---

# 퀘스트 데이터 검사

퀘스트 표(CSV)의 구조와 다른 표(몬스터, 아이템, 드롭, 레벨)와의 연결을 검사한다.
판정은 전부 `scripts/check_quests.py`가 한다. 선행 관계를 눈으로 따라가며 판단하지 않는다.

## 구성

- `scripts/check_quests.py`: 순수 Python. 구조, 연결, 진행 속도 검사와 레벨별 퀘스트 경험치 표.
- `references/quest-guide.md`: 열 정의, 규칙 설명, 결과 읽는 법, 한계, 퀘스트 데이터 설계 원칙.
- `references/quest-config.json`: 퀘스트 종류, 목표 종류, 허용 기준.
- `references/example/`: 10레벨 예시 데이터와 퀘스트 10개.

## 절차

1. **열이 맞는지 본다.** 프로젝트의 퀘스트 표 열 이름이 다르면 머리글만 읽고
   `references/quest-guide.md` 1절의 열 정의와 대응시킨다. 대응이 안 되는 열은 사용자에게 묻는다.
2. **검사한다.** 퀘스트 표와 몬스터, 아이템, 드롭 표가 같은 폴더에 있어야 한다.

   ```
   python scripts/check_quests.py <데이터 폴더> --config references/quest-config.json \
       --out report.json --md report.md
   ```

3. **error부터 처리한다.** `QUEST003`(순환)과 `QUEST006`(얻을 수 없는 수집 아이템)은 그 퀘스트와
   뒤에 이어진 퀘스트 전부를 완료할 수 없게 만든다. 메인 퀘스트에 걸리면 게임 진행이 막힌다.
4. **보고한다.** 완료할 수 없는 퀘스트, 끊긴 참조, 진행 속도 경고 순으로 전하고, 레벨별 퀘스트
   경험치 표에서 비중이 0%인 레벨을 함께 알린다.
5. **수정은 요청받았을 때만 한다.** 오타처럼 답이 분명한 참조만 고치고, 보상과 목표 개수는
   고칠 값을 제안하고 확인을 받는다.

## 다른 스킬과의 관계

- 드롭 확률이나 몬스터가 바뀌면 퀘스트도 다시 검사한다. 드롭 확률을 낮추면 수집 퀘스트의 필요
  사냥 수가 늘어난다(`QUEST013`).
- `mmo-economy-check`는 같은 폴더의 퀘스트 표를 읽어 퀘스트 보상을 성장 곡선에 더한다. 퀘스트 보상을
  바꾸면 경제 검사의 레벨업 시간도 달라지므로 함께 돌린다.
- NPC와 위치(대화, 도달 목표)는 이 검사가 보지 않는다. 스폰 지점 ID와의 연결은
  `ue-server-data-export`의 데이터가 정해지면 추가한다.

## 주의

- 이 검사는 완료 가능성과 수치의 이상만 본다. 퀘스트가 재미있는지, 이야기가 이어지는지는 보지 않는다.
- "얻을 수 있다"는 드롭이나 상점 판매가 데이터에 있다는 뜻이다. 그 몬스터가 실제로 맵에 배치되어
  있는지는 확인하지 않는다.
- 검사를 통과시키려고 허용 기준을 넓히지 않는다. 기준을 바꿔야 하면 사용자에게 묻는다.
