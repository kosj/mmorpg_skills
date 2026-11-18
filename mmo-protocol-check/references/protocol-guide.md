# 프로토콜 작성 가이드 (FlatBuffers, C++ 서버 + 언리얼 클라이언트)

패킷을 새로 정의하거나 프로토콜 구조를 설계할 때 읽는다.

## 목차

1. 파일 구성
2. 패킷 정의 규칙
3. 프레이밍
4. 받은 버퍼 다루기
5. 빌드 연동
6. 변경 절차

## 1. 파일 구성

- `.fbs` 파일은 한 폴더에 모으고 클라이언트와 서버가 같은 폴더를 참조한다. 복사본을 두지 않는다.
- 기능별로 파일을 나눈다(`common.fbs`, `move.fbs`, `combat.fbs`, `inventory.fbs`, `chat.fbs`).
- 사용자 속성 선언(`attribute "packet_id";` 등)은 `common.fbs`에 두고 다른 파일이 include한다.
- `protocol.lock.json`을 같은 폴더에 두고 소스 컨트롤에 넣는다.

## 2. 패킷 정의 규칙

- 패킷 하나가 table 하나다. 이름은 `C2S_`(클라이언트→서버) 또는 `S2C_`(서버→클라이언트)로 시작한다.
- 모든 패킷에 `(packet_id: N)`을 붙인다. 번호 대역을 나눠 두면 찾기 쉽다(예: 1000번대 C2S, 2000번대 S2C).
- 한번 쓴 번호는 패킷을 지워도 다시 쓰지 않는다.
- 클라이언트→서버 패킷:
  - `(rate: N)`으로 초당 허용 횟수를 적는다.
  - 문자열과 배열에 `(max_len: N)`을 붙인다.
  - 결과 값을 담지 않는다. 의도만 담는다.
- 좌표처럼 고정된 작은 묶음은 struct, 나머지는 table로 만든다.
- 필드를 지우지 않는다. `(deprecated)`로 표시한다. 새 필드는 맨 끝에 추가한다.
- 자주 보내는 패킷은 타입을 좁힌다: 각도는 `short`, 플래그는 `ubyte` 비트, ID가 작으면 `uint`.

`packet_id`, `dir`, `rate`, `max_len`은 프로젝트가 정한 사용자 속성이다. flatc는 이 값을 강제하지 않는다.
`check_protocol.py`가 검사하고, `--emit-header`로 만든 헤더를 통해 서버 코드가 적용한다.

## 3. 프레이밍

FlatBuffers는 메시지 경계와 종류를 알려 주지 않는다. 앞에 헤더를 붙인다.

```
[ 크기 uint16 ][ packet_id uint16 ][ FlatBuffers 버퍼 ... ]
```

- 수신 측은 크기를 먼저 읽고, 상한(예: 클라이언트→서버 4KB)을 넘으면 접속을 끊는다.
- `packet_id`가 `PacketMeta::Find`에 없거나 방향이 맞지 않으면 버린다.
- 스트림 전송(TCP)은 패킷이 쪼개지거나 붙어서 온다. 크기만큼 모일 때까지 기다렸다가 처리한다.
- 프로토콜 버전은 접속 직후 첫 패킷으로 교환하고, 맞지 않으면 접속을 거부한다.

## 4. 받은 버퍼 다루기

- **서버는 받은 버퍼를 반드시 Verifier로 검사한 뒤 읽는다.** FlatBuffers는 버퍼 안의 오프셋을 따라가며
  읽으므로, 조작된 버퍼를 검사 없이 읽으면 메모리 범위를 벗어난다.

  ```cpp
  flatbuffers::Verifier Verifier(Data, Size);
  if (!Verifier.VerifyBuffer<Game::Protocol::C2S_UseSkill>(nullptr)) { /* 버리고 위반 횟수 증가 */ }
  ```

- Verifier는 구조만 본다. 값의 의미(범위, 소유, 쿨다운)는 핸들러가 검사한다.
- Verifier 통과 후 `max_len`을 검사한다: `PacketMeta::MaxLen::C2S_Chat_text`.
- 필드는 없을 수 있다. 문자열, 배열, 중첩 table 접근자는 널을 돌려줄 수 있으므로 확인하고 쓴다.
- 받은 버퍼를 가리키는 포인터를 핸들러 밖에 보관하지 않는다. 필요한 값은 복사한다.
- 클라이언트도 서버에서 받은 버퍼를 Verifier로 검사한다. 개발 중 버전 불일치를 빨리 잡는다.

## 5. 빌드 연동

- flatc로 C++ 코드를 생성하고, 생성물은 소스 컨트롤에 넣지 않거나 넣더라도 손으로 고치지 않는다.
- 언리얼 쪽: FlatBuffers C++ 런타임은 헤더만으로 동작하므로 모듈의 `ThirdParty` 폴더에 include 경로만
  추가하면 된다. 생성된 헤더를 포함하는 부분은 `THIRD_PARTY_INCLUDES_START` / `END`로 감싼다.
- 서버와 클라이언트가 같은 flatc 버전을 쓴다. 버전을 저장소에 고정한다.
- `check_protocol.py`를 flatc 실행 전에 돌린다. 실패하면 코드 생성을 하지 않는다.

## 6. 변경 절차

1. `.fbs`를 고친다.
2. `check_protocol.py --lock protocol.lock.json`으로 검사한다.
3. 통과하면 `--update-lock --emit-header`로 lock과 헤더를 갱신한다.
4. flatc로 코드를 다시 생성하고 클라이언트와 서버를 함께 빌드한다.
5. `.fbs`, lock, 양쪽 코드 변경을 한 커밋으로 올린다.

호환을 깨는 변경이 꼭 필요하면(출시 전 대규모 정리 등) 프로토콜 버전을 올리고, lock 파일을
지운 뒤 다시 만든다. 이 경우 옛 클라이언트는 접속할 수 없게 된다는 점을 변경 설명에 적는다.
