---
name: ue-client-contract
description: Validates the data contract that links client content systems in the Unreal Engine 5.8 MMORPG - character parts, slots and sockets, skeletons, animation sets, movement modes (ground, swim, glide, fly), mounts and rider seats, IK profiles, VFX attachments and budgets, weather states, and biomes - and reports what is missing when content is added or extended (for example giving a mount flight, adding a new part with effects, or a weather that blocks flying). Use when adding or changing parts, mounts, movement modes, animation sets, attached effects, weather or biomes, when planning an extension, or when asked about 연결 규약, 확장성, 파츠와 탈것 연결, 호환 표, 소켓, 탑승.
---

# 클라이언트 연결 규약

파츠, 탈것, 비행, 애니메이션, IK, VFX, 날씨, 배경은 따로 만들어도 서로를 참조한다.
이 스킬은 그 참조를 데이터(JSON)로 적어 두고 스크립트로 검사한다. 새 콘텐츠를 추가했을 때
"무엇이 더 필요한지"를 사람이 기억하지 않고 검사기가 알려 주게 하는 것이 목적이다.

## 구성

- `scripts/check_contract.py`: 순수 Python. 규약 폴더의 모든 `.json`을 합쳐 검사하고 연결 표를 만든다.
- `references/contract-schema.md`: 항목 종류와 필드, 서로 어떻게 이어지는지.
- `references/rules.md`: 규칙별 의미와 고치는 방법.
- `references/example/contract.json`: 사람 캐릭터, 말, 그리핀(비행), 날씨 4종, 바이옴 2종 예시.

## 콘텐츠를 추가하거나 바꿨을 때

1. **규약 데이터를 고친다.** 새 항목은 기존 파일에 넣거나 콘텐츠 팩용 새 `.json`으로 추가한다.
   필드는 `references/contract-schema.md`를 읽고 맞춘다.
2. **검사한다.**

   ```
   python scripts/check_contract.py <규약 폴더> --out report.json --md report.md --matrix matrix.md
   ```

3. **지적 사항을 작업 목록으로 바꾼다.** 각 지적은 빠진 에셋이나 데이터 하나에 해당한다.
   `LINK003`은 만들어야 할 애니메이션 상태, `LINK002`는 스켈레톤에 추가할 소켓이다.
4. **보고한다.** error 수, 그리고 "이 변경을 완성하려면 더 필요한 것" 목록으로 전한다.
   `matrix.md`의 탈것/날씨 표가 바뀌었으면 바뀐 줄을 함께 보여 준다.

## 확장을 계획할 때

아직 만들지 않은 것을 규약에 먼저 적고 검사기를 돌린다. 나오는 지적이 곧 작업 범위다.
예: 말에 비행을 추가하려면 탈것의 `modes`에 `fly`를 넣고 돌린다. 말 애니메이션 세트에 없는
비행 상태와 탑승자 애니메이션 세트에 없는 비행 탑승 상태가 목록으로 나온다.
이렇게 얻은 목록을 사용자에게 주고, 실제 규약 파일은 사용자가 확정한 뒤에 고친다.

## 분야별 스킬과의 관계

이 스킬은 연결만 본다. 각 분야의 만드는 방법은 해당 스킬이 다룬다.

| 규약 항목 | 만드는 방법을 다루는 스킬 |
|---|---|
| `parts`, `slots` | `ue-character-parts` |
| `anim_sets`, `ik_profiles` | `ue-animation-ik` |
| `movement_modes`, `mounts`, `characters` | `ue-mount-flight` |
| `vfx` | `ue-vfx-niagara` |
| `weather` | `ue-weather` |
| `biomes` | `ue-environment-worldbuilding` |

## 주의

- 규약은 에셋이 실제로 있는지 확인하지 않는다. 규약에 적힌 소켓이 스켈레톤 에셋에 정말 있는지는
  에디터에서 확인해야 한다. 에디터 연동 수집 스크립트는 아직 없다.
- 예시의 예산 값과 상태 이름은 임시다. 프로젝트 것으로 바꾼다.
- 검사를 통과시키려고 `required_states`나 예산을 낮추지 않는다. 기준을 바꿔야 하면 사용자에게 묻는다.
