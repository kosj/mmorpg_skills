---
name: mmo-economy-check
description: Estimates leveling speed and gold flow for the MMORPG from game data tables (monsters, drops, items, levels) and flags problems - monsters that are far better gold or experience farms than others at the same level, level ranges with nothing to hunt, sudden leveling walls or drops in the time-to-level curve, and vendor items that are unaffordable or trivially cheap for their grade and level. Use when monster rewards, drop tables, item prices or the experience curve change, when reviewing progression pacing, or when asked about 경제, 골드 수급, 레벨업 속도, 성장 곡선, 사냥터 효율, 아이템 가격, 인플레이션.
---

# 성장과 재화 흐름 검사

기획 데이터로 "레벨마다 얼마나 걸리고 골드를 얼마나 버는가"를 어림 계산하고 이상한 곳을 찾는다.
계산은 전부 `scripts/check_economy.py`가 한다. 시간당 골드나 레벨업 시간을 암산하지 않는다.

## 구성

- `scripts/check_economy.py`: 순수 Python. 레벨별 곡선 계산과 판정.
- `references/economy-guide.md`: 계산 모델, 규칙 설명, 모델의 한계, 결과 읽는 법.
- `references/economy-config.json`: 플레이어 기준 전투력, 사냥 레벨 범위, 허용 기준.
- `references/example/`: 식으로 만든 10레벨 예시 데이터.

## 절차

1. **데이터 정합성을 먼저 본다.** `mmo-data-check`를 돌려 통과한 데이터로 계산한다. 참조가 끊긴
   데이터로 계산하면 드롭 가치가 0으로 잡혀 결과가 틀린다.
2. **계산한다.**

   ```
   python scripts/check_economy.py <데이터 폴더> --config references/economy-config.json \
       --out report.json --md report.md
   ```

   파일 이름이 다르면 `economy-config.json`의 `files`를 고친다.
3. **곡선을 먼저 본다.** `report.md`의 레벨별 표에서 레벨업 시간이 매끄럽게 늘어나는지 확인한다.
   지적 사항은 이 표에서 튀는 곳을 짚은 것이다.
4. **보고한다.** 최고 레벨까지의 시간, error(사냥감이 없는 구간), 효율이 튀는 몬스터, 가격이 맞지 않는
   아이템 순으로 전한다. 각 지적에 "오타일 가능성"과 "의도한 설계일 가능성"을 함께 말한다.
5. **변경안을 비교해 달라는 요청에는** 데이터 폴더를 복사해 값을 바꾸고 양쪽을 돌려 표로 비교한다.
   원본 데이터는 사용자가 확정한 뒤에 고친다.

## 주의

- 사냥만 계산한다. 퀘스트 보상, 플레이어 간 거래, 제작, 파티 사냥, 수리비 같은 고정 소모는 들어 있지
  않다. "경제가 건전하다"는 근거로 쓰지 않는다. 용도는 튀는 값 찾기와 변경 전후 비교다.
- 시간의 절대값은 `economy-config.json`의 플레이어 기준 전투력에 달려 있다. 임시값이면 레벨 간 비율과
  이상치만 본다. 전투력 값은 `mmo-combat-skill`의 직업별 DPS가 정해지면 그에 맞춘다.
- 수치는 고치지 않고 제안한다. 보상, 가격, 경험치 곡선은 기획 결정이다.
- 검사를 통과시키려고 허용 기준을 넓히지 않는다. 기준을 바꿔야 하면 사용자에게 묻는다.
