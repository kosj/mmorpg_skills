"""현지화 문자열 표(CSV)를 검사한다. 순수 Python.

    python check_strings.py strings.csv --config loc-config.json [--used-keys keys.txt] --md report.md

빠진 번역, 원문과 다른 자리표시자와 서식 태그, 닫히지 않은 괄호, 화면 폭을 넘는 길이, 번역되지 않은
문자열, 게임이 쓰는데 표에 없는 키를 찾는다. 번역의 품질은 판단하지 않는다.
종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import csv
import json
import os
import re
import sys
import unicodedata
from collections import Counter

DEFAULT_CONFIG = {
    "key_column": "key",
    "source_language": "ko",
    "required_languages": ["en"],
    "optional_languages": [],
    "max_width_column": "max_width",
    "wide_char_width": 2,
    "expansion_limit": {"default": 2.5},
    "expansion_min_source_width": 8,
    "same_as_source_ok_pattern": "^[\\W\\d_]*$",
    "severity": {"LOC001": "error", "LOC002": "error", "LOC003": "error", "LOC004": "warning",
                 "LOC005": "warning", "LOC006": "warning", "LOC007": "error", "LOC008": "error"},
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
_BRACE = re.compile(r"\{([^{}]*)\}")
_PRINTF = re.compile(r"%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?[sdifuxX]")
_TAG = re.compile(r"<(/?)([A-Za-z][\w.]*)[^<>]*>")


def _cfg(config):
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    cfg["severity"] = dict(DEFAULT_CONFIG["severity"], **(config or {}).get("severity", {}))
    cfg["expansion_limit"] = dict(DEFAULT_CONFIG["expansion_limit"], **(config or {}).get("expansion_limit", {}))
    return cfg


def width(text, wide=2):
    """화면 폭 어림: 한글, 한자, 가나 같은 전각 문자는 wide, 나머지는 1. 자리표시자와 태그는 빼고 센다."""
    text = _TAG.sub("", _PRINTF.sub("", _BRACE.sub("", text)))
    return sum(wide if unicodedata.east_asian_width(ch) in ("W", "F") else 1 for ch in text)


def placeholders(text):
    """자리표시자와 서식 태그를 모아 정렬한 목록. 순서가 바뀌는 것은 허용한다."""
    found = ["{" + m + "}" for m in _BRACE.findall(text)]
    found += _PRINTF.findall(text.replace("%%", ""))
    found += ["<" + slash + name + ">" for slash, name in _TAG.findall(text)]
    return sorted(found)


def unbalanced(text):
    """닫히지 않은 중괄호나 서식 태그가 있으면 설명을, 없으면 None을 돌려준다."""
    depth = 0
    for ch in text:
        depth += ch == "{"
        depth -= ch == "}"
        if depth < 0 or depth > 1:
            return "중괄호가 맞지 않음"
    if depth:
        return "중괄호가 닫히지 않음"
    stack = []
    for slash, name in _TAG.findall(text):
        if not slash:
            stack.append(name)
        elif not stack or stack.pop() != name:
            return f"서식 태그 </{name}>의 짝이 맞지 않음"
    return f"서식 태그 <{stack[-1]}>이(가) 닫히지 않음" if stack else None


def check(rows, config=None, used_keys=None):
    """rows: [(줄 번호, {열: 문자열})]"""
    cfg = _cfg(config)
    findings = []
    src, key_col = cfg["source_language"], cfg["key_column"]
    langs = [(l, True) for l in cfg["required_languages"]] + [(l, False) for l in cfg["optional_languages"]]
    ok_same = re.compile(cfg["same_as_source_ok_pattern"])
    wide = cfg["wide_char_width"]

    def add(rule, line, key, lang, message, severity=None):
        findings.append({"rule": rule, "severity": severity or cfg["severity"][rule], "line": line,
                         "key": key, "lang": lang, "message": message})

    seen = {}
    for line, row in rows:
        key = (row.get(key_col) or "").strip()
        if not key:
            add("LOC001", line, "", "", "키가 비어 있음")
            continue
        if key in seen:
            add("LOC001", line, key, "", f"키 중복 ({seen[key]}행에도 있음)")
            continue
        seen[key] = line
        source = row.get(src) or ""
        if not source.strip():
            add("LOC002", line, key, src, "원문이 비어 있음")
            continue
        problem = unbalanced(source)
        if problem:
            add("LOC007", line, key, src, problem)
        src_ph, src_w = placeholders(source), width(source, wide)
        limit = (row.get(cfg["max_width_column"]) or "").strip()
        limit = int(limit) if limit.isdigit() else None
        if limit and src_w > limit:
            add("LOC004", line, key, src, f"폭 {src_w}이(가) 제한 {limit}을 넘음")

        for lang, required in langs:
            text = row.get(lang)
            if text is None or not text.strip():
                add("LOC002", line, key, lang, "번역이 비어 있음", None if required else "warning")
                continue
            problem = unbalanced(text)
            if problem:
                add("LOC007", line, key, lang, problem)
            ph = placeholders(text)
            if ph != src_ph:
                missing = [p for p in src_ph if p not in ph or src_ph.count(p) > ph.count(p)]
                extra = [p for p in ph if p not in src_ph or ph.count(p) > src_ph.count(p)]
                parts = ([f"빠짐: {' '.join(sorted(set(missing)))}"] if missing else []) + \
                        ([f"원문에 없음: {' '.join(sorted(set(extra)))}"] if extra else [])
                add("LOC003", line, key, lang, "자리표시자나 서식 태그가 원문과 다름 (" + ", ".join(parts) + ")")
            w = width(text, wide)
            if limit:
                if w > limit:
                    add("LOC004", line, key, lang, f"폭 {w}이(가) 제한 {limit}을 넘음")
            else:
                ratio = cfg["expansion_limit"].get(lang, cfg["expansion_limit"]["default"])
                if src_w >= cfg["expansion_min_source_width"] and w > src_w * ratio:
                    add("LOC004", line, key, lang, f"폭 {w}이(가) 원문 {src_w}의 {w / src_w:.1f}배. UI에서 잘릴 수 있음")
            if text.strip() == source.strip() and not ok_same.match(_TAG.sub("", _BRACE.sub("", source))):
                add("LOC005", line, key, lang, "번역이 원문과 같음. 번역되지 않았을 수 있음")
            if text != text.strip() and source == source.strip():
                add("LOC006", line, key, lang, "앞이나 뒤에 원문에 없는 공백이 있음")
            elif "  " in text and "  " not in source:
                add("LOC006", line, key, lang, "연속된 공백이 있음")

    if used_keys is not None:
        for key in sorted(set(used_keys) - set(seen)):
            add("LOC008", 0, key, "", "게임이 쓰는 키인데 문자열 표에 없음")

    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["line"], f["rule"], f["lang"]))
    by_sev = Counter(f["severity"] for f in findings)
    total = len(seen)
    coverage = {}
    for lang, _ in langs:
        done = sum(1 for _, row in rows if (row.get(key_col) or "").strip() and (row.get(lang) or "").strip())
        coverage[lang] = round(done / total, 3) if total else 0
    summary = {"passed": by_sev.get("error", 0) == 0, "keys": total, "coverage": coverage,
               "unused_keys": len(set(seen) - set(used_keys)) if used_keys is not None else None,
               "error": by_sev.get("error", 0), "warning": by_sev.get("warning", 0),
               "by_rule": dict(sorted(Counter(f["rule"] for f in findings).items()))}
    return {"summary": summary, "findings": findings}


def to_markdown(report, max_rows=300):
    s = report["summary"]
    cov = ", ".join(f"{l} {v * 100:.0f}%" for l, v in s["coverage"].items())
    lines = ["# 현지화 문자열 검사 보고서", "", f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 키 {s['keys']}개, 번역률: {cov}", f"- error {s['error']} / warning {s['warning']}"]
    if s["unused_keys"] is not None:
        lines.append(f"- 게임이 쓰지 않는 키: {s['unused_keys']}개")
    lines += ["", "| 심각도 | 규칙 | 위치 | 언어 | 내용 |", "|---|---|---|---|---|"]
    for f in report["findings"][:max_rows]:
        where = f"{f['line']}행 {f['key']}" if f["line"] else f["key"]
        lines.append(f"| {f['severity']} | {f['rule']} | {where} | {f['lang'] or '-'} | {f['message']} |")
    if len(report["findings"]) > max_rows:
        lines += ["", f"나머지 {len(report['findings']) - max_rows}건은 report.json 참조."]
    return "\n".join(lines) + "\n"


def read_csv(path, cfg):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        header = [h.strip() for h in (reader.fieldnames or [])]
        need = [cfg["key_column"], cfg["source_language"]] + cfg["required_languages"]
        missing = [c for c in need if c not in header]
        if missing:
            raise ValueError("열 없음: " + ", ".join(missing))
        reader.fieldnames = header
        return [(i, row) for i, row in enumerate(reader, start=2) if any((v or "").strip() for v in row.values())]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("strings_csv")
    ap.add_argument("--config")
    ap.add_argument("--used-keys", help="게임이 쓰는 키가 한 줄에 하나씩 적힌 파일")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    try:
        config = None
        if a.config:
            with open(a.config, encoding="utf-8") as f:
                config = json.load(f)
        rows = read_csv(a.strings_csv, _cfg(config))
        used = None
        if a.used_keys:
            with open(a.used_keys, encoding="utf-8-sig") as f:
                used = [line.strip() for line in f if line.strip()]
    except (OSError, ValueError) as e:
        print(f"입력을 읽지 못함: {e}", file=sys.stderr)
        return 2
    report = check(rows, config, used)
    for target, text in ((a.out, json.dumps(report, ensure_ascii=False, indent=2)), (a.md, to_markdown(report))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
