---
name: mmo-combat-skill
description: Validates skill data for the target-based combat of the MMORPG and estimates sustained damage per class - checks ranges against the server view distance, cast times, cooldowns and global cooldown (including skills that could be used at an infinite rate), resource costs, area skills without a target cap, movement modes a skill can be used in, and runs a simple priority-rotation simulation to flag coefficient typos, skills that are never worth using, and classes whose damage is far from the others. Use when skill data is added or changed, when reviewing combat balance numbers, or when asked about 스킬 데이터, 쿨다운, 사거리, 전투 밸런스, DPS, 스킬 계수, 전역 쿨다운.
---

# 전투 스킬 데이터 검사

타겟팅 전투의 스킬 데이터(CSV)를 검사한다. 판정과 계산은 전부 `scripts/check_skills.py`가 한다.
피해량이나 DPS를 암산하지 않는다.

## 구성

- `scripts/check_skills.py`: 순수 Python. 형식과 규칙 검사, 직업별 DPS 어림 계산.
- `references/combat-guide.md`: 열 정의, 규칙 설명, 계산 모델과 한계, 타겟팅 전투의 데이터 설계.
- `references/combat-config.json`: 전역 쿨다운, 서버 틱, 최대 사거리, 기준 능력치, 허용 편차.
- `references/example/skills.csv`: 전사, 마법사, 궁수 예시.

## 절차

1. **열이 맞는지 본다.** 프로젝트의 스킬 테이블 열 이름이 다르면 CSV의 머리글만 읽고
   `references/combat-guide.md` 1절의 열 정의와 대응시킨다. 대응이 안 되는 열은 사용자에게 묻는다.
2. **검사한다.**

   ```
   python scripts/check_skills.py <skills.csv> --config references/combat-config.json \
       --out report.json --md report.md
   ```

3. **error부터 처리한다.** `SKILL004`의 무한 연속 사용과 `SKILL007`의 대상 수 상한 없음은 서버 부하와
   악용으로 이어지므로 개수가 적어도 따로 언급한다.
4. **시뮬레이션 지적을 구분해 전한다.** `SKILL009`, `SKILL010`, `SKILL011`은 확정된 오류가 아니라
   확인이 필요한 신호다. "오타일 가능성"과 "의도한 설계일 가능성"을 함께 말한다.
5. **수치는 고치지 않고 제안한다.** 계수, 쿨다운, 비용은 기획 결정이다. 오타가 분명해 보여도 바꿀 값을
   제안하고 확인을 받는다.

## 다른 스킬과의 관계

- 스킬이 참조하는 아이템, 버프, 대상 ID의 존재 여부는 `mmo-data-check`의 스키마에 스킬 테이블을
  추가해 검사한다. 이 스킬은 전투 규칙과 수치만 본다.
- `usable_modes`의 이동 모드 이름은 `ue-client-contract`의 `movement_modes`와 같은 이름을 쓴다.
  `mounted`는 탑승 중을 뜻하는 이 스킬의 추가 값이다.
- 서버의 스킬 요청 검증 순서는 `mmo-netcode-review/references/custom-server-guide.md`의 타겟팅 전투 절.
- 최대 사거리는 서버가 대상을 볼 수 있는 거리(관심 영역) 안이어야 한다(`mmo-server-capacity`).

## 주의

- 시뮬레이션은 대상 하나에 대한 지속 피해만 본다. 범위 피해, 버프, 치명타, 대상의 방어, 이동과
  거리 유지, 플레이어 숙련도는 들어 있지 않다. 결과를 "밸런스가 맞다"는 근거로 쓰지 않는다.
- 기준 능력치(`reference`)가 임시값이면 DPS의 절대값은 의미가 없다. 직업 간 비율과 이상치만 본다.
- 검사를 통과시키려고 허용 편차나 이상치 배수를 올리지 않는다. 기준을 바꿔야 하면 사용자에게 묻는다.
