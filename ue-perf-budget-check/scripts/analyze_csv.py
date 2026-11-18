"""CSV Profiler 캡처를 성능 예산과 비교해 판정한다. Unreal 없이 실행되는 순수 Python.

    python analyze_csv.py capture.csv --budget perf-budget.json --md report.md
    python analyze_csv.py --latest <Project>/Saved/Profiling/CSV --budget perf-budget.json

종료 코드: 0 통과, 1 error 규칙 실패, 2 입력 문제.
"""
import argparse
import csv
import glob
import json
import os
import re
import sys

SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _to_float(cell):
    try:
        return float(cell)
    except (TypeError, ValueError):
        return None


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = [r for r in csv.reader(f) if r]
    if not rows:
        raise ValueError("빈 CSV")
    return [h.strip() for h in rows[0]], rows[1:]


def find_column(header, aliases):
    """정확히 일치하는 열을 먼저 찾고, 없으면 'Category/Name'의 Name으로 찾는다. 대소문자 무시."""
    lower = [h.lower() for h in header]
    for a in aliases:
        if a.lower() in lower:
            return lower.index(a.lower())
    for a in aliases:
        for i, h in enumerate(lower):
            if h.rsplit("/", 1)[-1] == a.lower():
                return i
    return None


def similar_columns(header, aliases, limit=5):
    tokens = {a.rsplit("/", 1)[-1].lower() for a in aliases}
    tokens |= {t[:-4] for t in tokens if t.endswith("time") and len(t) > 6}
    return [h for h in header if any(t in h.lower() for t in tokens)][:limit]


def data_rows(header, rows, frame_idx, warmup):
    """끝에 반복되는 헤더 행과 메타데이터 행을 걸러내고 워밍업 프레임을 버린다."""
    if frame_idx is not None:
        out = [r for r in rows if frame_idx < len(r) and _to_float(r[frame_idx]) is not None]
    else:
        out = [r for r in rows if len(r) == len(header) and [c.strip() for c in r] != header
               and not r[0].startswith("[")]
    return out[warmup:]


def values(rows, idx):
    return [v for v in (_to_float(r[idx]) for r in rows if idx < len(r)) if v is not None]


def percentile(sorted_vals, p):
    if not sorted_vals:
        return None
    k = (len(sorted_vals) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def stat(vals, name, over=None):
    if not vals:
        return None
    if name == "avg":
        return sum(vals) / len(vals)
    if name == "max":
        return max(vals)
    if name == "min":
        return min(vals)
    if name == "pct_over":
        return 100.0 * sum(1 for v in vals if v > over) / len(vals)
    m = re.fullmatch(r"p(\d+(?:\.\d+)?)", name)
    if m:
        return percentile(sorted(vals), float(m.group(1)))
    raise ValueError(f"알 수 없는 stat: {name}")


def evaluate(header, rows, budget, baseline=None):
    frame_idx = find_column(header, budget.get("frame_time_columns", ["FrameTime"]))
    frames = data_rows(header, rows, frame_idx, budget.get("warmup_frames", 0))
    results, findings = [], []

    def finding(rule, severity, message):
        findings.append({"rule": rule, "severity": severity, "message": message})

    min_frames = budget.get("min_frames", 0)
    if len(frames) < min_frames:
        finding("GEN002", "warning", f"프레임 {len(frames)}개로 최소 {min_frames}개보다 적음. 통계를 믿기 어려움")

    for rule in budget.get("rules", []):
        idx = find_column(header, rule["columns"])
        res = {"id": rule["id"], "label": rule["label"], "stat": rule["stat"], "max": rule["max"],
               "unit": rule.get("unit", ""), "severity": rule.get("severity", "warning")}
        vals = values(frames, idx) if idx is not None else []
        if not vals:
            hint = similar_columns(header, rule["columns"])
            res.update(value=None, status="skipped")
            finding("GEN001", "info", f"{rule['id']} 건너뜀: 열 {rule['columns']} 없음"
                    + (f". 비슷한 열: {hint}" if hint else ""))
        else:
            v = stat(vals, rule["stat"], rule.get("over"))
            res.update(value=round(v, 3), column=header[idx], status="pass" if v <= rule["max"] else "fail")
            if res["status"] == "fail":
                finding(rule["id"], res["severity"],
                        f"{rule['label']}: {v:.2f}{res['unit']} (예산 {rule['max']}{res['unit']})")
        results.append(res)

    if baseline:
        pct = budget.get("regression_pct", 10)
        base = {r["id"]: r.get("value") for r in baseline.get("results", [])}
        for r in results:
            b = base.get(r["id"])
            if r["value"] is not None and b and r["value"] > b * (1 + pct / 100.0):
                finding("PERF900", "warning",
                        f"{r['label']}: 기준 {b:.2f} → {r['value']:.2f}{r['unit']} ({(r['value'] / b - 1) * 100:.0f}% 악화)")

    bottleneck = None
    bn = budget.get("bottleneck")
    if bn:
        scores = {}
        for name, cols in bn.get("threads", {}).items():
            idx = find_column(header, cols)
            vals = values(frames, idx) if idx is not None else []
            if vals:
                scores[name] = round(stat(vals, bn.get("stat", "p95")), 3)
        if scores:
            top = max(scores, key=scores.get)
            bottleneck = {"name": top, "stat": bn.get("stat", "p95"), "values": scores}

    ft = values(frames, frame_idx) if frame_idx is not None else []
    avg, p99 = stat(ft, "avg"), stat(ft, "p99")
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["rule"]))
    errors = sum(1 for f in findings if f["severity"] == "error")
    summary = {
        "passed": errors == 0,
        "frames": len(frames),
        "avg_fps": round(1000.0 / avg, 1) if avg else None,
        "low1_fps": round(1000.0 / p99, 1) if p99 else None,
        "error": errors,
        "warning": sum(1 for f in findings if f["severity"] == "warning"),
        "info": sum(1 for f in findings if f["severity"] == "info"),
        "bottleneck": bottleneck,
        "target_fps": budget.get("target_fps"),
    }
    return {"summary": summary, "results": results, "findings": findings}


