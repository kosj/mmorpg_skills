---
name: mmo-ci-pipeline
description: Runs the project's check skills together for the MMORPG - game data, combat skill data, protocol, netcode lint, client contract, server world data, asset spec and performance budget - selecting checks by the files that changed, enforcing files that must change together (a map change needs re-exported server data, a packet schema change needs an updated lock file), and producing one pass/fail report. Use before committing or submitting changes, when setting up pre-commit hooks or nightly builds, when asked which checks apply to a change, or when asked about 커밋 전 검사, 야간 빌드, CI, 전체 검사, 빌드 파이프라인.
---

# 검사 파이프라인

프로젝트의 검사 스킬들을 한 번에 돌린다. 어떤 검사를 돌릴지는 바뀐 파일로 정하고,
결과는 표 하나로 모은다. 실행과 판정은 `scripts/run_checks.py`가 한다.

## 구성

- `scripts/run_checks.py`: 순수 Python. 설정대로 검사를 실행하고 결과를 모은다.
- `references/pipeline.json`: 검사 목록, 실행 명령, 트리거, 함께 바뀌어야 하는 파일 규칙. 경로는 예시다.
- `references/ci-guide.md`: 단계 구성, 커밋 전 훅과 야간 빌드에 거는 방법, 검사 추가 방법, 상태 값 설명.

## 변경을 올리기 전에

1. **계획을 본다.** 실행하지 않고 어떤 검사가 걸리는지 확인한다.

   ```
   python scripts/run_checks.py --pipeline references/pipeline.json --stage precommit \
       --git-base origin/main --list
   ```

2. **실행한다.**

   ```
   python scripts/run_checks.py --pipeline references/pipeline.json --stage precommit \
       --git-base origin/main --out report.json --md report.md
   ```

   git을 쓰지 않으면 바뀐 파일 경로를 한 줄에 하나씩 적은 파일을 `--changed-files`로 준다.
3. **실패한 검사는 해당 스킬로 넘어가 처리한다.** 이 스킬은 실행과 집계만 한다. 지적의 의미와
   고치는 방법은 각 검사 스킬의 규칙 설명 문서나 가이드에 있다. 검사별 상세 보고서는
   `pipeline.json`의 `reports` 폴더에 생긴다.
4. **보고한다.** 통과/실패, 실패한 검사 이름, 각 실패의 한 줄 요약 순으로 전한다.
   "해당 없음"과 "입력 없음"은 통과가 아니므로 통과한 것처럼 말하지 않는다.

## 처음 설정할 때

`references/ci-guide.md`를 읽는다. `pipeline.json`의 `vars`를 프로젝트 경로로 바꾸는 것이 먼저다.
`--list`로 모든 검사가 `run`으로 나오는지 확인하고, `missing_input`이 나오면 경로가 틀린 것이다.

## 주의

- 실패를 통과로 만들려고 검사를 `pipeline.json`에서 빼거나 `required`를 끄지 않는다. 검사 구성을
  바꾸는 것은 사용자가 정한다.
- 바뀐 파일 목록 없이 실행하면 함께 바뀌어야 하는 파일 규칙(`co_change`)은 검사되지 않는다.
  커밋 전 검사에는 항상 `--git-base`나 `--changed-files`를 준다.
- 에셋 규격과 성능 검사는 에디터나 게임이 먼저 만든 파일을 판정한다. 그 파일이 오래된 것이면
  결과도 오래된 것이다. 야간 빌드에서 수집 직후에 돌린다.
- 훅이나 CI 설정 파일을 프로젝트에 추가하는 것은 사용자가 요청했을 때만 한다.
