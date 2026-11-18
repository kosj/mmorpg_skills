# 서버용 월드 데이터 가이드 (UE 5.8, 자체 C++ 서버)

## 목차

1. 서버가 필요한 것
2. 내보내는 방법
3. 파일 형식
4. 액터 태그 규칙
5. 규칙 설명
6. 서버 쪽 사용법
7. 자동화
8. 참고 자료

## 1. 서버가 필요한 것

| 데이터 | 쓰는 곳 | 파일 |
|---|---|---|
| 걸을 수 있는 지오메트리 | 몬스터 길 찾기, 플레이어 이동 검증 | `nav.obj` |
| 스폰 지점 | 몬스터, NPC, 채집물 배치, 플레이어 시작점 | `spawns.json` |
| 볼륨 | 비행 금지, 안전 지대, 스폰 금지, 트리거, 물 | `volumes.json` |
| 월드 범위 | 좌표 검증, 공간 분할 격자 크기 | `bounds.json` |
| 높이/충돌 (선택) | 낙하와 벽 통과 검증을 더 정밀하게 | `collision.obj` |

타겟팅 전투라서 서버는 정밀한 충돌 판정보다 "그 위치에 설 수 있는가", "대상이 시야에 있는가"가 필요하다.
처음에는 내비 지오메트리와 볼륨으로 시작하고, 벽 통과 핵이 문제가 되면 충돌 데이터를 추가한다.

## 2. 내보내는 방법

**내비 지오메트리**

1. 레벨에 내비메시 범위 볼륨을 두고 내비메시를 빌드한다.
2. 에디터 콘솔에서 `ExportNavigation`을 실행한다. 걸을 수 있는 지오메트리가 OBJ로 나온다. 단위는 cm다.
3. 나온 파일을 내보내기 폴더에 `nav.obj`로 둔다.

이 OBJ는 엔진의 내비메시 자체가 아니다. 엔진이 가진 Recast 내비메시 데이터를 그대로 꺼내는 기능은
공식 지원되지 않는다. 방법은 둘이다.

| 방법 | 내용 | 판단 |
|---|---|---|
| OBJ를 서버에서 다시 빌드 | 서버가 Recast로 `nav.obj`에서 내비메시를 만든다 | 엔진 수정이 없다. 에이전트 설정을 엔진과 맞춰야 한다. 권장 |
| 엔진의 내비메시를 직접 저장 | 플러그인이나 엔진 코드로 Detour 데이터를 파일로 쓴다 | 에디터에서 본 것과 정확히 같다. 엔진 버전마다 코드를 유지해야 한다 |

**스폰, 볼륨, 범위**

Unreal MCP의 Python 실행 도구로 `scripts/collect_level_data.py`를 실행한다.

```python
import sys, importlib, unreal
p = unreal.Paths.project_dir() + "Skills/ue-server-data-export/scripts"
if p not in sys.path:
    sys.path.insert(0, p)
import collect_level_data
importlib.reload(collect_level_data)
print(collect_level_data.main())
```

결과는 `<Project>/Saved/ServerWorldData/`에 생긴다. `nav.obj`도 같은 폴더에 둔다.

World Partition 맵은 로드된 영역의 액터만 보인다. 내보내기 전에 전체 영역을 로드했는지 확인한다.

## 3. 파일 형식

`manifest.json` (build가 만든다)

```json
{"format": 1, "map": "Field_01", "map_version": "5d64db7031bef8d2", "unit": "cm",
 "bounds": {"min": [0, 0, -500], "max": [50000, 50000, 20000]},
 "files": [{"name": "nav.obj", "kind": "nav_geometry", "sha256": "...", "size": 1234}]}
```

`map_version`은 파일 이름과 내용 해시에서 계산한다. 같은 내용이면 언제 만들어도 같은 값이 나온다.

`spawns.json`

```json
{"spawns": [{"id": "SP_Slime_01", "type": "monster", "ref_id": 101, "count": 3, "radius": 300, "pos": [20000, 20000, 60]}]}
```

`type`: `monster`, `npc`, `player_start`, `gather`. `ref_id`는 기획 데이터의 ID다.

`volumes.json`

```json
{"volumes": [{"id": "V_Castle_NoFly", "type": "no_fly", "min": [30000, 30000, 0], "max": [40000, 40000, 20000]}]}
```

`type`: `no_fly`, `safe_zone`, `no_spawn`, `trigger`, `water`. 축에 정렬된 상자다.

`map_versions.json` (클라이언트 콘텐츠에 넣는다)

```json
{"Field_01": "5d64db7031bef8d2"}
```

## 4. 액터 태그 규칙

레벨의 액터 Tags에 적는다. 전용 액터 클래스를 만들지 않아도 된다.

| 태그 | 의미 |
|---|---|
| `ServerSpawn:<종류>:<ref_id>:<count>:<radius>` | 스폰 지점. 예: `ServerSpawn:monster:101:3:300` |
| `ServerVolume:<종류>` | 볼륨. 액터 경계가 상자로 나간다. 예: `ServerVolume:no_fly` |

