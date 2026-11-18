---
name: ue-mount-flight
description: Guides mounts, riding and flight for the Unreal Engine 5.8 MMORPG with a custom server - movement component choice (Character Movement Component vs the experimental Mover plugin), data-driven movement modes (ground, swim, glide, fly) and their transitions, rider attachment to seat sockets with IK, takeoff and landing flow, flight limits and no-fly conditions such as weather, and how new mounts or movement modes are added without code changes. Use when designing or implementing mounts, riding, gliding, flying, movement mode switching, or when asked about 탈것, 탑승, 비행, 활공, 이동 모드, 이착륙, Mover.
---

# 탈것과 비행

## 구성

- `references/mount-flight-guide.md`: 이동 컴포넌트 선택(5.8 기준), 이동 모드 설계, 탑승 구조, 비행 흐름, 서버 연동, 확장 지점, 체크리스트.

## 절차

1. **`references/mount-flight-guide.md`를 읽는다.**
2. **이동 컴포넌트 결정을 확인한다.** `mmorpg-router/references/project-context.md`에 정해져 있지 않으면
   가이드 1절의 비교를 보여 주고, 임의로 정하지 않는다.
3. **탈것이나 이동 모드를 추가/변경하면** 규약 데이터(`mounts`, `movement_modes`, `characters`)를 고치고
   `ue-client-contract`의 검사기를 돌린다. 나온 지적이 남은 작업 목록이다.
4. **이동 관련 패킷이 필요하면** `mmo-protocol-check`의 규칙으로 정의한다. 클라이언트는 입력과 예측
   위치를 보내고, 모드 전환의 허용 여부는 서버가 정한다.

## 주의

- 이 프로젝트는 자체 서버를 쓴다. 엔진 이동 컴포넌트의 내장 네트워크 동기화는 쓰지 않으므로,
  "네트워크 지원이 좋다"는 이유로 컴포넌트를 고르지 않는다.
- 비행은 서버 검증(속도, 고도, 금지 구역)과 월드 스트리밍 속도에 영향을 준다. 클라이언트 연출만으로
  끝나는 기능으로 다루지 않는다.
- Mover는 5.8에서 Experimental이고 버전마다 API가 바뀐다. Mover 코드를 작성할 때는 해당 엔진 버전의
  소스를 확인한다.
