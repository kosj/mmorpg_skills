"""타겟팅 전투의 스킬 데이터(CSV)를 검사하고 직업별 지속 피해량을 어림 계산한다. 순수 Python.

    python check_skills.py skills.csv --config combat-config.json --out report.json --md report.md

형식과 규칙 위반을 찾고, 단순한 우선순위 회전으로 직업별 초당 피해량(DPS)을 계산해 편차를 본다.
시뮬레이션은 오타와 큰 불균형을 찾는 용도다. 밸런스의 정답을 주지 않는다.
종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import csv
import json
import os
import statistics
import sys
from collections import Counter, defaultdict

DEFAULT_CONFIG = {
    "gcd_ms": 1000,
    "server_tick_ms": 100,
    "max_range_cm": 4000,
    "classes": [],
    "target_types": ["enemy", "ally", "self", "ground"],
    "cost_types": ["none", "mana", "stamina"],
    "modes": ["ground", "swim", "glide", "fly", "mounted"],
    "reference": {"attack_power": 100, "resource_pool": 1000, "resource_regen_per_sec": 20},
    "sim_seconds": 180,
    "sim_mode": "ground",
    "class_dps_tolerance_pct": 15,
    "skill_outlier_ratio": 3.0,
    "severity": {"SKILL001": "error", "SKILL002": "error", "SKILL003": "error", "SKILL004": "error",
                 "SKILL005": "warning", "SKILL006": "error", "SKILL007": "error", "SKILL009": "warning",
                 "SKILL010": "warning", "SKILL011": "info"},
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
INT_COLS = ["range_cm", "cast_time_ms", "cooldown_ms", "cost", "hits", "dot_tick_ms", "dot_duration_ms",
            "aoe_radius_cm", "max_targets", "level_req"]
FLOAT_COLS = ["coefficient", "base_damage", "dot_coefficient"]
REQUIRED = ["id", "name", "class", "target_type", "range_cm", "cast_time_ms", "cooldown_ms", "gcd",
            "cost_type", "cost", "coefficient", "usable_modes"]
_TRUE, _FALSE = {"true", "1", "yes"}, {"false", "0", "no", ""}


def _cfg(config):
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    cfg["severity"] = dict(DEFAULT_CONFIG["severity"], **(config or {}).get("severity", {}))
    cfg["reference"] = dict(DEFAULT_CONFIG["reference"], **(config or {}).get("reference", {}))
    return cfg


def parse_rows(rows, add):
    """문자열 행을 타입이 있는 스킬 딕셔너리로 바꾼다. 읽지 못한 행은 SKILL001로 남기고 건너뛴다."""
    skills, seen = [], set()
    for line, raw in rows:
        s, ok = {"_line": line}, True
        for col in REQUIRED:
            if (raw.get(col) or "").strip() == "" and col not in ("gcd",):
                add("SKILL001", line, raw.get("id", ""), f"필수 값 '{col}'이(가) 비어 있음")
                ok = False
        for col in INT_COLS + FLOAT_COLS:
            v = (raw.get(col) or "").strip()
            default = 1 if col == "hits" else 0
            try:
                s[col] = (int(v) if col in INT_COLS else float(v)) if v != "" else default
            except ValueError:
                add("SKILL001", line, raw.get("id", ""), f"'{col}'의 값 '{v}'이(가) 숫자가 아님")
                ok = False
        g = (raw.get("gcd") or "").strip().lower()
        if g in _TRUE or g in _FALSE:
            s["gcd"] = g in _TRUE
        else:
            add("SKILL001", line, raw.get("id", ""), f"'gcd'의 값 '{g}'이(가) true/false가 아님")
            ok = False
        for col in ("id", "name", "class", "target_type", "cost_type"):
            s[col] = (raw.get(col) or "").strip()
        s["usable_modes"] = [m.strip() for m in (raw.get("usable_modes") or "").split("|") if m.strip()]
        if s["id"] in seen:
            add("SKILL001", line, s["id"], f"id {s['id']} 중복")
            ok = False
        seen.add(s["id"])
        if ok:
            skills.append(s)
    return skills


def damage(s, ap):
    direct = (s["base_damage"] + s["coefficient"] * ap) * max(s["hits"], 1)
    ticks = s["dot_duration_ms"] // s["dot_tick_ms"] if s["dot_tick_ms"] > 0 else 0
    return direct + ticks * s["dot_coefficient"] * ap


def time_spent_ms(s, gcd_ms):
    return max(s["cast_time_ms"], gcd_ms if s["gcd"] else 0)


def simulate(skills, cfg):
    """우선순위 회전: 쓸 수 있는 스킬 중 '쓴 시간당 피해'가 가장 큰 것을 고른다."""
    ref, gcd = cfg["reference"], cfg["gcd_ms"]
    ap, pool, regen = ref["attack_power"], ref["resource_pool"], ref["resource_regen_per_sec"]
    usable = [s for s in skills if s["target_type"] in ("enemy", "ground") and cfg["sim_mode"] in s["usable_modes"]
              and damage(s, ap) > 0]
    end = cfg["sim_seconds"] * 1000
    t, resource, total = 0, float(pool), 0.0
    ready = {s["id"]: 0 for s in usable}
    casts, dealt = Counter(), Counter()

    def score(s):
        spent = time_spent_ms(s, gcd)
        return damage(s, ap) / spent if spent > 0 else float("inf")

    guard = 0
    while t < end and usable and guard < 200000:
        guard += 1
        options = [s for s in usable if ready[s["id"]] <= t and (s["cost_type"] == "none" or s["cost"] <= resource)]
        if not options:
            waits = [ready[s["id"]] - t for s in usable if ready[s["id"]] > t]
            step = max(min(waits) if waits else cfg["server_tick_ms"], cfg["server_tick_ms"])
            step = min(step, 1000)
            t += step
            resource = min(pool, resource + regen * step / 1000.0)
            continue
        s = max(options, key=lambda x: (score(x), x["id"]))
        spent = time_spent_ms(s, gcd)
        if s["cost_type"] != "none":
            resource -= s["cost"]
        ready[s["id"]] = t + max(s["cooldown_ms"], spent, 1)
        d = damage(s, ap)
        total += d
        casts[s["id"]] += 1
        dealt[s["id"]] += d
        t += spent
        resource = min(pool, resource + regen * spent / 1000.0)
    return {"dps": round(total / cfg["sim_seconds"], 2), "casts": dict(casts),
            "share": {k: round(v / total, 3) for k, v in dealt.items()} if total else {},
            "candidates": [s["id"] for s in usable]}


def check(rows, config=None):
    """rows: [(줄 번호, {열: 문자열})]"""
    cfg = _cfg(config)
    findings = []

    def add(rule, line, sid, message):
        findings.append({"rule": rule, "severity": cfg["severity"][rule], "line": line, "id": sid, "message": message})

    skills = parse_rows(rows, add)
    tick = cfg["server_tick_ms"]
    for s in skills:
        ln, sid = s["_line"], s["id"]
        if cfg["classes"] and s["class"] not in cfg["classes"]:
            add("SKILL002", ln, sid, f"알 수 없는 직업 '{s['class']}'")
        if s["target_type"] not in cfg["target_types"]:
            add("SKILL002", ln, sid, f"알 수 없는 대상 종류 '{s['target_type']}'")
        if s["cost_type"] not in cfg["cost_types"]:
            add("SKILL002", ln, sid, f"알 수 없는 자원 종류 '{s['cost_type']}'")
        bad_modes = [m for m in s["usable_modes"] if m not in cfg["modes"]]
        if bad_modes:
            add("SKILL002", ln, sid, f"알 수 없는 이동 모드: {', '.join(bad_modes)}")

        if s["target_type"] == "self" and s["range_cm"] != 0:
            add("SKILL003", ln, sid, "자기 대상 스킬의 사거리는 0이어야 함")
        if s["target_type"] in ("enemy", "ally", "ground") and s["range_cm"] <= 0:
            add("SKILL003", ln, sid, "대상이 있는 스킬인데 사거리가 0 이하")
        if s["range_cm"] > cfg["max_range_cm"]:
            add("SKILL003", ln, sid, f"사거리 {s['range_cm']}이(가) 최대 {cfg['max_range_cm']}을 넘음. "
                                     "서버가 대상을 볼 수 있는 거리 안이어야 함")

        if s["cast_time_ms"] < 0 or s["cooldown_ms"] < 0:
            add("SKILL004", ln, sid, "시전 시간이나 쿨다운이 음수")
        elif s["cast_time_ms"] == 0 and s["cooldown_ms"] == 0 and not s["gcd"]:
            add("SKILL004", ln, sid, "시전 시간 0, 쿨다운 0, 전역 쿨다운 없음: 무한히 연속 사용할 수 있음")
        if s["dot_duration_ms"] > 0 and (s["dot_tick_ms"] <= 0 or s["dot_tick_ms"] > s["dot_duration_ms"]):
            add("SKILL004", ln, sid, "지속 피해의 간격이 0 이하이거나 지속 시간보다 김")
        off = [c for c in ("cast_time_ms", "cooldown_ms", "dot_tick_ms") if tick > 0 and s[c] % tick]
        if off:
            add("SKILL005", ln, sid, f"{', '.join(off)}이(가) 서버 틱 {tick}ms의 배수가 아님")

        if s["cost"] < 0:
            add("SKILL006", ln, sid, "비용이 음수. 쓸수록 자원이 늘어남")
        elif s["cost_type"] == "none" and s["cost"] > 0:
            add("SKILL006", ln, sid, "자원 종류가 none인데 비용이 있음")
        elif s["cost"] > cfg["reference"]["resource_pool"]:
            add("SKILL006", ln, sid, f"비용 {s['cost']}이(가) 기준 자원량 {cfg['reference']['resource_pool']}보다 커서 쓸 수 없음")

        if s["target_type"] == "ground" and s["aoe_radius_cm"] <= 0:
            add("SKILL007", ln, sid, "지면 지정 스킬인데 범위 반지름이 없음")
        if s["aoe_radius_cm"] > 0 and s["max_targets"] < 1:
            add("SKILL007", ln, sid, "범위 스킬에 최대 대상 수가 없음. 밀집 지역에서 서버 비용이 제한되지 않음")

    # 직업별 시뮬레이션과 이상치
    by_class = defaultdict(list)
    for s in skills:
        by_class[s["class"]].append(s)
    ap, gcd = cfg["reference"]["attack_power"], cfg["gcd_ms"]
    sims = {}
    for cls, group in sorted(by_class.items()):
        sim = simulate(group, cfg)
        sims[cls] = sim
        rates = {s["id"]: damage(s, ap) / time_spent_ms(s, gcd) for s in group
                 if s["id"] in sim["candidates"] and time_spent_ms(s, gcd) > 0}
        if len(rates) >= 3:
            med = statistics.median(rates.values())
            for s in group:
                r = rates.get(s["id"])
                if r and med > 0 and r > med * cfg["skill_outlier_ratio"]:
                    add("SKILL010", s["_line"], s["id"], f"쓴 시간당 피해가 직업 중앙값의 {r / med:.1f}배. 계수나 자릿수 오타 확인")
        for s in group:
            if s["id"] in sim["candidates"] and sim["casts"].get(s["id"], 0) == 0:
                add("SKILL011", s["_line"], s["id"], "기준 회전에서 한 번도 쓰이지 않음. 다른 스킬보다 항상 불리함")
    dps = {c: v["dps"] for c, v in sims.items() if v["dps"] > 0}
    if len(dps) >= 2:
        med = statistics.median(dps.values())
        for cls, v in sorted(dps.items()):
            dev = (v - med) / med * 100
            if abs(dev) > cfg["class_dps_tolerance_pct"]:
                add("SKILL009", 0, cls, f"직업 {cls}의 DPS {v:.1f}이(가) 중앙값 {med:.1f}에서 {dev:+.0f}% 벗어남")

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["line"], f["rule"]))
    by_sev = Counter(f["severity"] for f in findings)
    summary = {"passed": by_sev.get("error", 0) == 0, "skills": len(skills), "classes": len(by_class),
               "error": by_sev.get("error", 0), "warning": by_sev.get("warning", 0), "info": by_sev.get("info", 0),
               "dps": {c: v["dps"] for c, v in sims.items()},
               "by_rule": dict(sorted(Counter(f["rule"] for f in findings).items()))}
    return {"summary": summary, "findings": findings, "simulation": sims}


def to_markdown(report):
    s = report["summary"]
    lines = ["# 스킬 데이터 검사 보고서", "", f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 스킬 {s['skills']}개, 직업 {s['classes']}개",
             f"- error {s['error']} / warning {s['warning']} / info {s['info']}", "",
             "## 직업별 기준 DPS (어림값)", "", "| 직업 | DPS | 피해 비중 |", "|---|---|---|"]
    for cls, sim in sorted(report["simulation"].items()):
        share = ", ".join(f"{k} {v * 100:.0f}%" for k, v in sorted(sim["share"].items(), key=lambda kv: -kv[1]))
        lines.append(f"| {cls} | {sim['dps']} | {share or '-'} |")
    lines += ["", "## 지적 사항", "", "| 심각도 | 규칙 | 위치 | 내용 |", "|---|---|---|---|"]
    for f in report["findings"]:
        where = f"{f['line']}행 {f['id']}" if f["line"] else str(f["id"])
        lines.append(f"| {f['severity']} | {f['rule']} | {where} | {f['message']} |")
    return "\n".join(lines) + "\n"


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in REQUIRED if c not in reader.fieldnames]
        if missing:
            raise ValueError("열 없음: " + ", ".join(missing))
        return [(i, row) for i, row in enumerate(reader, start=2) if any((v or "").strip() for v in row.values())]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("skills_csv")
    ap.add_argument("--config")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    try:
        rows = read_csv(a.skills_csv)
        config = None
        if a.config:
            with open(a.config, encoding="utf-8") as f:
                config = json.load(f)
    except (OSError, ValueError) as e:
        print(f"입력을 읽지 못함: {e}", file=sys.stderr)
        return 2
    report = check(rows, config)
    for target, text in ((a.out, json.dumps(report, ensure_ascii=False, indent=2)), (a.md, to_markdown(report))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
