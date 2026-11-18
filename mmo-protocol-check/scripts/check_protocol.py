"""FlatBuffers 스키마(.fbs)로 정의한 게임 프로토콜을 검사한다. flatc 없이 실행되는 순수 Python.

    python check_protocol.py <스키마 폴더> --config protocol-config.json --lock protocol.lock.json
    python check_protocol.py <스키마 폴더> --lock protocol.lock.json --update-lock
    python check_protocol.py <스키마 폴더> --emit-header PacketMeta.generated.h

문법 검사는 flatc가 한다. 이 도구는 flatc가 보지 않는 프로젝트 규칙을 본다.
특정 줄을 건너뛰려면 그 줄이나 바로 윗줄에 `// protolint:ignore PROTO004 이유`를 적는다.
종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, defaultdict

DEFAULT_CONFIG = {
    "severity": {"PROTO001": "error", "PROTO002": "error", "PROTO003": "error", "PROTO004": "warning",
                 "PROTO005": "error", "PROTO006": "warning", "PROTO007": "error", "PROTO008": "error",
                 "PROTO009": "info", "PROTO010": "info"},
    "c2s_prefixes": ["C2S_", "CS_"],
    "s2c_prefixes": ["S2C_", "SC_"],
    "packet_id_min": 1,
    "packet_id_max": 65535,
    "authoritative_field_tokens": ["damage", "dmg", "gold", "money", "currency", "exp", "xp", "price", "cost",
                                   "reward", "health", "hp", "cooldown", "stat", "stats", "speed"],
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
CUSTOM_ATTRS = {"packet_id", "dir", "rate", "max_len"}
BUILTIN_ATTRS = {
    "id", "deprecated", "required", "key", "hash", "force_align", "bit_flags", "nested_flatbuffer",
    "flexbuffer", "shared", "original_order", "private", "streaming", "idempotent", "vector64", "offset64",
    "native_inline", "native_default", "native_custom_alloc", "native_type", "native_type_pack_name",
    "cpp_type", "cpp_ptr_type", "cpp_ptr_type_get", "cpp_str_type", "cpp_str_flex_ctor", "cpp_vec_type",
    "csharp_partial",
}

_DECL = re.compile(r"\b(table|struct|enum|union)\s+(\w+)\s*(?::\s*([\w.]+)\s*)?(?:\(([^)]*)\)\s*)?\{([^{}]*)\}", re.S)
_NAMESPACE = re.compile(r"\bnamespace\s+([\w.]+)\s*;")
_ATTR_DECL = re.compile(r'\battribute\s+"?(\w+)"?\s*;')
_FIELD = re.compile(r"^\s*(\w+)\s*:\s*(\[?\s*[\w.]+\s*(?::\s*\d+)?\s*\]?)\s*(?:=\s*([^()]+?))?\s*(?:\(([^)]*)\))?\s*$", re.S)
_IGNORE = re.compile(r"protolint:\s*ignore\b([^\n]*)")
_WORDS = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


def strip_comments(text):
    """주석을 공백으로 바꾼다. 문자열은 그대로 두고 줄 번호가 유지되도록 개행은 남긴다."""
    out, i, n = [], 0, len(text)
    while i < n:
        c, nxt = text[i], text[i + 1] if i + 1 < n else ""
        if c == '"':
            j = text.find('"', i + 1)
            j = n if j < 0 else j + 1
            out.append(text[i:j])
            i = j
        elif c == "/" and nxt == "/":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif c == "/" and nxt == "*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(ch if ch == "\n" else " " for ch in text[i:j]))
            i = j
        else:
            out.append(c)
            i += 1
    return "".join(out)


def parse_attrs(s):
    attrs = {}
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        key, _, val = part.partition(":")
        val = val.strip().strip('"')
        attrs[key.strip()] = True if val == "" else (int(val) if re.fullmatch(r"-?\d+", val) else val)
    return attrs


def _line(text, idx):
    return text.count("\n", 0, idx) + 1


def parse_file(path, raw):
    text = strip_comments(raw)
    namespaces = [(m.start(), m.group(1)) for m in _NAMESPACE.finditer(text)]
    declared = set(_ATTR_DECL.findall(text))
    decls = []
    for m in _DECL.finditer(text):
        kind, name, underlying, attrs, body = m.groups()
        ns = next((n for pos, n in reversed(namespaces) if pos < m.start()), "")
        d = {"kind": kind, "name": name, "ns": ns, "qual": f"{ns}.{name}" if ns else name, "file": path,
             "line": _line(text, m.start()), "attrs": parse_attrs(attrs), "underlying": underlying,
             "fields": [], "values": {}}
        body_start = m.start(5)
        if kind in ("table", "struct"):
            offset = 0
            for chunk in body.split(";"):
                fm = _FIELD.match(chunk)
                if fm:
                    lead = len(chunk) - len(chunk.lstrip())
                    d["fields"].append({"name": fm.group(1), "type": re.sub(r"\s+", "", fm.group(2)),
                                        "attrs": parse_attrs(fm.group(4)),
                                        "line": _line(text, body_start + offset + lead)})
                offset += len(chunk) + 1
        elif kind == "enum":
            nxt = 0
            for item in body.split(","):
                item = item.strip()
                if not item:
                    continue
                vname, _, val = item.partition("=")
                nxt = int(val.strip(), 0) if val.strip() else nxt
                d["values"][vname.strip()] = nxt
                nxt += 1
        else:
            d["values"] = {v.strip().split(":")[0].strip(): i + 1
                           for i, v in enumerate(x for x in body.split(",") if x.strip())}
        decls.append(d)
    return declared, decls


class Schema:
    def __init__(self, files):
        """files: {경로: 내용}"""
        self.raw_lines = {p: raw.split("\n") for p, raw in files.items()}
        self.declared_attrs = set()
        self.decls = {}
        self.by_short = defaultdict(list)
        for path in sorted(files):
            declared, decls = parse_file(path, files[path])
            self.declared_attrs |= declared
            for d in decls:
                self.decls[d["qual"]] = d
                self.by_short[d["name"]].append(d)

    def resolve(self, type_name, ns=""):
        base = re.sub(r"[\[\]]|:\d+", "", type_name)
        for cand in (base, f"{ns}.{base}" if ns else None):
            if cand and cand in self.decls:
                return self.decls[cand]
        short = self.by_short.get(base.rsplit(".", 1)[-1], [])
        return short[0] if len(short) == 1 else None

    def slots(self, d):
        """필드별 슬롯 번호. id 속성이 없으면 선언 순서이고, union은 두 칸을 쓴다."""
        out, pos = [], 0
        for f in d["fields"]:
            target = None if f["type"].startswith("[") else self.resolve(f["type"], d["ns"])
            is_union = bool(target and target["kind"] == "union")
            slot = f["attrs"]["id"] if isinstance(f["attrs"].get("id"), int) else pos + (1 if is_union else 0)
            pos += 2 if is_union else 1
            out.append(slot)
        return out

    def snapshot(self):
        types = {}
        for q, d in sorted(self.decls.items()):
            entry = {"kind": d["kind"]}
            if d["kind"] in ("table", "struct"):
                entry["fields"] = [{"name": f["name"], "type": f["type"], "slot": s,
                                    "deprecated": bool(f["attrs"].get("deprecated"))}
                                   for f, s in zip(d["fields"], self.slots(d))]
            else:
                entry["values"] = d["values"]
                entry["underlying"] = d["underlying"]
            types[q] = entry
        return types


def direction(d, cfg):
    v = d["attrs"].get("dir")
    if isinstance(v, str) and v.lower() in ("c2s", "s2c"):
        return v.lower()
    if any(d["name"].startswith(p) for p in cfg["c2s_prefixes"]):
        return "c2s"
    if any(d["name"].startswith(p) for p in cfg["s2c_prefixes"]):
        return "s2c"
    return None


def packets(schema, cfg):
    out = []
    for d in schema.decls.values():
        if d["kind"] != "table":
            continue
        dr = direction(d, cfg)
        if dr or "packet_id" in d["attrs"]:
            out.append((d, dr))
    return sorted(out, key=lambda x: (x[0]["file"], x[0]["line"]))


def check(files, config=None, lock=None, lock_given=False):
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    sev = dict(DEFAULT_CONFIG["severity"])
    sev.update((config or {}).get("severity", {}))
    tokens = set(cfg["authoritative_field_tokens"])
    schema = Schema(files)
    findings = []

    def add(rule, d, line, message):
        lines = schema.raw_lines.get(d["file"], [])
        for ln in (line, line - 1):
            if 1 <= ln <= len(lines):
                m = _IGNORE.search(lines[ln - 1])
                if m and (not m.group(1).strip() or rule in m.group(1)):
                    return
        findings.append({"rule": rule, "severity": sev.get(rule, "warning"),
                         "file": d["file"], "line": line, "message": message})

    # PROTO008: 선언하지 않은 사용자 속성 (flatc가 거부한다)
    for d in schema.decls.values():
        for holder, line in [(d, d["line"])] + [(f, f["line"]) for f in d["fields"]]:
            for a in holder["attrs"]:
                if a not in BUILTIN_ATTRS and a not in schema.declared_attrs:
                    add("PROTO008", d, line, f"속성 '{a}'을(를) 쓰지만 `attribute \"{a}\";` 선언이 없음")

    pk = packets(schema, cfg)
    by_id = defaultdict(list)
    for d, dr in pk:
        pid = d["attrs"].get("packet_id")
        if not isinstance(pid, int):
            add("PROTO002", d, d["line"], f"{d['name']}: 패킷인데 packet_id가 없음")
        elif not cfg["packet_id_min"] <= pid <= cfg["packet_id_max"]:
            add("PROTO002", d, d["line"], f"{d['name']}: packet_id {pid}이(가) 범위 "
                                          f"{cfg['packet_id_min']}~{cfg['packet_id_max']} 밖")
        else:
            by_id[pid].append(d)
        if dr is None:
            add("PROTO002", d, d["line"], f"{d['name']}: 방향을 알 수 없음. dir 속성이나 이름 접두사(C2S_/S2C_) 필요")

    for pid, ds in sorted(by_id.items()):
        if len(ds) > 1:
            names = ", ".join(x["name"] for x in ds)
            for d in ds:
                add("PROTO001", d, d["line"], f"packet_id {pid} 중복: {names}")

    # 클라이언트 → 서버 패킷: 포함하는 테이블까지 따라가며 검사한다
    seen_fields = set()
    for d, dr in pk:
        if dr != "c2s":
            continue
        if not isinstance(d["attrs"].get("rate"), int):
            add("PROTO006", d, d["line"], f"{d['name']}: 초당 허용 횟수(rate)가 없음")
        stack, visited = [d], set()
        while stack:
            t = stack.pop()
            if t["qual"] in visited:
                continue
            visited.add(t["qual"])
            for f in t["fields"]:
                target = schema.resolve(f["type"], t["ns"])
                if target and target["kind"] == "table":
                    stack.append(target)
                if target and target["kind"] == "union":
                    stack.extend(x for x in (schema.resolve(v, target["ns"]) for v in target["values"]) if x)
                key = (t["qual"], f["name"])
                if key in seen_fields or f["attrs"].get("deprecated"):
                    continue
                seen_fields.add(key)
                via = "" if t is d else f" ({d['name']}에서 사용)"
                if tokens & {w.lower() for w in _WORDS.findall(f["name"])}:
                    add("PROTO004", t, f["line"], f"{t['name']}.{f['name']}{via}: 클라이언트가 결과 값을 보냄. "
                                                  "의도만 보내고 수치는 서버가 계산해야 함")
                if (f["type"] == "string" or f["type"].startswith("[")) and not isinstance(f["attrs"].get("max_len"), int):
                    add("PROTO005", t, f["line"], f"{t['name']}.{f['name']}{via}: 가변 길이 필드에 max_len이 없음")

    # lock 파일과 비교
    if lock is None:
        if lock_given:
            any_decl = next(iter(schema.decls.values()), None)
            if any_decl:
                findings.append({"rule": "PROTO010", "severity": sev["PROTO010"], "file": "", "line": 0,
                                 "message": "lock 파일이 없어 ID 재사용과 호환성 검사를 건너뜀. --update-lock으로 생성"})
    else:
        locked_ids = {int(k): v for k, v in lock.get("packets", {}).items()}
        locked_names = {v: k for k, v in locked_ids.items()}
        for d, _ in pk:
            pid = d["attrs"].get("packet_id")
            if not isinstance(pid, int):
                continue
            if pid in locked_ids and locked_ids[pid] != d["qual"]:
                add("PROTO003", d, d["line"], f"packet_id {pid}은(는) 이전에 {locked_ids[pid]}에 쓰였음. "
                                              "ID는 재사용하지 않는다")
            elif d["qual"] in locked_names and locked_names[d["qual"]] != pid:
                add("PROTO003", d, d["line"], f"{d['name']}의 packet_id가 {locked_names[d['qual']]}에서 {pid}(으)로 바뀜")
        current = schema.snapshot()
        for q, old in lock.get("types", {}).items():
            d, cur = schema.decls.get(q), current.get(q)
            if not cur:
                continue
            if cur["kind"] != old["kind"]:
                add("PROTO007", d, d["line"], f"{q}: {old['kind']}에서 {cur['kind']}(으)로 바뀜")
            elif old["kind"] == "table":
                by_slot = {f["slot"]: (f, src) for f, src in zip(cur["fields"], d["fields"])}
                for of in old["fields"]:
                    hit = by_slot.get(of["slot"])
                    if not hit:
                        add("PROTO007", d, d["line"], f"{q}.{of['name']}: 필드가 사라짐. 지우지 말고 (deprecated)로 표시")
                    elif hit[0]["type"] != of["type"]:
                        add("PROTO007", d, hit[1]["line"], f"{q}: 슬롯 {of['slot']}의 타입이 {of['type']}에서 "
                                                           f"{hit[0]['type']}(으)로 바뀜. 필드 순서를 바꾸거나 중간에 끼워 넣지 않았는지 확인")
                    elif hit[0]["name"] != of["name"]:
                        add("PROTO009", d, hit[1]["line"], f"{q}: 필드 이름이 {of['name']}에서 {hit[0]['name']}(으)로 바뀜. "
                                                           "바이너리는 호환되지만 양쪽 코드를 함께 고쳐야 함")
            elif old["kind"] == "struct":
                if [(f["name"], f["type"]) for f in cur["fields"]] != [(f["name"], f["type"]) for f in old["fields"]]:
                    add("PROTO007", d, d["line"], f"{q}: struct는 한번 정하면 바꿀 수 없음. 새 struct를 만들 것")
            else:
                if cur.get("underlying") != old.get("underlying"):
                    add("PROTO007", d, d["line"], f"{q}: 기반 타입이 {old.get('underlying')}에서 {cur.get('underlying')}(으)로 바뀜")
                for vname, v in old["values"].items():
                    if vname not in cur["values"]:
                        add("PROTO007", d, d["line"], f"{q}.{vname}: 값이 사라짐")
                    elif cur["values"][vname] != v:
                        add("PROTO007", d, d["line"], f"{q}.{vname}: 값이 {v}에서 {cur['values'][vname]}(으)로 바뀜")

    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["file"], f["line"], f["rule"]))
    by_sev = Counter(f["severity"] for f in findings)
    summary = {"passed": by_sev.get("error", 0) == 0, "files": len(files), "types": len(schema.decls),
               "packets": len(pk), "c2s": sum(1 for _, dr in pk if dr == "c2s"),
               "s2c": sum(1 for _, dr in pk if dr == "s2c"),
               "error": by_sev.get("error", 0), "warning": by_sev.get("warning", 0), "info": by_sev.get("info", 0),
               "by_rule": dict(sorted(Counter(f["rule"] for f in findings).items()))}
    return {"summary": summary, "findings": findings}, schema, pk


def make_lock(schema, pk, old_lock=None):
    """현재 스키마로 lock을 만든다. 예전에 쓴 packet_id는 지우지 않고 남긴다."""
    ids = dict((old_lock or {}).get("packets", {}))
    for d, _ in pk:
        if isinstance(d["attrs"].get("packet_id"), int):
            ids[str(d["attrs"]["packet_id"])] = d["qual"]
    return {"version": 1, "packets": dict(sorted(ids.items(), key=lambda kv: int(kv[0]))),
            "types": schema.snapshot()}


def emit_header(pk):
    rows = sorted(((d["attrs"]["packet_id"], d, dr) for d, dr in pk
                   if isinstance(d["attrs"].get("packet_id"), int) and dr), key=lambda r: r[0])
    out = ["// 자동 생성 파일. 직접 고치지 말 것. check_protocol.py --emit-header 로 다시 만든다.",
           "#pragma once", "#include <cstdint>", "", "namespace PacketMeta", "{",
           "enum class EPacketId : uint16_t", "{"]
    out += [f"    {d['name']} = {pid}," for pid, d, _ in rows]
    out += ["};", "",
            "struct FPacketInfo", "{", "    uint16_t Id;", "    const char* Name;",
            "    bool bClientToServer;", "    uint16_t MaxPerSecond; // 0이면 제한 없음(서버가 보내는 패킷)", "};", "",
            "inline constexpr FPacketInfo Packets[] =", "{"]
    for pid, d, dr in rows:
        rate = d["attrs"].get("rate") if isinstance(d["attrs"].get("rate"), int) else 0
        out.append(f'    {{ {pid}, "{d["name"]}", {"true" if dr == "c2s" else "false"}, {rate} }},')
    out += ["};", "", "// 가변 길이 필드의 최대 길이. 서버는 패킷을 처리하기 전에 이 값으로 검사한다.", "namespace MaxLen", "{"]
    for pid, d, dr in rows:
        for f in d["fields"]:
            if isinstance(f["attrs"].get("max_len"), int):
                out.append(f"    inline constexpr uint32_t {d['name']}_{f['name']} = {f['attrs']['max_len']};")
    out += ["} // namespace MaxLen", "", "constexpr const FPacketInfo* Find(uint16_t Id)", "{",
            "    for (const FPacketInfo& Info : Packets)", "    {", "        if (Info.Id == Id) { return &Info; }",
            "    }", "    return nullptr;", "}", "} // namespace PacketMeta", ""]
    return "\n".join(out)


def to_markdown(report, max_rows=200):
    s = report["summary"]
    lines = ["# 프로토콜 검사 보고서", "",
             f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 스키마 파일 {s['files']}개, 타입 {s['types']}개, 패킷 {s['packets']}개 "
             f"(클라이언트→서버 {s['c2s']}, 서버→클라이언트 {s['s2c']})",
             f"- error {s['error']} / warning {s['warning']} / info {s['info']}",
             "", "| 심각도 | 규칙 | 위치 | 내용 |", "|---|---|---|---|"]
    for f in report["findings"][:max_rows]:
        where = f"`{f['file']}:{f['line']}`" if f["file"] else "-"
        lines.append(f"| {f['severity']} | {f['rule']} | {where} | {f['message']} |")
    if len(report["findings"]) > max_rows:
        lines += ["", f"나머지 {len(report['findings']) - max_rows}건은 report.json 참조."]
    return "\n".join(lines) + "\n"


def read_schemas(root):
    files = {}
    for dirpath, _, filenames in os.walk(root):
        for fn in filenames:
            if fn.endswith(".fbs"):
                path = os.path.join(dirpath, fn)
                with open(path, encoding="utf-8-sig", errors="replace") as f:
                    files[os.path.relpath(path, root).replace(os.sep, "/")] = f.read()
    return files


def _write(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("schema_dir")
    ap.add_argument("--config")
    ap.add_argument("--lock", help="protocol.lock.json 경로")
    ap.add_argument("--update-lock", action="store_true", help="검사를 통과하면 lock을 현재 스키마로 갱신")
    ap.add_argument("--emit-header", help="패킷 ID와 제한값을 담은 C++ 헤더를 생성")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.schema_dir):
        print(f"스키마 폴더 없음: {a.schema_dir}", file=sys.stderr)
        return 2
    files = read_schemas(a.schema_dir)
    if not files:
        print(f".fbs 파일이 없음: {a.schema_dir}", file=sys.stderr)
        return 2
    config = None
    if a.config:
        with open(a.config, encoding="utf-8") as f:
            config = json.load(f)
    lock = None
    if a.lock and os.path.isfile(a.lock):
        with open(a.lock, encoding="utf-8") as f:
            lock = json.load(f)

    creating = a.update_lock and lock is None
    report, schema, pk = check(files, config, lock, lock_given=bool(a.lock) and not creating)
    passed = report["summary"]["passed"]
    if a.out:
        _write(a.out, json.dumps(report, ensure_ascii=False, indent=2))
    if a.md:
        _write(a.md, to_markdown(report))
    if a.update_lock:
        if not a.lock:
            print("--update-lock에는 --lock 경로가 필요함", file=sys.stderr)
            return 2
        if passed:
            _write(a.lock, json.dumps(make_lock(schema, pk, lock), ensure_ascii=False, indent=2) + "\n")
        else:
            print("error가 있어 lock을 갱신하지 않음", file=sys.stderr)
    if a.emit_header and passed:
        _write(a.emit_header, emit_header(pk))
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
