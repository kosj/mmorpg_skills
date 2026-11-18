# 규칙 설명과 수정 방법

| ID | 의미 | 고치는 방법 |
|---|---|---|
| NET001 | `Replicated` 프로퍼티가 `GetLifetimeReplicatedProps`에 등록되지 않았다 | 해당 클래스의 `GetLifetimeReplicatedProps`에 `DOREPLIFETIME(클래스, 멤버)` 추가. 소유자만 봐야 하면 `DOREPLIFETIME_CONDITION(..., COND_OwnerOnly)` |
| NET002 | `ReplicatedUsing=OnRep_X`인데 `OnRep_X` 선언이 없다 | 같은 클래스에 `UFUNCTION() void OnRep_X();` 선언과 구현 추가 |
| NET003 | `Reliable` `NetMulticast` | 이펙트, 사운드, 피격 연출은 `Unreliable`로. 반드시 전달되어야 하는 상태는 RPC가 아니라 복제 프로퍼티로 옮긴다 |
| NET004 | `Server` RPC에 `WithValidation`이 없다 | 위반은 아니다. 구현부 첫머리에서 대상 유효성, 거리, 쿨다운, 소유권을 검사하는지 확인한다 |
| NET005 | `Server` RPC가 결과 값(피해량, 골드, 경험치 등)을 인자로 받는다 | 클라이언트는 "무엇을 하려는지"만 보낸다(스킬 ID, 대상). 수치는 서버가 자기 데이터로 계산한다 |
| NET006 | `TArray`를 복제한다 | 인벤토리, 버프 목록처럼 크거나 자주 바뀌면 `FFastArraySerializer`로 바꿔 바뀐 항목만 보낸다. 작고 드물게 바뀌면 그대로 둔다 |

## NET005 예시

나쁜 예: 클라이언트가 피해량을 정한다. 패킷을 조작하면 원하는 피해를 줄 수 있다.

```cpp
UFUNCTION(Server, Reliable)
void ServerDealDamage(AActor* Target, float Damage);
```

좋은 예: 클라이언트는 의도만 보내고, 서버가 검증하고 계산한다.

```cpp
UFUNCTION(Server, Reliable)
void ServerUseSkill(int32 SkillId, AActor* Target);
// 구현부: 스킬 보유 여부, 쿨다운, 사거리, 시야를 서버 데이터로 확인한 뒤 피해량을 서버가 계산
```

## 오탐 처리

정규식 기반이라 틀릴 수 있다. 의도한 코드라면 그 줄이나 바로 윗줄에 이유와 함께 적는다.

```cpp
// netlint:ignore NET003 보스 페이즈 전환은 모든 클라이언트에 반드시 도착해야 함
UFUNCTION(NetMulticast, Reliable)
void MulticastPhaseChange(int32 Phase);
```

의심 단어 목록은 `lint-config.json`의 `authoritative_param_tokens`에서 조정한다.
단어는 CamelCase 단위로 비교한다(`NewHP`의 `hp`는 걸리고 `ExpectedIndex`의 `exp`는 걸리지 않는다).

## 이 검사기가 보지 못하는 것

- 블루프린트로 만든 RPC와 복제 설정
- RPC가 Tick에서 매 프레임 호출되는지 여부
- 구현부의 검증 로직이 충분한지 여부
- NetUpdateFrequency, 도먼시, 관련성 설정

이 항목들은 `netcode-guide.md`의 체크리스트로 사람이 리뷰한다.
