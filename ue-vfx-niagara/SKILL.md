---
name: ue-vfx-niagara
description: Guides real-time VFX with Niagara for the Unreal Engine 5.8 MMORPG - effect categories and budgets, scalability with Niagara Effect Types, pooling, Niagara Data Channels for many small events, CPU vs GPU simulation, attaching effects to part and mount sockets, reducing other players' effects in crowded scenes, and weather and environment effects. Use when creating or reviewing skill effects, hit effects, part or mount effects, ambient effects, or when asked about VFX, 이펙트, 나이아가라, 파티클, 스킬 이펙트, 이펙트 최적화.
---

# VFX (Niagara)

## 구성

- `references/vfx-guide.md`: 분류와 예산, 확장성 설정(5.8 기준), 부착 규칙, 다수 플레이어 대응, 체크리스트.

## 절차

1. **`references/vfx-guide.md`를 읽는다.**
2. **이펙트를 분류한다.** 모든 이펙트는 가이드 1절의 분류 중 하나에 속하고, 분류가 예산과 확장성
   설정을 정한다. 분류 없이 만들지 않는다.
3. **파츠나 탈것에 붙는 이펙트면** 규약의 `vfx`에 등록하고 붙는 쪽(`parts.vfx`, `mounts.vfx`)에
   소켓과 함께 적은 뒤 `ue-client-contract`의 검사기를 돌린다.
4. **성능을 확인한다.** 대규모 전투 장면에서 `ue-perf-budget-check`로 측정한다. 이펙트 하나를
   빈 맵에서 본 결과로 판단하지 않는다.

## 주의

- Niagara의 모듈 이름과 설정 이름을 기억에 의존해 단정하지 않는다. 구현 전에 에디터나 공식 문서로 확인한다.
- 내 스킬 이펙트가 멋있는 것과 50명이 동시에 쓸 때 화면이 보이는 것은 다른 문제다. 둘 다 본다.
- 이펙트는 게임 판정에 쓰지 않는다. 피격 판정은 서버가 하고, 이펙트는 결과를 보여 줄 뿐이다.
