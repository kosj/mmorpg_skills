---
name: mmo-protocol-check
description: Checks the game protocol defined in FlatBuffers schemas (.fbs) for an MMORPG with a custom C++ server and Unreal client - duplicate or reused packet IDs, missing packet ID or direction, client-to-server packets that carry result values such as damage or gold, unbounded strings and vectors, missing rate limits, and changes that break compatibility with the previous version (removed or reordered fields, changed structs or enum values). Also generates a C++ header with packet IDs, rate limits and length limits. Use when adding or changing packets, reviewing .fbs files, before generating code with flatc, or when asked about 패킷 정의, 프로토콜 검사, 패킷 ID, 호환성, fbs, FlatBuffers.
---

# 프로토콜 검사 (FlatBuffers)

`.fbs` 스키마가 프로젝트의 프로토콜 규칙을 지키는지 검사한다. flatc는 문법만 보므로,
이 스킬은 flatc가 보지 않는 것(패킷 번호 관리, 클라이언트 입력의 안전성, 버전 간 호환)을 본다.
판정은 전부 `scripts/check_protocol.py`가 한다.

## 구성

- `scripts/check_protocol.py`: 순수 Python. 검사, lock 갱신, C++ 헤더 생성.
- `references/protocol-config.json`: 접두사, ID 범위, 의심 단어, 심각도.
- `references/rules.md`: 규칙별 의미와 수정 방법, 호환되는 변경 표, 오탐 처리.
- `references/protocol-guide.md`: 패킷 정의 규칙, 프레이밍, Verifier, 빌드 연동, 변경 절차.
- `references/example/game.fbs`: 규칙을 지킨 예시 스키마.

## 패킷을 검사할 때

1. **검사한다.** lock 파일은 스키마 폴더에 있는 것을 쓴다.

   ```
   python scripts/check_protocol.py <스키마 폴더> --config references/protocol-config.json \
       --lock <스키마 폴더>/protocol.lock.json --out report.json --md report.md
   ```

2. **error부터 처리한다.** `PROTO003`과 `PROTO007`은 이미 배포된 클라이언트와 어긋나는 변경이다.
   고치는 방법은 `references/rules.md`의 호환 표를 읽고 정한다.
3. **`PROTO004`는 필드의 용도를 확인한다.** 이름만 보고 낸 경고다. 서버가 그 값을 계산에 쓰는
   것이면 필드를 없애는 수정을 제안하고, 아니면 `protolint:ignore`와 이유를 제안한다.
4. **통과하면 lock과 헤더를 갱신한다.** 사용자가 변경을 확정했을 때만 한다.

   ```
   python scripts/check_protocol.py <스키마 폴더> --lock <스키마 폴더>/protocol.lock.json \
       --update-lock --emit-header <생성 폴더>/PacketMeta.generated.h
   ```

   error가 있으면 lock과 헤더는 갱신되지 않는다.
5. **보고한다.** 패킷 수, error 수, 호환성 문제, 보안 경고 순으로 전한다.

## 패킷을 새로 만들 때

`references/protocol-guide.md`의 2절을 읽고 `references/example/game.fbs`의 형식을 따른다.
새 `packet_id`는 lock 파일의 `packets`에 없는 번호로 정한다. 작성 후 위 절차로 검사해
error가 없음을 확인하고 전달한다.

## 주의

- lock 파일을 손으로 고치거나 지워서 검사를 통과시키지 않는다. 호환을 깨야 하는 상황이면
  사용자에게 알리고 `references/protocol-guide.md` 6절의 절차를 따른다.
- 이 검사기는 FlatBuffers 문법의 일부만 해석한다. 문법이 맞는지는 flatc로 확인한다.
  예시 스키마도 flatc로 컴파일해 확인한 것이 아니다.
- `max_len`과 `rate`는 스키마에 적는다고 적용되지 않는다. 서버 코드가 생성된 헤더의 값을 써야 한다.
- 검사 통과가 "서버가 안전하다"는 뜻은 아니다. 핸들러의 검증은 `mmo-netcode-review`로 본다.
