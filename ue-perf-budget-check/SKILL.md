---
name: ue-perf-budget-check
description: Judges an Unreal Engine 5.8 CSV Profiler capture against the studio performance budget (Windows, 60 fps target) - frame time average and percentiles, hitch rate, game/render/GPU thread times, draw calls, memory - and reports pass/fail, the likely bottleneck, and regressions against a baseline. Use when asked to check performance, verify 60fps, analyze a csvprofile capture, compare builds, or when asked about 성능 예산, 프레임 판정, 프로파일 분석, 히치, 병목.
---

# UE 성능 예산 판정

CSV Profiler 캡처를 예산과 비교해 통과/실패를 판정한다.
수치 계산과 판정은 전부 `scripts/analyze_csv.py`가 한다. CSV를 직접 읽고 암산하지 않는다.

## 구성

- `scripts/analyze_csv.py`: 순수 Python. CSV 파싱 → 통계 → 예산 판정 → 보고서. 에디터 없이 실행된다.
- `references/perf-budget.json`: 예산 값과 CSV 열 이름. 수치를 바꾸려면 이 파일만 고친다.
- `references/capture-guide.md`: 캡처 조건과 방법. 캡처를 직접 하거나 안내할 때 읽는다.
- `references/rules.md`: 규칙별 의미와 원인을 좁히는 방법. 실패 원인을 설명할 때만 읽는다.

## 절차

1. **캡처가 있는지 확인한다.** CSV는 `<Project>/Saved/Profiling/CSV/`에 생긴다. 없거나 새로 측정해야 하면
   `references/capture-guide.md`를 읽고 캡처한다.
2. **측정 조건을 확인한다.** 아래 중 하나라도 해당하면 판정 결과에 그 사실을 함께 적는다.
   판정 자체를 거부하지는 않는다.
   - 에디터(PIE)에서 측정했다: 에디터 부하가 섞여 실제 게임보다 느리다. 참고용이다.
   - 수직동기화나 프레임 제한이 켜져 있다: 프레임 시간이 16.67ms 근처에 묶여 여유를 알 수 없다.
   - 측정 PC 사양이 목표 사양과 다르다.
3. **판정한다.**

   ```
   python scripts/analyze_csv.py --latest "<Project>/Saved/Profiling/CSV" \
       --budget references/perf-budget.json \
       --out "<Project>/Saved/PerfBudget/report.json" --md "<Project>/Saved/PerfBudget/report.md" \
       --label "빌드 번호, 맵, PC 사양"
   ```

   특정 파일을 볼 때는 `--latest` 대신 CSV 경로를 첫 인자로 준다.
   이전 결과와 비교하려면 `--baseline <이전 report.json>`을 붙인다.
4. **보고한다.** 통과/실패, 평균 fps와 1% low fps, 실패한 규칙, 추정 병목 순으로 짧게 전한다.
   전체 표는 보고서 경로로 안내한다.
5. **원인 분석은 요청받았을 때 한다.** `references/rules.md`의 해당 규칙을 읽고 다음 측정 방법을 제안한다.
   이 스킬은 판정까지만 한다. 설정이나 에셋을 고치지 않는다.

## 주의

- `GEN001`은 CSV에 해당 열이 없어 검사를 건너뛴 것이다. 실패가 아니다. 보고서에 비슷한 열 이름이
  함께 나오므로, 맞는 이름을 `perf-budget.json`의 `columns`에 추가한다.
- `GEN002`는 프레임 수가 부족해 통계를 믿기 어렵다는 뜻이다. 더 길게 캡처한다.
- 추정 병목은 스레드별 p95를 비교한 것이다. 5.8에서는 FrameTime이 스레드 타이머보다 한 프레임 늦게
  기록되므로 프레임 단위로 열끼리 맞춰 보지 않는다.
- 한 번의 캡처로 결론 내리지 않는다. 결과가 예산 경계에 있으면 같은 조건으로 다시 측정해 보라고 권한다.
- 예산 값이 프로젝트 기준과 다르다는 말을 들으면 코드가 아니라 `references/perf-budget.json`을 고친다.
