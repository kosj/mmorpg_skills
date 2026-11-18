"""에셋 사실 정보(facts)를 규격(spec)과 비교해 위반 목록을 만든다.

Unreal에 의존하지 않는 순수 Python이라 에디터 밖(CI, 테스트)에서도 실행된다.

    python validate.py facts.json asset-spec.json --out report.json --md report.md

error가 하나라도 있으면 종료 코드 1을 반환한다.
"""
import argparse
import json
import re
import sys
from collections import Counter

DEFAULT_SEVERITY = {
    "NAME001": "error", "NAME002": "error",
    "TEX001": "error", "TEX002": "error", "TEX003": "warning", "TEX004": "warning",
    "SM001": "error", "SM002": "warning", "SM003": "error", "SM004": "warning",
    "GEN001": "info",
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _starts_with_any(path, prefixes):
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in prefixes or [])


def is_excluded(path, spec):
    return _starts_with_any(path, spec.get("exclude"))


def _is_pow2(n):
    return isinstance(n, int) and n > 0 and (n & (n - 1)) == 0


def _max_size_for(path, tex_spec):
    """가장 긴 path_prefix가 일치하는 override를 쓴다."""
    best_len, best = -1, tex_spec.get("max_size")
    for o in tex_spec.get("max_size_overrides", []):
        p = o["path_prefix"]
        if _starts_with_any(path, [p]) and len(p) > best_len:
            best_len, best = len(p), o["max_size"]
    return best


def _suffix_rule(name, tex_spec):
    """가장 긴 접미사가 일치하는 규칙을 쓴다."""
    rules = tex_spec.get("suffix_rules", {})
    for suffix in sorted(rules, key=len, reverse=True):
        if name.endswith(suffix):
            return suffix, rules[suffix]
    return None, None


class _Collector:
    def __init__(self, spec):
        self.severity = dict(DEFAULT_SEVERITY)
        self.severity.update(spec.get("severity", {}))
        self.findings = []

    def add(self, rule, fact, message):
        self.findings.append({
            "rule": rule,
            "severity": self.severity.get(rule, "warning"),
            "path": fact.get("path", ""),
            "class": fact.get("class", ""),
            "message": message,
        })

    def missing(self, fact, field, skipped_rule):
        self.add("GEN001", fact, f"'{field}' 정보를 수집하지 못해 {skipped_rule} 검사를 건너뜀")


def _check_naming(fact, spec, out):
    naming = spec.get("naming", {})
    name, cls = fact.get("name", ""), fact.get("class", "")
    prefix = naming.get("prefix", {}).get(cls)
    if prefix and not name.startswith(prefix):
        out.add("NAME001", fact, f"{cls}의 이름은 '{prefix}'로 시작해야 함: {name}")
    pattern = naming.get("allowed_pattern")
    if pattern and not re.match(pattern, name):
        out.add("NAME002", fact, f"이름에 허용되지 않는 문자가 있음: {name}")


def _check_texture(fact, spec, out):
    t = spec.get("texture")
    if not t:
        return
    path, name = fact["path"], fact.get("name", "")
    w, h = fact.get("width"), fact.get("height")
    if w is None or h is None:
        out.missing(fact, "width/height", "TEX001, TEX002")
    else:
        if t.get("power_of_two") and not _starts_with_any(path, t.get("power_of_two_exempt_prefixes")):
            if not (_is_pow2(w) and _is_pow2(h)):
                out.add("TEX001", fact, f"크기가 2의 거듭제곱이 아님: {w}x{h}")
        limit = _max_size_for(path, t)
        if limit and max(w, h) > limit:
            out.add("TEX002", fact, f"크기 {w}x{h}가 최대 {limit}을 넘음")

    suffix, rule = _suffix_rule(name, t)
    if not rule:
        return
    if "srgb" in rule:
        if fact.get("srgb") is None:
            out.missing(fact, "srgb", "TEX003")
        elif fact["srgb"] != rule["srgb"]:
            want = "켜짐" if rule["srgb"] else "꺼짐"
            out.add("TEX003", fact, f"접미사 '{suffix}' 텍스처는 sRGB가 {want}이어야 함")
    if "compression" in rule:
        if fact.get("compression") is None:
            out.missing(fact, "compression", "TEX004")
        elif fact["compression"] != rule["compression"]:
            out.add("TEX004", fact,
                    f"접미사 '{suffix}' 텍스처의 압축은 {rule['compression']}이어야 함 (현재 {fact['compression']})")