def to_markdown(report, source="", label=""):
    s = report["summary"]
    lines = ["# 성능 예산 판정 보고서", "",
             f"- 결과: {'통과' if s['passed'] else '실패'} (목표 {s['target_fps']}fps)",
             f"- 캡처: {source}"]
    if label:
        lines.append(f"- 조건: {label}")
    lines += [f"- 프레임 {s['frames']}개 / 평균 {s['avg_fps']}fps / 1% low {s['low1_fps']}fps",
              f"- error {s['error']} / warning {s['warning']} / info {s['info']}"]
    if s["bottleneck"]:
        b = s["bottleneck"]
        detail = ", ".join(f"{k} {v}ms" for k, v in b["values"].items())
        lines.append(f"- 추정 병목: {b['name']} ({b['stat']} 기준: {detail})")
    lines += ["", "## 규칙별 결과", "", "| 규칙 | 항목 | 값 | 예산 | 판정 |", "|---|---|---|---|---|"]
    mark = {"pass": "통과", "fail": "실패", "skipped": "건너뜀"}
    for r in report["results"]:
        val = "-" if r["value"] is None else f"{r['value']}{r['unit']}"
        lines.append(f"| {r['id']} | {r['label']} | {val} | {r['max']}{r['unit']} | {mark[r['status']]} |")
    if report["findings"]:
        lines += ["", "## 지적 사항", ""]
        lines += [f"- [{f['severity']}] {f['rule']}: {f['message']}" for f in report["findings"]]
    return "\n".join(lines) + "\n"


def latest_csv(folder):
    files = glob.glob(os.path.join(folder, "**", "*.csv"), recursive=True)
    return max(files, key=os.path.getmtime) if files else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--latest", help="이 폴더에서 가장 최근 CSV를 사용")
    ap.add_argument("--budget", required=True)
    ap.add_argument("--baseline", help="비교할 이전 report.json")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--label", default="")
    a = ap.parse_args(argv)

    path = a.csv or (latest_csv(a.latest) if a.latest else None)
    if not path or not os.path.isfile(path):
        print("CSV를 찾지 못함. 경로를 주거나 --latest 폴더를 확인할 것", file=sys.stderr)
        return 2
    with open(a.budget, encoding="utf-8") as f:
        budget = json.load(f)
    baseline = None
    if a.baseline:
        with open(a.baseline, encoding="utf-8") as f:
            baseline = json.load(f)
    try:
        header, rows = read_csv(path)
    except ValueError as e:
        print(f"CSV를 읽지 못함: {e}", file=sys.stderr)
        return 2

    report = evaluate(header, rows, budget, baseline)
    report["source"], report["label"] = path, a.label
    for target, text in ((a.out, json.dumps(report, ensure_ascii=False, indent=2)),
                         (a.md, to_markdown(report, path, a.label))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(dict(report["summary"], source=path), ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
