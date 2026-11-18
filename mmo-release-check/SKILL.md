---
name: mmo-release-check
description: Verifies before a release or patch that the client build and the custom server build of the MMORPG contain the same protocol definitions, game data tables and map versions, that the build number and protocol version were raised when contents changed, and that the check pipeline passed - and provides release, maintenance, hotfix and rollback checklists for live operation. Use when preparing a release, patch or hotfix, when a client and server mismatch is suspected, or when asked about 릴리스 검사, 패치 절차, 점검, 핫픽스, 롤백, 클라이언트 서버 버전 불일치, 라이브 운영.
---

# 릴리스 일치 검사

클라이언트와 서버는 따로 빌드된다. 둘이 서로 다른 프로토콜 정의나 기획 데이터를 담고 나가면
접속은 되는데 게임이 깨진다. 이 스킬은 두 빌드가 같은 것을 담았는지 해시로 확인한다.
비교와 판정은 `scripts/check_release.py`가 한다.

## 구성

- `scripts/check_release.py`: 순수 Python. 빌드 매니페스트 생성(`make`)과 비교(`compare`).
- `references/release-guide.md`: 매니페스트 형식, 규칙 설명, 릴리스·점검·핫픽스·롤백 체크리스트.

## 절차

1. **빌드마다 매니페스트를 만든다.** 클라이언트 빌드와 서버 빌드가 각자 자기 소스에서 실행한다.

   ```
   python scripts/check_release.py make --name client --build <빌드 번호> --protocol-version <N> \
       --schema-dir <.fbs 폴더> --data-dir <기획 데이터 폴더> --map-versions <map_versions.json> \
       --out client.manifest.json
   ```

2. **비교한다.** 이전 릴리스의 매니페스트와 야간 검사 보고서가 있으면 함께 준다.

   ```
   python scripts/check_release.py compare client.manifest.json server.manifest.json \
       --previous <이전 릴리스의 client.manifest.json> \
       --pipeline-report <mmo-ci-pipeline의 report.json> --out report.json --md report.md
   ```

3. **실패하면 릴리스하지 않는다.** 어느 파일이 다른지 보고서에 나온다. 한쪽 빌드가 옛 소스에서
   만들어진 경우가 대부분이므로, 같은 커밋에서 다시 빌드한다.
4. **통과하면 체크리스트로 넘어간다.** `references/release-guide.md`의 해당 절(릴리스, 핫픽스)을 읽고
   남은 항목을 사용자와 확인한다.
5. **릴리스한 매니페스트를 보관한다.** 다음 릴리스의 `--previous`와 롤백 판단에 쓴다.

## 주의

- 이 검사는 "같은 입력에서 빌드되었는가"를 본다. 빌드 결과물(실행 파일, 패키지) 자체를 검증하지 않는다.
- 매니페스트를 손으로 고쳐 검사를 통과시키지 않는다. 내용이 다르면 다시 빌드한다.
- 체크리스트의 항목(공지, 백업, 점검 시간)은 사람이 확인하는 것이다. 확인하지 않은 항목을 완료로
  표시하지 않는다.
- 실제 배포, 서버 재시작, 데이터베이스 변경은 이 스킬의 범위가 아니다. 요청받아도 절차를 안내할 뿐
  직접 실행하지 않는다.
