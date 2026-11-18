# 애니메이션과 IK 가이드 (UE 5.8)

## 목차

1. 기술 선택
2. 애니메이션 세트 구조
3. IK 규칙
4. 다수 캐릭터 비용
5. 확장 지점
6. 체크리스트
7. 참고 자료

## 1. 기술 선택

| 기술 | 5.8 상태 | 용도 | 판단 |
|---|---|---|---|
| Motion Matching (Pose Search) | Production-Ready | 이동 애니메이션을 상태 머신 없이 데이터베이스에서 골라 재생 | 내 캐릭터와 가까운 캐릭터의 지상 이동에 쓴다. Character Movement Component 위에서도 동작한다 |
| Chooser | 사용 가능 | 조건(이동 모드, 탑승 여부, 무기)에 따라 애니메이션이나 데이터베이스를 고르는 표 | 이동 모드별 애니메이션 세트 선택에 쓴다. 규약의 `movement_modes`와 1:1로 맞춘다 |
| Anim Blueprint | 안정 | 애니메이션 그래프 | 현재의 기반. UAF가 안정될 때까지 유지한다 |
| Unreal Animation Framework (UAF) | Experimental | Anim Blueprint의 후속 | 5.8의 Game Animation Sample에 UAF 캐릭터가 포함되었다. 평가용으로만 쓴다 |
| IK Rig + IK Retargeter | 안정 | 스켈레톤 간 애니메이션 공유 | 체형이나 종족이 여럿이면 필수. 탑승 애니메이션을 체형마다 새로 만들지 않기 위해 쓴다 |
| Control Rig (런타임) | 안정 | 발 배치, 손 위치 보정, 조준 등 절차적 보정 | 발 배치 Control Rig 노드가 5.7에 추가되었다. Full Body IK도 Control Rig 노드다 |
| Modular Control Rig | 5.8에서 안정성 개선 | 리그 모듈 조립 | 탈것 등 새 스켈레톤의 리그를 빠르게 만들 때 |
| Direct Mesh Controls (DMC) | Experimental | 메시 위에 직접 컨트롤 배치 | 제작 도구. 런타임 구조와 무관 |

UE 5.8은 UE5의 마지막 주요 버전으로 예고되었다. UAF와 Mover는 UE6 방향이므로, 지금은 안정된
기술로 만들되 **애니메이션 데이터(세트, 상태 이름)를 그래프 기술과 분리**해 두면 나중에 옮기기 쉽다.

## 2. 애니메이션 세트 구조

- 세트 하나는 "스켈레톤 하나가 어떤 상태들을 재생할 수 있는가"다.
- 필요한 상태는 이동 모드가 정한다. 예: `fly` 모드는 `takeoff`, `fly_idle`, `fly_move`, `fly_land`.
- 탑승자 세트는 탈것 종류별로 둔다(말 탑승, 그리핀 탑승). 앉는 자세와 고삐 위치가 다르기 때문이다.
- 탈것은 자기 스켈레톤의 세트를 갖는다. 탑승자와 탈것은 같은 상태 변화에 맞춰 각자 재생한다.
  예: 이륙 시 탈것은 `takeoff`, 탑승자는 `ride_takeoff`.
- 전환은 상태 이름으로 요청하고, 어떤 클립을 쓸지는 Chooser가 정한다. 코드에 클립을 직접 넣지 않는다.
- 스킬 애니메이션처럼 이동과 무관한 것은 상체 레이어나 몽타주로 얹는다. 탑승 중에 쓸 수 있는
  스킬이면 탑승 자세 위에 얹을 수 있게 만든다.

## 3. IK 규칙

| 상황 | 발 IK | 손 IK | 비고 |
|---|---|---|---|
| 지상 이동 | 켬 | 무기 잡는 손만 | 경사와 계단에서 발을 지면에 맞추고 골반 높이를 조정 |
| 수영, 활공, 비행 | 끔 | 끔 | 공중에서 발 IK를 켜면 발이 아래 지면을 찾아 늘어난다. 규약의 `LINK007`이 검사한다 |
| 탑승 | 끔 (등자에 고정) | 고삐 소켓에 고정 | 탈것의 `rider_ik_sockets`로 손발을 붙인다. 체형과 갑옷 부피 차이를 흡수한다 |
| 탈것(네발) | 켬 | 해당 없음 | 네 발 각각 지면에 맞추고 몸통 기울기를 경사에 맞춘다 |
| 이착륙 전환 | 서서히 켜고 끔 | 유지 | IK를 한 프레임에 켜고 끄면 튄다. 전환 길이에 맞춰 섞는다 |

