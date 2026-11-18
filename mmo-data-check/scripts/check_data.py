"""게임 데이터 테이블(CSV)을 스키마와 비교해 검사한다. Unreal 없이 실행되는 순수 Python.

    python check_data.py <데이터 폴더> --schema data-schema.json --md report.md

검사 내용은 전부 스키마(JSON)에 적는다. 종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict

SEVERITY = {
    "DATA001": "error", "DATA002": "error", "DATA003": "error", "DATA004": "error",
    "DATA005": "error", "DATA006": "error", "DATA007": "error", "DATA008": "error",
    "DATA009": "error", "DATA010": "error", "DATA011": "error", "DATA012": "warning",
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
_TRUE, _FALSE = {"true", "1", "yes"}, {"false", "0", "no"}


def _parse(raw, col):
    """(값, 오류 메시지)를 반환한다. 타입이 맞지 않으면 값은 None."""
    t = col.get("type", "str")
    try:
        if t == "int":
            return int(raw), None
        if t == "float":
            return float(raw), None
        if t == "bool":
            if raw.lower() in _TRUE:
                return True, None
            if raw.lower() in _FALSE:
                return False, None
            raise ValueError
        return raw, None
    except ValueError:
        return None, f"'{raw}'은(는) {t} 형식이 아님"


class Checker:
    def __init__(self, schema, severity=None):
        self.schema = schema
        self.severity = dict(SEVERITY)
        self.severity.update(schema.get("severity", {}))
        self.severity.update(severity or {})
        self.findings = []
        self.tables = {}   # name -> list of {"_line": n, col: parsed value or None}
        self.loaded = {}   # name -> bool
        self.row_count = 0

    def add(self, rule, table, line, column, message):
        self.findings.append({"rule": rule, "severity": self.severity.get(rule, "error"),
                              "table": table, "line": line, "column": column, "message": message})

    # ---- 1단계: 읽기와 열 단위 검사 -------------------------------------------------
    def load(self, data_dir):
        for name, tdef in self.schema.get("tables", {}).items():
            path = os.path.join(data_dir, tdef["file"])
            self.loaded[name] = False
            self.tables[name] = []
            if not os.path.isfile(path):
                self.add("DATA001", name, 0, "", f"파일 없음: {tdef['file']}")
                continue
            with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
                reader = csv.DictReader(f)
                header = [h.strip() for h in (reader.fieldnames or [])]
                reader.fieldnames = header
                missing = [c for c in tdef.get("columns", {}) if c not in header]
                for c in missing:
                    self.add("DATA002", name, 1, c, f"열 '{c}' 없음")
                if missing:
                    continue
                self.loaded[name] = True
                for i, raw_row in enumerate(reader, start=2):
                    if not any((v or "").strip() for v in raw_row.values()):
                        continue
                    self.tables[name].append(self._check_row(name, tdef, i, raw_row))
            self.row_count += len(self.tables[name])
            self._check_key(name, tdef)

    def _check_row(self, name, tdef, line, raw_row):
        row = {"_line": line}
        for cname, col in tdef.get("columns", {}).items():
            raw = (raw_row.get(cname) or "").strip()
            if raw == "":
                row[cname] = None
                if col.get("required"):
                    self.add("DATA008", name, line, cname, "필수 값이 비어 있음")
                continue
            parts = [p.strip() for p in raw.split(col["sep"])] if col.get("sep") else [raw]
            parsed = []
            for part in parts:
                v, err = _parse(part, col)
                if err:
                    self.add("DATA004", name, line, cname, err)
                    continue
                if "min" in col and v < col["min"]:
                    self.add("DATA005", name, line, cname, f"{v}이(가) 최소 {col['min']}보다 작음")
                if "max" in col and v > col["max"]:
                    self.add("DATA005", name, line, cname, f"{v}이(가) 최대 {col['max']}보다 큼")
                if "values" in col and v not in col["values"]:
                    self.add("DATA006", name, line, cname, f"'{v}'은(는) 허용 값 {col['values']}에 없음")
                parsed.append(v)
            row[cname] = parsed if col.get("sep") else (parsed[0] if parsed else None)
        return row

    def _check_key(self, name, tdef):
        key = tdef.get("key")
        if not key or not self.loaded[name]:
            return
        seen = Counter(r[key] for r in self.tables[name] if r.get(key) is not None)
        for r in self.tables[name]:
            if r.get(key) is not None and seen[r[key]] > 1:
                self.add("DATA003", name, r["_line"], key, f"키 {r[key]} 중복")

    # ---- 2단계: 테이블 간, 행 간 검사 -----------------------------------------------
    def cross_check(self):
        for name, tdef in self.schema.get("tables", {}).items():
            if not self.loaded.get(name):
                continue
            rows = self.tables[name]
            for cname, col in tdef.get("columns", {}).items():
                if "ref" in col:
                    self._check_ref(name, rows, cname, col)
            for chk in tdef.get("checks", []):
                getattr(self, "_chk_" + chk["type"])(name, rows, chk)

    def _check_ref(self, name, rows, cname, col):
        rtable, rcol = col["ref"].split(".")
        if not self.loaded.get(rtable):
            return  # 대상 테이블 문제는 이미 DATA001/002로 보고됨
        targets = {r[rcol] for r in self.tables[rtable] if r.get(rcol) is not None}
        allow = set(col.get("ref_allow", []))
        for r in rows:
            v = r.get(cname)
            for item in (v if isinstance(v, list) else [v]):
                if item is None or item in allow or item in targets:
                    continue
                self.add("DATA007", name, r["_line"], cname, f"{col['ref']}에 {item}이(가) 없음")

    def _chk_sum(self, name, rows, chk):
        groups = defaultdict(list)
        for r in rows:
            if r.get(chk["column"]) is not None:
                groups[r.get(chk["group_by"])].append(r)
        for g, members in groups.items():
            total = sum(m[chk["column"]] for m in members)
            eps = 1e-9
            if "max" in chk and total > chk["max"] + eps:
                self.add("DATA009", name, members[0]["_line"], chk["column"],
                         f"{chk['group_by']}={g}의 합 {total:.4f}이(가) 최대 {chk['max']}을 넘음")
            if "equals" in chk and abs(total - chk["equals"]) > chk.get("tolerance", 1e-6):
                self.add("DATA009", name, members[0]["_line"], chk["column"],
                         f"{chk['group_by']}={g}의 합 {total:.4f}이(가) {chk['equals']}이 아님")

    def _chk_lte(self, name, rows, chk):
        for r in rows:
            a, b = r.get(chk["left"]), r.get(chk["right"])
            if chk.get("skip_when_right_zero") and b == 0:
                continue  # 예: 구매가 0은 상점에서 팔지 않는 아이템이라 되팔기 차익이 생기지 않는다
            if a is not None and b is not None and a > b:
                self.add("DATA010", name, r["_line"], chk["left"],
                         f"{chk['left']}({a})이(가) {chk['right']}({b})보다 큼"
                         + (f". {chk['why']}" if chk.get("why") else ""))

    def _chk_increasing(self, name, rows, chk):
        usable = [r for r in rows if r.get(chk["order_by"]) is not None and r.get(chk["column"]) is not None]
        usable.sort(key=lambda r: r[chk["order_by"]])
        for prev, cur in zip(usable, usable[1:]):
            if cur[chk["column"]] <= prev[chk["column"]]:
                self.add("DATA011", name, cur["_line"], chk["column"],
                         f"{chk['order_by']}={cur[chk['order_by']]}의 값 {cur[chk['column']]}이(가) "
                         f"이전 값 {prev[chk['column']]}보다 커야 함")

    def _chk_contiguous(self, name, rows, chk):
        vals = sorted({r[chk["column"]] for r in rows if r.get(chk["column"]) is not None})
        if not vals:
            return
        gaps = sorted(set(range(vals[0], vals[-1] + 1)) - set(vals))
        if gaps:
            shown = ", ".join(map(str, gaps[:10])) + (" ..." if len(gaps) > 10 else "")
            self.add("DATA012", name, 0, chk["column"], f"빠진 값: {shown}")

    # ---- 결과 ----------------------------------------------------------------------
    def report(self):
        self.findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["table"], f["line"], f["rule"]))
        by_sev = Counter(f["severity"] for f in self.findings)
        summary = {
            "passed": by_sev.get("error", 0) == 0,
            "tables": len(self.schema.get("tables", {})),
            "rows": self.row_count,
            "error": by_sev.get("error", 0),
            "warning": by_sev.get("warning", 0),
            "by_rule": dict(sorted(Counter(f["rule"] for f in self.findings).items())),
            "by_table": dict(sorted(Counter(f["table"] for f in self.findings).items())),
        }
        return {"summary": summary, "findings": self.findings}


def check(data_dir, schema):
    c = Checker(schema)
    c.load(data_dir)
    c.cross_check()
    return c.report()


def to_markdown(report, max_rows=200):
    s = report["summary"]
    lines = ["# 게임 데이터 검사 보고서", "",
             f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 테이블 {s['tables']}개, 행 {s['rows']}개",
             f"- error {s['error']} / warning {s['warning']}",
             "", "## 테이블별 개수", "", "| 테이블 | 개수 |", "|---|---|"]
    lines += [f"| {t} | {n} |" for t, n in s["by_table"].items()] or ["| 없음 | 0 |"]
    lines += ["", "## 지적 사항", "", "| 심각도 | 규칙 | 위치 | 내용 |", "|---|---|---|---|"]
    for f in report["findings"][:max_rows]:
        where = f"{f['table']}:{f['line']}" + (f" [{f['column']}]" if f["column"] else "")
        lines.append(f"| {f['severity']} | {f['rule']} | {where} | {f['message']} |")
    if len(report["findings"]) > max_rows:
        lines += ["", f"나머지 {len(report['findings']) - max_rows}건은 report.json 참조."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("data_dir")
    ap.add_argument("--schema", required=True)
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.data_dir):
        print(f"데이터 폴더 없음: {a.data_dir}", file=sys.stderr)
        return 2
    with open(a.schema, encoding="utf-8") as f:
        schema = json.load(f)
    report = check(a.data_dir, schema)
    for target, text in ((a.out, json.dumps(report, ensure_ascii=False, indent=2)), (a.md, to_markdown(report))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
