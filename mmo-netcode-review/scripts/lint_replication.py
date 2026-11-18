"""Unreal C++ 소스에서 리플리케이션/RPC 실수를 찾는 정적 검사기. Unreal 없이 실행되는 순수 Python.

    python lint_replication.py <Project>/Source --config lint-config.json --md report.md

정규식 기반이라 매크로를 중첩하거나 특이한 서식을 쓰면 놓칠 수 있다. 컴파일러를 대신하지 않는다.
특정 줄을 건너뛰려면 그 줄이나 바로 윗줄에 `// netlint:ignore NET003` 처럼 적는다.
종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter

DEFAULT_CONFIG = {
    "severity": {"NET001": "error", "NET002": "error", "NET003": "warning",
                 "NET004": "info", "NET005": "warning", "NET006": "info"},
    "skip_dirs": ["Intermediate", "Binaries", "ThirdParty", "Saved", ".git"],
    "authoritative_param_tokens": ["damage", "dmg", "gold", "money", "currency", "exp", "xp", "price",
                                   "cost", "reward", "health", "hp", "cooldown", "stat", "stats", "speed"],
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}

_MACRO = re.compile(r"\b(UPROPERTY|UFUNCTION)\s*\(")
_CLASS = re.compile(r"\b(enum\s+)?(?:class|struct)\s+(?:\w+_API\s+)?(\w+)\s*(?:final\s*)?[:{]")
_DOREP = re.compile(r"\b(DOREPLIFETIME\w*)\s*\(\s*(\w+)\s*,\s*(\w+)")
_IGNORE = re.compile(r"netlint:\s*ignore\b([^\n]*)")
_WORDS = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


def strip_comments(text):
    """주석과 문자열 내용을 공백으로 바꾼다. 줄 번호가 유지되도록 개행은 남긴다."""
    out, i, n = [], 0, len(text)
    while i < n:
        c, nxt = text[i], text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:j]))
            i = j
        elif c == '"':
            j = i + 1
            while j < n and text[j] != '"' and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append('"' + " " * max(j - i - 2, 0) + '"')
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _balanced(text, open_idx):
    """open_idx의 '('와 짝이 맞는 ')' 위치. 없으면 -1."""
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _split_top(s, sep=","):
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch in "(<[{":
            depth += 1
        elif ch in ")>]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def _last_identifier(decl):
    decl = _split_top(decl, "=")[0] if "=" in decl else decl
    decl = re.sub(r"\{[^}]*\}\s*$", "", decl.strip())
    decl = re.sub(r"\[[^\]]*\]\s*$", "", decl.strip())
    decl = re.sub(r":\s*\d+\s*$", "", decl.strip())
    ids = re.findall(r"[A-Za-z_]\w*", decl)
    return ids[-1] if ids else None


def _line(text, idx):
    return text.count("\n", 0, idx) + 1


def parse_header(raw):
    """헤더에서 리플리케이션 프로퍼티와 네트워크 함수를 뽑는다."""
    text = strip_comments(raw)
    classes = [(m.start(), m.group(2)) for m in _CLASS.finditer(text) if not m.group(1)]
    props, funcs = [], []
    for m in _MACRO.finditer(text):
        close = _balanced(text, m.end() - 1)
        if close < 0:
            continue
        specs_raw = _split_top(text[m.end():close])
        specs = {re.sub(r"\s*=\s*", "=", s).split("=")[0].lower(): re.sub(r"\s*=\s*", "=", s).partition("=")[2]
                 for s in specs_raw}
        cls = next((name for pos, name in reversed(classes) if pos < m.start()), None)
        line = _line(text, m.start())
        if m.group(1) == "UPROPERTY":
            if "replicated" not in specs and "replicatedusing" not in specs:
                continue
            end = text.find(";", close)
            if end < 0:
                continue
            decl = text[close + 1:end]
            props.append({"class": cls, "name": _last_identifier(decl), "line": line,
                          "onrep": specs.get("replicatedusing") or None,
                          "is_array": bool(re.search(r"\bTArray\s*<", decl))})
        else:
            if not ({"server", "client", "netmulticast"} & set(specs)):
                continue
            open_idx = text.find("(", close + 1)
            if open_idx < 0:
                continue
            pclose = _balanced(text, open_idx)
            name = _last_identifier(text[close + 1:open_idx])
            params = [_last_identifier(p) for p in _split_top(text[open_idx + 1:pclose])] if pclose > 0 else []
            funcs.append({"class": cls, "name": name, "line": line, "specs": set(specs),
                          "params": [p for p in params if p and p != "void"]})
    return text, props, funcs


def collect_registrations(cpp_texts):
    reg = set()
    for raw in cpp_texts:
        for m in _DOREP.finditer(strip_comments(raw)):
            if "ACTIVE_OVERRIDE" in m.group(1) or "CHANGE_CONDITION" in m.group(1):
                continue
            reg.add((m.group(2), m.group(3)))
    return reg


def _ignored(raw_lines, line, rule):
    for ln in (line, line - 1):
        if 1 <= ln <= len(raw_lines):
            m = _IGNORE.search(raw_lines[ln - 1])
            if m and (not m.group(1).strip() or rule in m.group(1)):
                return True
    return False


def lint(headers, cpps, config=None):
    """headers: {경로: 내용}, cpps: {경로: 내용}. 지적 사항 리스트를 반환한다."""
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    sev = dict(DEFAULT_CONFIG["severity"])
    sev.update((config or {}).get("severity", {}))
    tokens = set(cfg["authoritative_param_tokens"])
    # 헤더에 인라인으로 구현한 경우도 있으므로 헤더도 함께 본다
    registered = collect_registrations(list(cpps.values()) + list(headers.values()))
    registered_names = {name for _, name in registered}
    findings = []

    for path, raw in sorted(headers.items()):
        raw_lines = raw.split("\n")
        text, props, funcs = parse_header(raw)

        def add(rule, line, message):
            if not _ignored(raw_lines, line, rule):
                findings.append({"rule": rule, "severity": sev.get(rule, "warning"),
                                 "file": path, "line": line, "message": message})

        for p in props:
            if not p["name"]:
                continue
            who = f"{p['class']}::{p['name']}" if p["class"] else p["name"]
            if (p["class"], p["name"]) not in registered and p["name"] not in registered_names:
                add("NET001", p["line"], f"{who}: Replicated인데 DOREPLIFETIME 등록이 없음. 값이 복제되지 않음")
            if p["onrep"] and not re.search(r"\b" + re.escape(p["onrep"]) + r"\s*\(", text):
                add("NET002", p["line"], f"{who}: ReplicatedUsing={p['onrep']} 함수 선언이 이 헤더에 없음")
            if p["is_array"]:
                add("NET006", p["line"], f"{who}: TArray 복제. 항목이 많거나 자주 바뀌면 FFastArraySerializer 검토")

        for fn in funcs:
            who = f"{fn['class']}::{fn['name']}" if fn["class"] else str(fn["name"])
            if "netmulticast" in fn["specs"] and "reliable" in fn["specs"]:
                add("NET003", fn["line"], f"{who}: Reliable NetMulticast. 접속자 수만큼 신뢰성 전송이 생김. "
                                          "연출용이면 Unreliable로")
            if "server" in fn["specs"]:
                if "withvalidation" not in fn["specs"]:
                    add("NET004", fn["line"], f"{who}: Server RPC. 구현부에서 입력 검증을 하는지 확인")
                bad = [p for p in fn["params"] if tokens & {w.lower() for w in _WORDS.findall(p)}]
                if bad:
                    add("NET005", fn["line"], f"{who}: 클라이언트가 {', '.join(bad)} 값을 보냄. "
                                              "결과 값은 서버가 계산하고 클라이언트는 의도만 보내야 함")

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["file"], f["line"], f["rule"]))
    return findings


def read_sources(root, skip_dirs):
    headers, cpps = {}, {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in (".h", ".hpp", ".cpp", ".inl"):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8-sig", errors="replace") as f:
                (headers if ext in (".h", ".hpp") else cpps)[os.path.relpath(path, root)] = f.read()
    return headers, cpps


def summarize(findings, n_headers, n_cpps):
    by_sev = Counter(f["severity"] for f in findings)
    return {"passed": by_sev.get("error", 0) == 0, "headers": n_headers, "sources": n_cpps,
            "error": by_sev.get("error", 0), "warning": by_sev.get("warning", 0), "info": by_sev.get("info", 0),
            "by_rule": dict(sorted(Counter(f["rule"] for f in findings).items()))}


def to_markdown(summary, findings, max_rows=200):
    lines = ["# 넷코드 정적 검사 보고서", "",
             f"- 결과: {'통과' if summary['passed'] else '실패'}",
             f"- 헤더 {summary['headers']}개, 소스 {summary['sources']}개",
             f"- error {summary['error']} / warning {summary['warning']} / info {summary['info']}",
             "", "| 심각도 | 규칙 | 위치 | 내용 |", "|---|---|---|---|"]
    for f in findings[:max_rows]:
        lines.append(f"| {f['severity']} | {f['rule']} | `{f['file']}:{f['line']}` | {f['message']} |")
    if len(findings) > max_rows:
        lines += ["", f"나머지 {len(findings) - max_rows}건은 report.json 참조."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source_dir")
    ap.add_argument("--config")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.source_dir):
        print(f"소스 폴더 없음: {a.source_dir}", file=sys.stderr)
        return 2
    config = None
    if a.config:
        with open(a.config, encoding="utf-8") as f:
            config = json.load(f)
    skip = (config or {}).get("skip_dirs", DEFAULT_CONFIG["skip_dirs"])
    headers, cpps = read_sources(a.source_dir, skip)
    findings = lint(headers, cpps, config)
    summary = summarize(findings, len(headers), len(cpps))
    for target, text in ((a.out, json.dumps({"summary": summary, "findings": findings}, ensure_ascii=False, indent=2)),
                         (a.md, to_markdown(summary, findings))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
