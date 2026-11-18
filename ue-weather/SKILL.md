---
name: ue-weather
description: Guides the weather system for the Unreal Engine 5.8 MMORPG with a custom server - server-decided weather states per region, data-driven parameters blended on the client (rain, snow, wind, fog, wetness, snow cover), Niagara precipitation, volumetric clouds and fog, wind-reactive vegetation, surface wetness and snow in materials, indoor handling, and gameplay links such as weather that blocks flying. Use when designing or implementing weather, time of day interaction, rain or snow effects, or when asked about 날씨, 비, 눈, 폭풍, 안개, 바람, 날씨 효과, 젖은 표면.
---

# 날씨

## 구성

- `references/weather-guide.md`: 구조, 파라미터, 구성 요소별 구현(5.8 기준), 게임플레이 연결, 확장 지점, 체크리스트.

## 절차

1. **`references/weather-guide.md`를 읽는다.**
2. **날씨는 데이터로 정의한다.** 날씨 상태, 전환, 파라미터는 규약의 `weather`에 적는다.
   날씨를 추가/변경하면 `ue-client-contract`의 검사기를 돌린다.
3. **파라미터를 추가할 때는 모든 날씨에 값을 넣는다.** 하나라도 빠지면 전환 중에 값이 튄다(`LINK009`).
4. **게임플레이에 영향을 주는 날씨면**(비행 금지, 미끄러움) 서버가 판정한다는 점을 설계에 넣고,
   막힌 이동 모드에서 빠져나올 전환이 있는지 검사기 결과(`LINK010`)로 확인한다.

## 주의

- 날씨 상태는 서버가 정해 알려 준다. 클라이언트가 스스로 날씨를 바꾸면 같은 곳의 플레이어들이 서로
  다른 날씨를 본다.
- 렌더링 기능의 설정 이름을 기억에 의존해 단정하지 않는다. 5.8에서 새로 들어온 기능은 Experimental인
  것이 있으므로 가이드의 상태 표를 확인한다.
- 날씨는 화면 전체에 걸리는 비용이다. 마을 장면과 겹쳤을 때의 프레임을 `ue-perf-budget-check`로 잰다.
