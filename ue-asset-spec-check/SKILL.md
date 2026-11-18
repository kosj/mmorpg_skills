---
name: ue-asset-spec-check
description: Checks Unreal Engine 5.8 project assets against the studio asset spec (naming prefixes, texture size / power-of-two / sRGB / compression, static mesh LODs, triangle budget, collision, material slots) and produces a pass/fail report. Use when asked to validate, audit, or review assets, before submitting content to source control, or when asked about 에셋 규격 검사, 네이밍 검사, 텍스처/메시 규격, LOD 점검.
---

# UE 에셋 규격 검사

프로젝트 에셋이 스튜디오 규격을 지키는지 검사하고 보고서를 만든다.
판정은 전부 스크립트가 한다. 눈으로 보고 추정하지 말고 스크립트 결과만 보고한다.

## 구성

- `scripts/collect_assets.py`: 에디터 안에서 실행. 에셋의 사실 정보(이름, 클래스, 크기, LOD 등)만 수집한다.
- `scripts/validate.py`: 순수 Python. 수집된 사실과 규격을 비교해 위반 목록을 만든다. 에디터 없이도 실행된다.
- `scripts/run_check.py`: 에디터 안 진입점. 수집 → 판정 → 보고서 저장을 한 번에 한다.
- `references/asset-spec.json`: 규격 값. 수치를 바꾸려면 이 파일만 고친다.
- `references/rules.md`: 규칙 ID별 의미와 고치는 방법. 위반을 설명하거나 수정안을 낼 때만 읽는다.

## 절차

1. **범위를 정한다.** 사용자가 폴더를 말했으면 그 경로만 검사한다. 말하지 않았으면 묻지 말고
   변경된 폴더나 `/Game` 하위의 좁은 경로부터 시작한다. `/Game` 전체는 에셋을 모두 로드하므로
   사용자가 명시적으로 요청했을 때만 돌린다.
2. **에디터에서 실행한다.** Unreal MCP의 Python 실행 도구로 아래를 보낸다.

   ```python
   import sys, importlib, unreal
   p = unreal.Paths.project_dir() + "Skills/ue-asset-spec-check/scripts"
   if p not in sys.path:
       sys.path.insert(0, p)
   import run_check
   importlib.reload(run_check)
   print(run_check.main(roots=["/Game/Environment/Props"]))
   ```

   에디터를 띄우지 않는 CI에서는 커맨드릿으로 실행한다.

   ```
   UnrealEditor-Cmd <Project>.uproject -run=pythonscript -script="<Project>/Skills/ue-asset-spec-check/scripts/run_check.py"
   ```

   이때 범위는 환경변수 `ASSET_SPEC_ROOTS`(쉼표 구분)로 넘긴다.
3. **결과를 읽는다.** 보고서는 `<Project>/Saved/AssetSpec/report.md`와 `report.json`에 저장된다.
   `main()`의 반환값에 요약(검사 수, error/warning/info 개수, 보고서 경로)이 들어 있다.
4. **보고한다.** error 개수를 먼저 말하고, 규칙별 개수, 대표 위반 몇 건 순으로 짧게 전한다.
   전체 목록은 보고서 경로로 안내한다.
5. **수정은 요청받았을 때만 한다.** 이 스킬은 읽기 전용 검사다. 이름 변경, 압축 설정 변경 같은
   수정을 요청받으면 `references/rules.md`의 해당 규칙을 읽고, 바꿀 에셋 목록을 먼저 보여준 뒤 진행한다.
   이름 변경은 리디렉터와 참조에 영향을 주므로 한 번에 대량으로 하지 않는다.

## 주의

- `GEN001`(검사 불가)은 위반이 아니라 수집 실패다. 엔진 버전에 따라 Python API 이름이 달라
  생길 수 있다. 다수 발생하면 `collect_assets.py`의 해당 호출을 엔진 Python API 문서로 확인하고 고친다.
- MCP 도구 호출은 한 번에 하나만 보낸다. 검사가 끝나기 전에 다른 호출을 겹쳐 보내지 않는다.
- 규격 값이 프로젝트 기준과 다르다는 말을 들으면 코드가 아니라 `references/asset-spec.json`을 고친다.
- 사실 정보만 따로 뽑아 에디터 밖에서 다시 판정할 수 있다:
  `python scripts/validate.py facts.json references/asset-spec.json --md report.md`