액터 이름이 ID가 된다. 이름을 바꾸면 서버 쪽 참조(퀘스트의 스폰 ID 등)도 바뀐다.

## 5. 규칙 설명

| ID | 의미 | 고치는 방법 |
|---|---|---|
| WORLD001 | manifest가 없거나 읽을 수 없다 | `build`를 실행한다 |
| WORLD002 | 파일이 없거나 내용이 manifest와 다르다 | 내보낸 뒤 파일을 고쳤다면 `build`를 다시 한다 |
| WORLD003 | 필수 데이터가 묶음에 없다 | 빠진 파일을 내보낸다. `nav.obj`가 흔히 빠진다 |
| WORLD004 | 서버 데이터의 맵 버전이 클라이언트와 다르다. 한쪽만 갱신된 것이다 | 내보내기와 `build`를 다시 하고, 갱신된 `map_versions.json`을 함께 커밋한다. 맵을 고치고 내보내기를 아예 하지 않은 경우는 이 규칙이 아니라 `mmo-ci-pipeline`의 함께 바뀌어야 하는 파일 규칙이 잡는다 |
| WORLD005 | 스폰 문제: ID 중복, 알 수 없는 종류, 범위 밖, 스폰 금지 볼륨 안, count 오류 | 레벨에서 해당 액터를 고친다 |
| WORLD006 | 스폰이 기획 데이터에 없는 몬스터를 가리킨다 | 태그의 `ref_id`를 고치거나 기획 데이터에 몬스터를 추가한다 |
| WORLD007 | 볼륨 문제: ID 중복, 알 수 없는 종류, min이 max보다 큼, 범위 밖 | 레벨에서 해당 볼륨을 고친다 |
| WORLD008 | 내비 지오메트리가 비었거나 인덱스가 틀렸거나 크기가 너무 작다 | 내비메시를 빌드한 뒤 다시 내보낸다. 크기가 작으면 단위를 확인한다 |
| WORLD009 | 플레이어 시작점이 없다 | `ServerSpawn:player_start` 태그를 가진 액터를 둔다 |

스폰 금지 볼륨은 몬스터와 채집물에만 적용한다. 플레이어 시작점과 NPC는 마을 안에 둘 수 있다.

## 6. 서버 쪽 사용법

- 서버는 시작할 때 manifest를 읽고 파일 해시를 확인한다. 다르면 시작하지 않는다.
- 접속 시 클라이언트가 자기 `map_versions.json`의 값을 보내고, 서버가 다르면 접속을 거부한다.
  프로토콜 버전 교환과 같은 단계에서 한다(`mmo-protocol-check`의 프로토콜 가이드).
- 좌표계: 언리얼은 왼손 좌표계에 Z가 위, 단위는 cm다. Recast는 Y가 위인 좌표계를 쓰므로 서버에서
  읽을 때 축을 바꾼다. 변환을 한곳에만 둔다.
- 내비메시를 다시 빌드할 때 에이전트 반지름, 높이, 오를 수 있는 경사와 단차를 엔진 프로젝트 설정과
  같게 한다. 다르면 클라이언트에서 갈 수 있는 곳을 서버가 막거나 그 반대가 된다.
- 비행은 내비메시로 검증할 수 없다. 고도 한계와 `no_fly` 볼륨으로 검증한다(`ue-mount-flight`).
- 볼륨이 많아지면 서버에서 격자로 나눠 찾는다. 매 이동 패킷마다 전체 볼륨을 훑지 않는다.

## 7. 자동화

- 맵을 고치는 커밋에 내보내기와 `build`가 함께 들어가야 한다. 사람이 기억에 의존하면 반드시 빠진다.
- `mmo-ci-pipeline`이 `check`를 돌리고, 맵 파일이 바뀌었는데 서버 데이터가 바뀌지 않은 변경을 막는다.
- 에디터를 띄우지 않고 내보내려면 커맨드릿으로 Python을 실행한다:
  `UnrealEditor-Cmd <Project>.uproject <Map> -run=pythonscript -script=<collect_level_data.py 경로>`.
  `ExportNavigation`의 자동 실행은 엔진 버전에 따라 방법이 다르므로 프로젝트에서 확인한다.
- PCG로 생성한 통과 불가 오브젝트가 내비메시에 반영된 뒤에 내보낸다. 생성 → 내비 빌드 → 내보내기 순서다.

## 8. 참고 자료

- Epic 포럼, "How to obtain all the 3d positions of all the points in navmesh?": 콘솔의 `ExportNavigation`으로 OBJ를 얻는 방법
- Epic 답변, "How can I export navmesh data to file?": 내보내는 것은 걸을 수 있는 지오메트리의 OBJ이며, 내비메시 자체의 내보내기는 지원되지 않음
- Epic 포럼, "How can I use Navmesh data in Server Side?": 자체 서버에서는 엔진 소스로 Recast 데이터를 직접 꺼내야 함
- hxhb/ue4-export-nav-data: Recast 내비 데이터와 OBJ(cm 단위)를 내보내는 플러그인 사례
- Epic 포럼, "Problem with exporting nav mesh data": C++에서 `ExportNavigationData`를 호출하는 예
