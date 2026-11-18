"""퀘스트 데이터(CSV)의 구조와 다른 표와의 연결을 검사한다. 순수 Python.

    python check_quests.py <데이터 폴더> --config quest-config.json --md report.md

선행 퀘스트의 순환, 끊긴 참조, 얻을 수 없는 수집 아이템, 지나치게 많은 사냥이 필요한 수집 퀘스트,
메인 퀘스트의 레벨 공백, 과한 경험치 보상을 찾는다. 퀘스트의 재미는 판단하지 않는다.
종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

DEFAULT_CONFIG = {
    "files": {"quests": "quests.csv", "monsters": "monsters.csv", "items": "items.csv",
              "drops": "drops.csv", "levels": "levels.csv"},
    "types": ["main", "side", "daily"],
    "objective_types": ["kill", "collect", "talk", "reach"],
    "target_level_above": 2,
    "target_level_below": 5,
    "max_expected_kills": 60,
    "main_level_gap": 2,
    "max_exp_share_of_level": 0.5,
    "severity": {"QUEST001": "error", "QUEST002": "error", "QUEST003": "error", "QUEST004": "warning",
                 "QUEST005": "error", "QUEST006": "error", "QUEST007": "warning", "QUEST008": "error",
                 "QUEST009": "warning", "QUEST010": "warning", "QUEST011": "warning", "QUEST013": "warning"},
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
QUEST_COLS = ["id", "name", "type", "level_req", "prev_quests", "objective_type", "objective_target",
              "objective_count", "reward_exp", "reward_gold", "reward_items"]
OTHER_COLS = {"monsters": ["id", "level", "drop_group"], "items": ["id", "price_buy"],
              "drops": ["group_id", "item_id", "prob", "min_count", "max_count"], "levels": ["level", "exp_required"]}


def _cfg(config):
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    for k in ("files", "severity"):
        cfg[k] = dict(DEFAULT_CONFIG[k], **(config or {}).get(k, {}))
    return cfg


def _read(path, cols):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in (reader.fieldnames or [])]
        missing = [c for c in cols if c not in header]
        if missing:
            raise ValueError(f"{os.path.basename(path)}에 열 없음: {', '.join(missing)}")
        reader.fieldnames = header
        return [(i, {k: (v or "").strip() for k, v in row.items()}) for i, row in enumerate(reader, start=2)
                if any((v or "").strip() for v in row.values())]


def read_tables(folder, cfg):
    tables = {}
    for name, cols in dict(OTHER_COLS, quests=QUEST_COLS).items():
        path = os.path.join(folder, cfg["files"][name])
        if not os.path.isfile(path):
            if name == "levels":      # 없으면 경험치 비중 검사만 건너뛴다
                tables[name] = []
                continue
            raise ValueError(f"파일 없음: {cfg['files'][name]}")
        tables[name] = _read(path, cols)
    return tables


def _ids(cell):
    return [x.strip() for x in cell.split("|") if x.strip()]


def find_cycles(prev):
    """선행 관계 그래프에서 순환을 찾는다. 각 순환은 한 번만, 가장 작은 id부터 적는다."""
    color, cycles, seen = {}, [], set()

    def visit(node, stack):
        color[node] = 1
        stack.append(node)
        for nxt in prev.get(node, []):
            if nxt not in prev:
                continue
            if color.get(nxt) == 1:
                cyc = stack[stack.index(nxt):]
                k = cyc.index(min(cyc))
                cyc = cyc[k:] + cyc[:k]
                if tuple(cyc) not in seen:
                    seen.add(tuple(cyc))
                    cycles.append(cyc)
            elif nxt not in color:
                visit(nxt, stack)
        stack.pop()
        color[node] = 2

    for node in sorted(prev):
        if node not in color:
            visit(node, [])
    return cycles


def check(tables, config=None):
    cfg = _cfg(config)
    findings = []

    def add(rule, line, qid, message):
        findings.append({"rule": rule, "severity": cfg["severity"][rule], "line": line, "id": qid, "message": message})

    def num(s, default=None):
        try:
            return float(s) if s != "" else default
        except ValueError:
            return None

    monsters = {r["id"]: r for _, r in tables["monsters"]}
    items = {r["id"]: r for _, r in tables["items"]}
    # 아이템별: 그것을 떨어뜨리는 몬스터 중 한 마리당 기대 개수가 가장 큰 값
    group_yield = defaultdict(dict)
    for _, d in tables["drops"]:
        p, lo, hi = num(d["prob"], 0), num(d["min_count"], 1), num(d["max_count"], 1)
        if p and lo is not None and hi is not None:
            group_yield[d["group_id"]][d["item_id"]] = p * (lo + hi) / 2
    best_yield = defaultdict(float)
    for m in monsters.values():
        for item_id, y in group_yield.get(m["drop_group"], {}).items():
            best_yield[item_id] = max(best_yield[item_id], y)
    levels = sorted(((int(num(r["level"])), num(r["exp_required"])) for _, r in tables["levels"]
                     if num(r["level"]) is not None and num(r["exp_required"]) is not None))
    exp_for = {lv: nxt - cur for (lv, cur), (_, nxt) in zip(levels, levels[1:])}

    quests, seen = {}, set()
    for line, r in tables["quests"]:
        qid, ok = r["id"], True
        if not qid or not r["name"]:
            add("QUEST001", line, qid, "id나 name이 비어 있음")
            ok = False
        if qid in seen:
            add("QUEST001", line, qid, f"id {qid} 중복")
            ok = False
        seen.add(qid)
        q = {"line": line, "id": qid, "type": r["type"], "prev": _ids(r["prev_quests"]),
             "otype": r["objective_type"], "target": r["objective_target"], "rewards": _ids(r["reward_items"])}
        for col, default in (("level_req", None), ("objective_count", 1), ("reward_exp", 0), ("reward_gold", 0)):
            v = num(r[col], default)
            if v is None or v < 0:
                add("QUEST001", line, qid, f"'{col}'의 값 '{r[col]}'이(가) 0 이상의 숫자가 아님")
                ok = False
            q[col] = v
        if r["type"] not in cfg["types"]:
            add("QUEST001", line, qid, f"알 수 없는 퀘스트 종류 '{r['type']}'")
        if r["objective_type"] not in cfg["objective_types"]:
            add("QUEST001", line, qid, f"알 수 없는 목표 종류 '{r['objective_type']}'")
        if ok:
            quests[qid] = q

    for q in quests.values():
        line, qid, lv = q["line"], q["id"], q["level_req"]
        for p in q["prev"]:
            if p == qid:
                add("QUEST002", line, qid, "자기 자신을 선행 퀘스트로 가짐")
            elif p not in quests:
                add("QUEST002", line, qid, f"선행 퀘스트 {p}이(가) 없음")
            elif quests[p]["level_req"] > lv:
                add("QUEST004", line, qid, f"요구 레벨 {lv:g}인데 선행 퀘스트 {p}의 요구 레벨이 {quests[p]['level_req']:g}. "
                                           "실제로는 더 높은 레벨에서만 받을 수 있음")
        if q["otype"] in ("kill", "collect") and q["objective_count"] < 1:
            add("QUEST005", line, qid, "목표 개수가 1보다 작음")
        if q["otype"] == "kill":
            m = monsters.get(q["target"])
            if not m:
                add("QUEST005", line, qid, f"처치 대상 몬스터 {q['target']}이(가) 없음")
            else:
                diff = num(m["level"], 0) - lv
                if diff > cfg["target_level_above"] or -diff > cfg["target_level_below"]:
                    add("QUEST007", line, qid, f"요구 레벨 {lv:g}인데 대상 몬스터 {q['target']}의 레벨이 {m['level']}")
        elif q["otype"] == "collect":
            it = items.get(q["target"])
            if not it:
                add("QUEST005", line, qid, f"수집 대상 아이템 {q['target']}이(가) 없음")
            elif best_yield.get(q["target"], 0) <= 0:
                if (num(it["price_buy"], 0) or 0) <= 0:
                    add("QUEST006", line, qid, f"수집 대상 아이템 {q['target']}을(를) 얻을 방법이 없음 (드롭도 상점 판매도 없음)")
            else:
                kills = q["objective_count"] / best_yield[q["target"]]
                if kills > cfg["max_expected_kills"]:
                    add("QUEST013", line, qid, f"아이템 {q['target']} {q['objective_count']:g}개를 모으려면 평균 {kills:.0f}마리를 "
                                               f"잡아야 함 (기준 {cfg['max_expected_kills']}마리)")
        for item_id in q["rewards"]:
            if item_id not in items:
                add("QUEST008", line, qid, f"보상 아이템 {item_id}이(가) 없음")
        need = exp_for.get(int(lv))
        if need and q["reward_exp"] > need * cfg["max_exp_share_of_level"]:
            add("QUEST010", line, qid, f"보상 경험치 {q['reward_exp']:g}이(가) 레벨 {lv:g}의 필요 경험치 {need:g}의 "
                                       f"{q['reward_exp'] / need * 100:.0f}%")

    for cyc in find_cycles({qid: q["prev"] for qid, q in quests.items()}):
        add("QUEST003", quests[cyc[0]]["line"], cyc[0], "선행 퀘스트가 서로를 요구함: " + " → ".join(cyc + cyc[:1]))

    # 메인 퀘스트: 시작점이 하나인지, 이어지는 퀘스트 사이의 레벨 공백
    main = {qid: q for qid, q in quests.items() if q["type"] == "main"}
    roots = sorted(qid for qid, q in main.items() if not any(p in main for p in q["prev"]))
    if len(roots) > 1:
        for qid in roots[1:]:
            add("QUEST011", main[qid]["line"], qid, f"메인 퀘스트의 시작점이 여러 개임 ({', '.join(roots)}). "
                                                    "선행 메인 퀘스트가 빠졌는지 확인")
    for qid, q in main.items():
        for p in q["prev"]:
            if p in main and q["level_req"] - main[p]["level_req"] > cfg["main_level_gap"]:
                add("QUEST009", q["line"], qid, f"메인 퀘스트 {p}(레벨 {main[p]['level_req']:g}) 다음이 레벨 {q['level_req']:g}. "
                                                "그 사이에 메인 퀘스트가 없는 구간")

    coverage = []
    by_level = defaultdict(float)
    for q in quests.values():
        if q["type"] != "daily":
            by_level[int(q["level_req"])] += q["reward_exp"]
    for lv in sorted(exp_for):
        coverage.append({"level": lv, "quest_exp": round(by_level.get(lv, 0)), "needed": round(exp_for[lv]),
                         "share": round(by_level.get(lv, 0) / exp_for[lv], 2) if exp_for[lv] else 0})

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["line"], f["rule"]))
    by_sev = Counter(f["severity"] for f in findings)
    summary = {"passed": by_sev.get("error", 0) == 0, "quests": len(quests),
               "by_type": dict(sorted(Counter(q["type"] for q in quests.values()).items())),
               "error": by_sev.get("error", 0), "warning": by_sev.get("warning", 0),
               "by_rule": dict(sorted(Counter(f["rule"] for f in findings).items()))}
    return {"summary": summary, "findings": findings, "coverage": coverage}


def to_markdown(report):
    s = report["summary"]
    types = ", ".join(f"{k} {v}" for k, v in s["by_type"].items())
    lines = ["# 퀘스트 데이터 검사 보고서", "", f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 퀘스트 {s['quests']}개 ({types})", f"- error {s['error']} / warning {s['warning']}", ""]
    if report["coverage"]:
        lines += ["## 레벨별 퀘스트 경험치 (일일 퀘스트 제외)", "", "| 레벨 | 퀘스트 경험치 | 필요 경험치 | 비중 |", "|---|---|---|---|"]
        lines += [f"| {c['level']} | {c['quest_exp']:,} | {c['needed']:,} | {c['share'] * 100:.0f}% |" for c in report["coverage"]]
        lines.append("")
    lines += ["## 지적 사항", "", "| 심각도 | 규칙 | 위치 | 내용 |", "|---|---|---|---|"]
    lines += [f"| {f['severity']} | {f['rule']} | {f['line']}행 {f['id']} | {f['message']} |" for f in report["findings"]]
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
    report = check(tables, config)
    for target, text in ((a.out, json.dumps(report, ensure_ascii=False, indent=2)), (a.md, to_markdown(report))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
