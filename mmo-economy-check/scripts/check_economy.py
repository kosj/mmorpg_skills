"""기획 데이터로 레벨별 성장 속도와 재화 흐름을 어림 계산하고 이상한 곳을 찾는다. 순수 Python.

    python check_economy.py <데이터 폴더> --config economy-config.json --md report.md

입력은 mmo-data-check와 같은 CSV다: monsters.csv, drops.csv, items.csv, levels.csv.
모델: 각 레벨의 플레이어는 자기 레벨 근처 몬스터 중 경험치 효율이 가장 좋은 것을 사냥한다.
어림 계산이다. 퀘스트 보상, 거래, 제작, 파티 사냥은 들어 있지 않다.
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
    "files": {"monsters": "monsters.csv", "drops": "drops.csv", "items": "items.csv", "levels": "levels.csv"},
    "player": {"base_dps": 10.0, "dps_growth_per_level": 1.2, "downtime_sec_per_kill": 4.0},
    "hunt_level_below": 2,
    "hunt_level_above": 1,
    "efficiency_outlier_ratio": 2.0,
    "level_time_spike_ratio": 2.5,
    "afford_hours_by_grade": {"common": [0.05, 3], "uncommon": [0.3, 8], "rare": [1, 20],
                              "epic": [3, 60], "legendary": [10, 200]},
    "severity": {"ECON001": "error", "ECON002": "warning", "ECON003": "warning", "ECON004": "error",
                 "ECON005": "warning", "ECON006": "warning"},
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
NEEDED = {"monsters": ["id", "level", "hp", "exp_reward", "gold_min", "gold_max", "drop_group"],
          "drops": ["group_id", "item_id", "prob", "min_count", "max_count"],
          "items": ["id", "grade", "level_req", "price_buy", "price_sell"],
          "levels": ["level", "exp_required"]}


def _cfg(config):
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    for k in ("files", "player", "severity", "afford_hours_by_grade"):
        cfg[k] = dict(DEFAULT_CONFIG[k], **(config or {}).get(k, {}))
    return cfg


def read_tables(folder, cfg):
    """필요한 열만 숫자로 읽는다. 파일이나 열이 없으면 ValueError."""
    tables = {}
    for name, cols in NEEDED.items():
        path = os.path.join(folder, cfg["files"][name])
        if not os.path.isfile(path):
            raise ValueError(f"파일 없음: {cfg['files'][name]}")
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            header = [h.strip() for h in (reader.fieldnames or [])]
            missing = [c for c in cols if c not in header]
            if missing:
                raise ValueError(f"{cfg['files'][name]}에 열 없음: {', '.join(missing)}")
            reader.fieldnames = header
            tables[name] = [(i, row) for i, row in enumerate(reader, start=2)
                            if any((v or "").strip() for v in row.values())]
    return tables


def _num(row, col, default=0.0):
    v = (row.get(col) or "").strip()
    return float(v) if v != "" else default


def analyze(tables, config=None):
    cfg = _cfg(config)
    findings = []

    def add(rule, where, message):
        findings.append({"rule": rule, "severity": cfg["severity"][rule], "where": where, "message": message})

    def parse(name, cols):
        out = []
        for line, row in tables[name]:
            try:
                out.append(dict({c: _num(row, c) for c in cols}, _line=line,
                                _raw={k: (v or "").strip() for k, v in row.items()}))
            except ValueError:
                add("ECON001", f"{cfg['files'][name]}:{line}", "숫자가 아닌 값이 있어 계산에서 제외함")
        return out

    monsters = parse("monsters", ["id", "level", "hp", "exp_reward", "gold_min", "gold_max", "drop_group"])
    drops = parse("drops", ["group_id", "item_id", "prob", "min_count", "max_count"])
    items = parse("items", ["id", "level_req", "price_buy", "price_sell"])
    levels = sorted(parse("levels", ["level", "exp_required"]), key=lambda r: r["level"])

    sell = {int(i["id"]): i["price_sell"] for i in items}
    drop_value = defaultdict(float)
    for d in drops:
        drop_value[int(d["group_id"])] += d["prob"] * (d["min_count"] + d["max_count"]) / 2 * sell.get(int(d["item_id"]), 0.0)

    p = cfg["player"]

    def stats(m, player_level):
        dps = p["base_dps"] * p["dps_growth_per_level"] ** (player_level - 1)
        ttk = m["hp"] / dps + p["downtime_sec_per_kill"]
        gold = (m["gold_min"] + m["gold_max"]) / 2 + drop_value.get(int(m["drop_group"]), 0.0)
        return {"id": int(m["id"]), "level": int(m["level"]), "ttk": ttk,
                "gold_per_hour": gold / ttk * 3600, "exp_per_hour": m["exp_reward"] / ttk * 3600}

    valid = [m for m in monsters if m["hp"] > 0]
    curve, cum_hours, cum_gold = [], 0.0, 0.0
    for cur, nxt in zip(levels, levels[1:]):
        lv = int(cur["level"])
        pool = [stats(m, lv) for m in valid
                if lv - cfg["hunt_level_below"] <= m["level"] <= lv + cfg["hunt_level_above"] and m["exp_reward"] > 0]
        if not pool:
            add("ECON004", f"레벨 {lv}", f"레벨 {lv - cfg['hunt_level_below']}~{lv + cfg['hunt_level_above']} 범위에 "
                                       "경험치를 주는 몬스터가 없음. 사냥으로 성장할 수 없는 구간")
            curve.append({"level": lv, "monster": None, "exp_per_hour": 0, "gold_per_hour": 0, "hours": None})
            continue
        best = max(pool, key=lambda s: (s["exp_per_hour"], -s["id"]))
        if len(pool) >= 3:
            for key, rule, label in (("gold_per_hour", "ECON002", "골드"), ("exp_per_hour", "ECON003", "경험치")):
                med = statistics.median(s[key] for s in pool)
                top = max(pool, key=lambda s: (s[key], -s["id"]))
                if med > 0 and top[key] > med * cfg["efficiency_outlier_ratio"]:
                    add(rule, f"몬스터 {top['id']}", f"레벨 {lv} 기준 {label} 효율이 같은 구간 중앙값의 "
                                                   f"{top[key] / med:.1f}배. 모두가 이 몬스터만 잡게 됨")
        hours = (nxt["exp_required"] - cur["exp_required"]) / best["exp_per_hour"]
        cum_hours += hours
        cum_gold += hours * best["gold_per_hour"]
        curve.append({"level": lv, "monster": best["id"], "exp_per_hour": round(best["exp_per_hour"]),
                      "gold_per_hour": round(best["gold_per_hour"]), "hours": round(hours, 2),
                      "cum_hours": round(cum_hours, 1), "cum_gold": round(cum_gold)})

    known = [c for c in curve if c["hours"]]
    for prev, cur in zip(known, known[1:]):
        ratio = cur["hours"] / prev["hours"] if prev["hours"] > 0 else 0
        if ratio > cfg["level_time_spike_ratio"]:
            add("ECON005", f"레벨 {cur['level']}", f"레벨업 시간이 이전 레벨의 {ratio:.1f}배 ({prev['hours']}시간 → {cur['hours']}시간). 성장 벽")
        elif 0 < ratio < 1 / cfg["level_time_spike_ratio"]:
            add("ECON005", f"레벨 {cur['level']}", f"레벨업 시간이 이전 레벨의 {ratio:.2f}배로 급감 ({prev['hours']}시간 → {cur['hours']}시간)")

    gph = {c["level"]: c["gold_per_hour"] for c in curve if c["gold_per_hour"]}
    for it in items:
        grade, lv = it["_raw"].get("grade", ""), int(it["level_req"])
        band = cfg["afford_hours_by_grade"].get(grade)
        if not band or it["price_buy"] <= 0 or lv not in gph:
            continue
        hours = it["price_buy"] / gph[lv]
        if hours > band[1]:
            add("ECON006", f"아이템 {int(it['id'])}", f"{grade} 등급인데 레벨 {lv}에서 {hours:.1f}시간 사냥해야 살 수 있음 (기준 {band[1]}시간 이하)")
        elif hours < band[0]:
            add("ECON006", f"아이템 {int(it['id'])}", f"{grade} 등급인데 레벨 {lv}에서 {hours * 60:.1f}분이면 살 수 있음 (기준 {band[0]}시간 이상). 골드 소모처 역할을 못 함")

    # 같은 지적이 여러 레벨에서 반복되면 처음 것만 남긴다
    uniq, seen = [], set()
    for f in findings:
        key = (f["rule"], f["where"])
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    uniq.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"], f["where"]))
    by_sev = Counter(f["severity"] for f in uniq)
    summary = {"passed": by_sev.get("error", 0) == 0, "levels": len(curve),
               "hours_to_max": round(cum_hours, 1), "gold_to_max": round(cum_gold),
               "error": by_sev.get("error", 0), "warning": by_sev.get("warning", 0),
               "by_rule": dict(sorted(Counter(f["rule"] for f in uniq).items()))}
    return {"summary": summary, "findings": uniq, "curve": curve}


def to_markdown(report):
    s = report["summary"]
    lines = ["# 성장과 재화 흐름 검사 보고서", "", "사냥만으로 계산한 어림값이다. 퀘스트, 거래, 제작, 파티는 들어 있지 않다.", "",
             f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 최고 레벨까지 약 {s['hours_to_max']}시간, 누적 골드 약 {s['gold_to_max']:,}",
             f"- error {s['error']} / warning {s['warning']}", "",
             "## 레벨별 곡선", "", "| 레벨 | 사냥 몬스터 | 경험치/시간 | 골드/시간 | 레벨업 시간 | 누적 시간 |", "|---|---|---|---|---|---|"]
    for c in report["curve"]:
        if c["hours"] is None:
            lines.append(f"| {c['level']} | 없음 | - | - | - | - |")
        else:
            lines.append(f"| {c['level']} | {c['monster']} | {c['exp_per_hour']:,} | {c['gold_per_hour']:,} | {c['hours']} | {c['cum_hours']} |")
    lines += ["", "## 지적 사항", "", "| 심각도 | 규칙 | 위치 | 내용 |", "|---|---|---|---|"]
    lines += [f"| {f['severity']} | {f['rule']} | {f['where']} | {f['message']} |" for f in report["findings"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data_dir")
    ap.add_argument("--config")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    try:
        config = None
        if a.config:
            with open(a.config, encoding="utf-8") as f:
                config = json.load(f)
        if not os.path.isdir(a.data_dir):
            raise ValueError(f"데이터 폴더 없음: {a.data_dir}")
        tables = read_tables(a.data_dir, _cfg(config))
    except (OSError, ValueError) as e:
        print(f"입력을 읽지 못함: {e}", file=sys.stderr)
        return 2
    report = analyze(tables, config)
    for target, text in ((a.out, json.dumps(report, ensure_ascii=False, indent=2)), (a.md, to_markdown(report))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
