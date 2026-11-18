---
name: ue-environment-worldbuilding
description: Guides environment asset creation and placement for the Unreal Engine 5.8 MMORPG - terrain choice (Landscape vs the experimental Mesh Terrain), vegetation with the experimental Procedural Vegetation Editor and Nanite Foliage, rule-based placement with PCG and hand placement for landmarks, World Partition streaming and HLOD, biome density budgets, and what must stay in sync with the custom server (collision and navigation data). Use when creating terrain, foliage, rocks, buildings, biomes, placing environment assets, or when asked about 배경 에셋, 배경 배치, 지형, 식생, PCG, 월드 빌딩, 바이옴, 레벨 디자인 배치.
---

# 배경 에셋 제작과 배치

## 구성

- `references/environment-guide.md`: 기술 선택(5.8 기준), 제작 규칙, 배치 방법, 스트리밍, 서버 데이터 동기화, 확장 지점, 체크리스트.

## 절차

1. **`references/environment-guide.md`를 읽는다.** 1절의 상태 표를 먼저 본다. 5.8의 새 기능 중 여러 개가
   Experimental이다.
2. **에셋을 만들거나 가져왔으면** `ue-asset-spec-check`로 규격을 검사한다.
3. **바이옴이나 배치 밀도를 바꿨으면** 규약의 `biomes`를 고치고 `ue-client-contract`의 검사기를 돌린다.
4. **지형이나 충돌이 바뀌는 배치면** 서버용 내비메시와 충돌 데이터를 다시 내보내야 한다고 알린다.
   이 프로젝트는 자체 서버라서 맵 변경이 서버에 자동으로 반영되지 않는다.
5. **배치 후 성능을 잰다.** `ue-perf-budget-check`의 필드 이동 장면으로 확인한다.

## 주의

- Experimental 기능(Mesh Terrain, Procedural Vegetation Editor)을 본 제작에 쓰자고 제안할 때는
  상태와 위험(버전 간 에셋 비호환 사례)을 함께 말한다.
- PCG 그래프의 노드 이름을 기억에 의존해 단정하지 않는다. Epic의 City Sample(5.8)과 공식 문서로 확인한다.
- 에디터를 직접 조작하는 배치 작업은 Epic의 `unreal-mcp` 스킬로 한다. 이 스킬은 무엇을 어떤 기준으로
  배치할지를 다룬다.
