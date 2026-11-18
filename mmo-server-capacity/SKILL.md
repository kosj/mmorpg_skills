---
name: mmo-server-capacity
description: Estimates MMORPG server capacity from a scenario file - per-client bandwidth, per-server egress, number of zone server processes, entity updates per second, monthly traffic, and the effect of an area-of-interest cap in crowded scenes - and explains server architecture options (shards, zones, single world, backend services, persistence). Use when planning server architecture, sizing zone servers, discussing concurrent user targets, crowd scenes such as towns and sieges, or when asked about 서버 구조, 동시 접속, 존 서버, 채널, 대역폭, 서버 비용, 공성전 인원.
---

# MMORPG 서버 용량과 구조

서버 구조 질문에는 선택지와 판단 기준으로 답하고, 수치가 필요하면 스크립트로 계산한다.
대역폭이나 서버 수를 머릿속으로 계산해 말하지 않는다.

## 구성

- `scripts/capacity_calc.py`: 순수 Python. 시나리오로 대역폭, 서버 수, 갱신량을 계산한다.
- `references/scenario.json`: 입력 시나리오. 전부 임시 가정값이다.
- `references/architecture.md`: 월드 구성 방식, 구성 요소, 저장, 밀집 상황 대응, 계산 모델의 한계.

## 수치를 물을 때

1. **입력을 확인한다.** 사용자가 준 값(목표 동시 접속, 서버 정원, 보이는 인원 상한 등)으로
   `references/scenario.json`의 복사본을 만든다. 사용자가 주지 않은 값은 기본값을 쓰고,
   어떤 값이 가정인지 답에 적는다.
2. **계산한다.**

   ```
   python scripts/capacity_calc.py <scenario.json> --out report.json --md report.md
   ```

3. **보고한다.** 필요한 서버 프로세스 수, 밀집 상황의 클라이언트 수신량과 서버 송신량,
   지적 사항 순으로 전한다. 항상 "어림값이며 부하 테스트로 확인해야 한다"는 말을 붙인다.
4. **비교를 요청받으면** 값만 바꾼 시나리오를 여러 개 만들어 각각 돌리고 표로 비교한다.
   예: 보이는 플레이어 상한 40 / 60 / 100.

## 구조를 물을 때

`references/architecture.md`를 읽는다. 답하기 전에 1절의 "먼저 정해야 할 것"이
`mmorpg-router/references/project-context.md`에 정해져 있는지 확인한다.
미정이면 선택지를 비교해 주고, 어느 쪽인지 정해지면 기록하라고 권한다. 임의로 정해서 답하지 않는다.

## 주의

- 서버 정원(`players_per_server_cap`)은 이 스크립트가 구해 주지 않는다. 입력값이다.
  실제 한계는 서버 CPU가 정하며, 봇 부하 테스트로만 확인된다.
- `CAP004`(초당 갱신량)는 CPU 부담의 간접 지표일 뿐이다.
- 패킷 크기(`bytes_per_*`)는 프로토타입이 생기면 실측값으로 바꾼다. 언리얼에서는 네트워크
  프로파일러나 `stat net`으로 볼 수 있다.