- 발 IK는 지면 검사(트레이스)가 필요하다. 캐릭터 수만큼 매 프레임 쏘면 비싸므로 가까운 캐릭터만 한다.
- Full Body IK는 목표에 완전히 닿지 않거나 몸이 뜨는 사례가 보고되어 있다. 발 배치에는 전용 노드나
  두 본 IK와 골반 보정 조합을 먼저 쓰고, 전신 자세가 필요한 곳에만 Full Body IK를 쓴다.
- 리타기팅한 애니메이션은 손발 위치가 어긋날 수 있다. 등반, 탑승처럼 접촉이 중요한 동작은 IK로 보정한다.

## 4. 다수 캐릭터 비용

| 거리/중요도 | 애니메이션 | IK | 갱신 |
|---|---|---|---|
| 내 캐릭터 | Motion Matching | 전부 | 매 프레임 |
| 가까운 캐릭터 | Motion Matching 또는 단순 블렌드 | 발 IK만 | 매 프레임 |
| 중간 거리 | 단순 블렌드 | 끔 | 몇 프레임에 한 번 |
| 먼 거리 | 최소 포즈 | 끔 | 드물게 |

- 갱신 빈도 조절과 예산 할당 기능(Update Rate Optimization, Animation Budget Allocator)을 쓴다.
- 화면 밖 캐릭터는 포즈 갱신을 멈춘다.
- 군중 NPC는 플레이어 캐릭터와 다른 경로로 만든다. 5.8의 MetaHuman Crowd와 Mass 기반 군중은
  Experimental이다.
- 기준은 `ue-perf-budget-check`의 마을과 대규모 전투 장면이다. 게임 스레드 예산을 애니메이션이 얼마나
  쓰는지 측정해 단계 거리를 정한다.

## 5. 확장 지점

- **새 이동 모드:** 규약에 모드와 필요한 상태를 적는다. 검사기가 세트별로 빠진 상태를 알려 준다.
- **새 체형/종족:** 스켈레톤이 다르면 IK Rig와 리타게터를 만들고, 기존 세트를 리타기팅해 새 세트로
  등록한다. 탑승자 세트도 필요하다. 규약의 연결 표에서 그 체형이 탈 수 있는 탈것을 확인한다.
- **새 탈것:** 탈것 스켈레톤의 세트와 IK 프로필, 좌석 소켓, 탑승자 세트가 필요하다.
- **새 무기 종류:** 이동 세트는 그대로 두고 상체 레이어와 Chooser 조건을 추가한다.

## 6. 체크리스트

- [ ] 상태 이름이 규약의 `movement_modes`와 일치한다
- [ ] 클립 선택이 Chooser나 데이터에 있고 코드에 하드코딩되지 않았다
- [ ] 공중/수영 모드에서 발 IK가 꺼진다
- [ ] IK를 켜고 끌 때 섞는 시간이 있다
- [ ] 탑승자의 손발이 탈것 소켓에 IK로 붙는다
- [ ] 거리별 애니메이션 단계가 정해져 있고 측정값에 근거한다
- [ ] 리타기팅한 세트의 접촉 동작(등반, 탑승)을 눈으로 확인했다
- [ ] 규약 검사(`ue-client-contract`)를 통과했다

## 7. 참고 자료

- Epic, "Explore the updates to the Game Animation Sample Project in UE 5.7" (2025-12-03): UAF가 Anim Blueprint의 후속이며 5.8에서도 Experimental 예정, 발 배치 Control Rig 노드 추가
- Epic, Game Animation Sample Project 5.8 업데이트 공지: UAF로 구성한 캐릭터 포함
- Epic, Unreal Engine 5.8 Release Notes: Modular Control Rig 개선
- Epic 문서, "IK Rig in Unreal Engine": 솔버, 발 정렬 예시
- Epic 포럼, "Control Rig's Full-Body IK not fully reaching its targets", "Full Body IK Node Lifting and Tilting Character Forward": Full Body IK 사용 시 보고된 문제
- 80 Level, "Unreal Engine 5.8 Preview has arrived": DMC (Experimental)