def _check_static_mesh(fact, spec, out):
    s = spec.get("static_mesh")
    if not s:
        return
    path = fact["path"]
    nanite, tris, lods = fact.get("nanite"), fact.get("tris_lod0"), fact.get("lods")

    if nanite is None:
        out.missing(fact, "nanite", "SM001, SM002")
    elif tris is None:
        out.missing(fact, "tris_lod0", "SM001, SM002")
    else:
        budget = s.get("max_tris_nanite") if nanite else s.get("max_tris_lod0_non_nanite")
        if budget and tris > budget:
            kind = "Nanite" if nanite else "비 Nanite"
            out.add("SM002", fact, f"LOD0 삼각형 {tris:,}개가 {kind} 예산 {budget:,}개를 넘음")
        min_lods = s.get("min_lods_non_nanite")
        if not nanite and min_lods and tris >= s.get("lod_exempt_below_tris", 0):
            if lods is None:
                out.missing(fact, "lods", "SM001")
            elif lods < min_lods:
                out.add("SM001", fact, f"Nanite가 꺼진 메시의 LOD가 {lods}개 (최소 {min_lods}개)")

    if s.get("require_collision") and not _starts_with_any(path, s.get("collision_exempt_prefixes")):
        c = fact.get("simple_collision_count")
        if c is None:
            out.missing(fact, "simple_collision_count", "SM003")
        elif c == 0:
            out.add("SM003", fact, "단순 콜리전이 없음")

    max_slots = s.get("max_material_slots")
    if max_slots:
        slots = fact.get("material_slots")
        if slots is None:
            out.missing(fact, "material_slots", "SM004")
        elif slots > max_slots:
            out.add("SM004", fact, f"머티리얼 슬롯 {slots}개 (최대 {max_slots}개)")


def validate(facts, spec):
    """위반 목록을 severity, 규칙, 경로 순으로 정렬해 반환한다."""
    out = _Collector(spec)
    for fact in facts:
        if is_excluded(fact.get("path", ""), spec):
            continue
        _check_naming(fact, spec, out)
        if fact.get("class") == "Texture2D":
            _check_texture(fact, spec, out)
        elif fact.get("class") == "StaticMesh":
            _check_static_mesh(fact, spec, out)
    out.findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["rule"], f["path"]))
    return out.findings


def summarize(facts, findings, spec):
    checked = sum(1 for f in facts if not is_excluded(f.get("path", ""), spec))
    by_sev = Counter(f["severity"] for f in findings)
    return {
        "checked": checked,
        "error": by_sev.get("error", 0),
        "warning": by_sev.get("warning", 0),
        "info": by_sev.get("info", 0),
        "by_rule": dict(sorted(Counter(f["rule"] for f in findings).items())),
        "passed": by_sev.get("error", 0) == 0,
    }


def to_markdown(summary, findings, max_rows=200):
    lines = [
        "# 에셋 규격 검사 보고서", "",
        f"- 결과: {'통과' if summary['passed'] else '실패'}",
        f"- 검사한 에셋: {summary['checked']}개",
        f"- error {summary['error']} / warning {summary['warning']} / info {summary['info']}",
        "", "## 규칙별 개수", "", "| 규칙 | 개수 |", "|---|---|",
    ]
    lines += [f"| {r} | {n} |" for r, n in summary["by_rule"].items()] or ["| 없음 | 0 |"]
    lines += ["", "## 위반 목록", "", "| 심각도 | 규칙 | 에셋 | 내용 |", "|---|---|---|---|"]
    for f in findings[:max_rows]:
        lines.append(f"| {f['severity']} | {f['rule']} | `{f['path']}` | {f['message']} |")
    if len(findings) > max_rows:
        lines += ["", f"나머지 {len(findings) - max_rows}건은 report.json 참조."]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("facts")
    ap.add_argument("spec")
    ap.add_argument("--out", help="report.json 경로")
    ap.add_argument("--md", help="report.md 경로")
    a = ap.parse_args(argv)
    with open(a.facts, encoding="utf-8") as f:
        facts = json.load(f)
    with open(a.spec, encoding="utf-8") as f:
        spec = json.load(f)
    findings = validate(facts, spec)
    summary = summarize(facts, findings, spec)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump({"summary": summary, "findings": findings}, f, ensure_ascii=False, indent=2)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(to_markdown(summary, findings))
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
