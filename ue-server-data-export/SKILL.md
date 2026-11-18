---
name: ue-server-data-export
description: Exports and validates the world data a custom C++ game server needs from an Unreal Engine 5.8 map - navigation geometry, spawn points, and volumes such as no-fly zones, safe zones and no-spawn areas - builds a manifest with content hashes and a map version, and checks that the server data matches the map version shipped in the client, that spawns and volumes are valid, and that spawns reference existing monsters. Use after changing terrain, collision, placement, spawn points or volumes in a level, before a server or client build, or when asked about 서버 맵 데이터, 내비메시 내보내기, 스폰 지점, 비행 금지 구역, 맵 버전 불일치.
---

# 서버용 월드 데이터 내보내기

자체 서버는 언리얼 맵을 읽지 못한다. 맵이 바뀌면 서버가 쓰는 데이터를 다시 내보내야 하고,
클라이언트와 서버가 같은 맵 상태를 보고 있는지 확인해야 한다. 어긋나면 벽을 통과하거나
허공에 몬스터가 선다.

## 구성

- `scripts/collect_level_data.py`: 에디터 안에서 실행. 스폰 지점, 볼륨, 월드 범위를 JSON으로 내보낸다.
- `scripts/check_world_data.py`: 순수 Python. 묶음의 manifest를 만들고(`build`) 검사한다(`check`).
- `references/world-data-guide.md`: 내보내는 방법, 파일 형식, 액터 태그 규칙, 규칙 설명, 서버 쪽 사용법.
- `references/world-data-config.json`: 필수 데이터 종류, 스폰/볼륨 종류, 심각도.

## 절차

1. **내보낸다.** 에디터에서 두 가지를 같은 폴더에 만든다. 방법은 `references/world-data-guide.md` 2절.
   - 내비 지오메트리 `nav.obj`
   - `collect_level_data.py`가 만드는 `spawns.json`, `volumes.json`, `bounds.json`
2. **묶는다.** 맵 버전이 계산되고 클라이언트용 버전 파일이 갱신된다.

   ```
   python scripts/check_world_data.py build <내보내기 폴더> --map <맵 이름> \
       --client-versions <클라이언트 콘텐츠>/map_versions.json
   ```

3. **검사한다.**

   ```
   python scripts/check_world_data.py check <내보내기 폴더> \
       --client-versions <클라이언트 콘텐츠>/map_versions.json \
       --monsters-csv <기획 데이터>/monsters.csv --out report.json --md report.md
   ```

4. **보고한다.** 통과 여부, 맵 버전, 지적 사항 순으로 전한다. `WORLD004`(버전 불일치)는
   "맵을 고친 뒤 내보내기를 다시 하지 않았다"는 뜻이므로 가장 먼저 알린다.
5. **서버 데이터와 클라이언트 버전 파일을 같은 커밋으로 올리게 한다.** 따로 올리면 그 사이의
   빌드가 어긋난다.

## 맵 변경 요청을 받았을 때

지형, 충돌이 있는 에셋, 스폰 지점, 볼륨을 바꾸는 작업을 했다면 끝에 이 스킬의 절차를 돌려야 한다고
알린다. 에디터에 접근할 수 없어 1단계를 할 수 없으면, 어떤 맵을 다시 내보내야 하는지 적어 전한다.

## 주의

- `collect_level_data.py`는 에디터에서 실행해 검증하지 않았다. 결과의 `skipped`에 액터가 많이 나오면
  5.8의 Python API에 맞게 고쳐야 한다.
- `nav.obj`는 내비메시 자체가 아니라 걸을 수 있는 지오메트리다. 서버가 같은 에이전트 설정(반지름, 높이,
  경사, 단차)으로 내비메시를 다시 만들어야 클라이언트 에디터에서 본 것과 같아진다.
- 이 검사는 묶음의 온전함과 버전 일치를 본다. 내비메시의 품질(끊긴 길, 좁은 통로)은 보지 않는다.
- 회전된 볼륨은 축에 정렬된 상자로 커져서 나간다. 정밀한 금지 구역이 필요하면 볼륨을 축에 맞춰 배치한다.
- manifest를 손으로 고쳐 검사를 통과시키지 않는다. 내용이 바뀌었으면 `build`를 다시 한다.
