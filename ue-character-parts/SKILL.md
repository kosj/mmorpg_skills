---
name: ue-character-parts
description: Guides modular character assembly for the Unreal Engine 5.8 MMORPG - choosing between Mutable (Customizable Objects, Production-Ready in 5.8), Leader Pose components and socket attachments, structuring slots, body types and part data, hiding covered body regions, handling many customized players on screen, and making parts work with mounts and effects. Use when designing or implementing character customization, equipment appearance, costume or armor parts, dyes, body types, or when asked about 파츠 조립, 캐릭터 커스터마이징, 장비 외형, Mutable, 코스튬, 염색.
---

# 캐릭터 파츠 조립

장비와 코스튬을 조합해 캐릭터 외형을 만드는 방법을 다룬다.

## 구성

- `references/parts-guide.md`: 기술 선택(5.8 기준), 데이터 구조, 다수 캐릭터 대응, 확장 지점, 체크리스트.

## 절차

1. **`references/parts-guide.md`를 읽는다.** 기술 선택 표에서 질문에 해당하는 방식을 고른다.
2. **프로젝트 결정을 확인한다.** 아트 스타일과 체형 수는 `mmorpg-router/references/project-context.md`에
   있다. 미정이면 가정을 밝힌다.
3. **파츠를 추가/변경하는 작업이면** 규약 데이터(`parts`, `slots`)를 함께 고치고
   `ue-client-contract`의 검사기를 돌린다. 파츠 메시 자체의 규격은 `ue-asset-spec-check`로 본다.
4. **구현 코드를 작성할 때는** 가이드 4절(다수 캐릭터 대응)의 규칙을 지킨다. 외형 생성은 비동기이고
   비용이 크므로, 요청을 한곳에서 줄 세워 처리하는 구조로 만든다.

## 주의

- 기능 상태(Production-Ready, Experimental)는 5.8 기준으로 조사한 것이다. 엔진 패치 버전이 다르면
  공식 문서로 다시 확인한다.
- Mutable의 노드 이름과 C++ API를 기억에 의존해 단정하지 않는다. 구현 전에 엔진 소스나 공식 문서,
  Epic의 Mutable Sample을 확인한다.
- 다른 플레이어 수백 명이 보이는 장면이 기준이다. 캐릭터 한 명에서 잘 되는 것으로 판단하지 않는다.
