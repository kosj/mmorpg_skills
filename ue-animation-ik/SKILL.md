---
name: ue-animation-ik
description: Guides character animation and IK for the Unreal Engine 5.8 MMORPG - Motion Matching with Pose Search and Choosers, the experimental Unreal Animation Framework (UAF), retargeting with IK Rig and IK Retargeter, runtime IK with Control Rig (foot placement, Full Body IK, rider hand and foot IK), animation set structure per movement mode, and animation cost control for crowds. Use when building locomotion, animation sets, retargeting between body types, foot or hand IK, riding poses, or when asked about 애니메이션, 모션 매칭, IK, 발 배치, 리타기팅, 컨트롤 릭, 애니메이션 세트.
---

# 애니메이션과 IK

## 구성

- `references/animation-ik-guide.md`: 기술 선택(5.8 기준), 애니메이션 세트 구조, IK 규칙, 다수 캐릭터 비용, 체크리스트.

## 절차

1. **`references/animation-ik-guide.md`를 읽는다.** 1절의 기술 선택 표로 방식을 정한다.
2. **상태 이름은 규약을 따른다.** 애니메이션 상태 이름(`idle`, `fly_move`, `ride_idle` 등)은
   `ue-client-contract`의 `movement_modes`가 정한다. 새 이름을 만들지 말고 규약에 있는 이름을 쓴다.
   새 상태가 필요하면 규약의 이동 모드에 먼저 추가한다.
3. **애니메이션 세트를 추가/변경했으면** 규약의 `anim_sets`를 고치고 검사기를 돌린다.
   `LINK003`이 남아 있으면 그 상태의 애니메이션이 아직 없는 것이다.
4. **IK를 다룰 때는** 가이드 3절을 따른다. 이동 모드마다 IK를 켜고 끄는 기준이 다르다.

## 주의

- UAF와 Mover는 5.8에서 Experimental이다. 이들을 전제로 한 구조를 제안할 때는 상태를 밝히고,
  안정된 대안(Anim Blueprint, Character Movement Component)을 함께 제시한다.
- 애니메이션 그래프의 노드 이름과 API를 기억에 의존해 단정하지 않는다. Epic의 Game Animation Sample
  (5.8)과 공식 문서로 확인한다.
- 내 캐릭터 한 명 기준으로 판단하지 않는다. 다른 플레이어에게 같은 비용을 쓸 수 없다.
