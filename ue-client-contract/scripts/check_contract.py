"""클라이언트 콘텐츠 연결 규약을 검사한다. Unreal 없이 실행되는 순수 Python.

파츠, 탈것, 이동 모드, 애니메이션 세트, IK, VFX, 날씨, 바이옴이 서로를 올바르게 참조하는지 본다.
폴더 안의 모든 .json을 합쳐서 읽으므로, 콘텐츠 팩마다 파일을 따로 추가하면 된다.

    python check_contract.py <규약 폴더> --md report.md --matrix matrix.md

종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import json
import os
import sys
from collections import Counter, defaultdict

KINDS = ["skeletons", "slots", "parts", "anim_sets", "movement_modes", "characters", "mounts",
         "vfx", "ik_profiles", "weather", "biomes"]
SEVERITY = {"LINK000": "error", "LINK001": "error", "LINK002": "error", "LINK003": "error",
            "LINK004": "error", "LINK005": "warning", "LINK006": "error", "LINK007": "warning",
            "LINK008": "warning", "LINK009": "error", "LINK010": "error", "LINK011": "warning"}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def load_dir(folder):
    """폴더의 모든 .json을 종류별로 합친다. 항목마다 출처 파일을 _file에 남긴다."""
    data = {k: [] for k in KINDS}
    data["budgets"] = {}
    for dirpath, _, filenames in os.walk(folder):
        for fn in sorted(filenames):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding="utf-8-sig") as f:
                doc = json.load(f)
            rel = os.path.relpath(path, folder).replace(os.sep, "/")
            for k in KINDS:
                for item in doc.get(k, []):
                    data[k].append(dict(item, _file=rel))
            data["budgets"].update(doc.get("budgets", {}))
    return data


def _reach(start, edges, allowed):
    seen, stack = set(), [start]
    while stack:
        n = stack.pop()
        if n in seen or n not in allowed:
            continue
        seen.add(n)
        stack.extend(edges.get(n, []))
    return seen


def check(data):
    findings = []
    sev = dict(SEVERITY)
    sev.update(data.get("severity", {}))

    def add(rule, item, message):
        findings.append({"rule": rule, "severity": sev[rule], "file": (item or {}).get("_file", ""),
                         "id": (item or {}).get("id", ""), "message": message})

    idx = {}
    for k in KINDS:
        idx[k] = {}
        for item in data.get(k, []):
            if item.get("id") in idx[k]:
                add("LINK000", item, f"{k}에 id '{item.get('id')}'가 중복됨 "
                                     f"({idx[k][item['id']].get('_file', '')}에도 있음)")
            else:
                idx[k][item.get("id")] = item

    def ref(kind, value, owner, what):
        """참조가 있으면 대상을, 없으면 LINK001을 남기고 None을 돌려준다."""
        if value is None:
            return None
        target = idx[kind].get(value)
        if target is None:
            add("LINK001", owner, f"{what} '{value}'이(가) {kind}에 없음")
        return target

    def sockets_of(skeleton):
        return set(skeleton.get("sockets", [])) if skeleton else set()

    def need_socket(skeleton, socket, owner, what):
        if skeleton and socket not in sockets_of(skeleton):
            add("LINK002", owner, f"{what}: 소켓 '{socket}'이(가) 스켈레톤 {skeleton['id']}에 없음")

    budgets = data.get("budgets", {})
    modes = idx["movement_modes"]
    edges = {m["id"]: list(m.get("transitions", [])) for m in modes.values()}

    # 스켈레톤과 IK
    for sk in idx["skeletons"].values():
        prof = ref("ik_profiles", sk.get("ik_profile"), sk, "ik_profile")
        if prof and prof.get("skeleton") != sk["id"]:
            add("LINK004", sk, f"ik_profile {prof['id']}의 스켈레톤이 {prof.get('skeleton')}임")
    for prof in idx["ik_profiles"].values():
        ref("skeletons", prof.get("skeleton"), prof, "skeleton")
    for m in modes.values():
        for t in m.get("transitions", []):
            ref("movement_modes", t, m, "transitions")
        if m.get("airborne") and m.get("foot_ik"):
            add("LINK007", m, "공중 모드인데 foot_ik가 켜져 있음. 발이 허공의 바닥을 찾는다")

    # VFX 묶음 검사
    def check_vfx(owner, entries, skeleton, extra_sockets, budget_key, label):
        cost = 0
        for e in entries or []:
            fx = ref("vfx", e.get("effect"), owner, f"{label} vfx")
            if not fx:
                continue
            cost += fx.get("cost", 0)
            if e.get("socket"):
                if skeleton and e["socket"] not in sockets_of(skeleton) | set(extra_sockets):
                    add("LINK002", owner, f"{label} vfx {fx['id']}: 소켓 '{e['socket']}'이(가) 없음")
                if fx.get("attach") == "world":
                    add("LINK008", owner, f"{label} vfx {fx['id']}: 월드 고정 이펙트를 소켓에 붙임")
                if not fx.get("pooled"):
                    add("LINK008", owner, f"{label} vfx {fx['id']}: 부착 이펙트인데 풀링이 꺼져 있음")
        limit = budgets.get(budget_key)
        if limit is not None and cost > limit:
            add("LINK008", owner, f"{label}의 VFX 비용 {cost}이(가) 예산 {limit}을 넘음")

    # 파츠
    for p in idx["parts"].values():
        ref("slots", p.get("slot"), p, "slot")
        for s in p.get("covers", []):
            ref("slots", s, p, "covers")
        sk = ref("skeletons", p.get("skeleton"), p, "skeleton")
        for s in p.get("requires_sockets", []):
            need_socket(sk, s, p, "requires_sockets")
        check_vfx(p, p.get("vfx"), sk, p.get("provides_sockets", []), "vfx_cost_per_part", "파츠")

    # 이동 모드를 가진 주체(캐릭터, 탈것) 공통 검사
    def check_mover(owner, label):
        sk = ref("skeletons", owner.get("skeleton"), owner, "skeleton")
        aset = ref("anim_sets", owner.get("anim_set"), owner, "anim_set")
        if aset and sk and aset.get("skeleton") != sk["id"]:
            add("LINK004", owner, f"anim_set {aset['id']}의 스켈레톤이 {aset.get('skeleton')}임 ({label}는 {sk['id']})")
        own_modes = [m for m in owner.get("modes", []) if ref("movement_modes", m, owner, "modes")]
        prof = idx["ik_profiles"].get(sk.get("ik_profile")) if sk else None
        for mid in own_modes:
            m = modes[mid]
            if aset:
                missing = [s for s in m.get("required_states", []) if s not in aset.get("states", [])]
                if missing:
                    add("LINK003", owner, f"모드 {mid}에 필요한 상태가 anim_set {aset['id']}에 없음: {', '.join(missing)}")
            if m.get("foot_ik") and not (prof and prof.get("foot_placement")):
                add("LINK007", owner, f"모드 {mid}는 foot_ik를 쓰는데 스켈레톤에 발 배치 IK 프로필이 없음")
        default = owner.get("default_mode")
        if default not in own_modes:
            add("LINK006", owner, f"default_mode '{default}'이(가) modes에 없음")
        else:
            allowed = set(own_modes)
            forward = _reach(default, edges, allowed)
            for mid in own_modes:
                if mid not in forward:
                    add("LINK006", owner, f"모드 {mid}에 들어갈 전환 경로가 없음 (기본 모드 {default}에서 출발)")
                elif default not in _reach(mid, edges, allowed):
                    add("LINK006", owner, f"모드 {mid}에서 기본 모드 {default}(으)로 돌아올 전환 경로가 없음")
        return sk, own_modes

    char_skeletons = {}
    for c in idx["characters"].values():
        sk, _ = check_mover(c, "캐릭터")
        if sk:
            char_skeletons.setdefault(sk["id"], []).append(c["id"])

    riders = defaultdict(list)
    for mt in idx["mounts"].values():
        sk, own_modes = check_mover(mt, "탈것")
        for s in mt.get("rider_hidden_slots", []):
            ref("slots", s, mt, "rider_hidden_slots")
        for i, seat in enumerate(mt.get("seats", [])):
            need_socket(sk, seat.get("socket"), mt, f"좌석 {i}")
            for s in seat.get("rider_ik_sockets", []):
                need_socket(sk, s, mt, f"좌석 {i} rider_ik_sockets")
            rset = ref("anim_sets", seat.get("rider_anim_set"), mt, f"좌석 {i} rider_anim_set")
            if not rset:
                continue
            for mid in own_modes:
                missing = [s for s in modes[mid].get("rider_states", []) if s not in rset.get("states", [])]
                if missing:
                    add("LINK003", mt, f"좌석 {i}: 모드 {mid}에 필요한 탑승자 상태가 {rset['id']}에 없음: {', '.join(missing)}")
            for cid in char_skeletons.get(rset.get("skeleton"), []):
                if cid not in riders[mt["id"]]:
                    riders[mt["id"]].append(cid)
        if not mt.get("seats"):
            add("LINK005", mt, "좌석이 없음")
        elif not riders[mt["id"]]:
            add("LINK005", mt, "탈 수 있는 캐릭터가 없음. 좌석의 rider_anim_set 스켈레톤과 맞는 캐릭터가 없다")
        # 참조와 소켓은 전체 목록으로 한 번 보고, 예산은 모드별로 본다 (모드가 없는 이펙트는 항상 켜짐)
        check_vfx(mt, mt.get("vfx"), sk, [], None, "탈것")
        for e in mt.get("vfx", []):
            if e.get("mode"):
                ref("movement_modes", e["mode"], mt, "vfx mode")
        limit = budgets.get("vfx_cost_per_mount")
        if limit is not None:
            for mid in own_modes:
                cost = sum(idx["vfx"][e["effect"]].get("cost", 0) for e in mt.get("vfx", [])
                           if e.get("effect") in idx["vfx"] and e.get("mode") in (None, mid))
                if cost > limit:
                    add("LINK008", mt, f"모드 {mid}에서 탈것의 VFX 비용 {cost}이(가) 예산 {limit}을 넘음")

    # 날씨
    weathers = list(idx["weather"].values())
    all_params = set().union(*[set(w.get("params", {})) for w in weathers]) if weathers else set()
    w_edges = {w["id"]: list(w.get("transitions", [])) for w in weathers}
    for w in weathers:
        for t in w.get("transitions", []):
            ref("weather", t, w, "transitions")
        for fx in w.get("vfx", []):
            ref("vfx", fx, w, "vfx")
        missing = sorted(all_params - set(w.get("params", {})))
        if missing:
            add("LINK009", w, f"다른 날씨에 있는 파라미터가 빠짐: {', '.join(missing)}. 전환할 때 값이 튄다")
        blocked = {m for m in w.get("blocked_modes", []) if ref("movement_modes", m, w, "blocked_modes")}
        for owner in list(idx["characters"].values()) + list(idx["mounts"].values()):
            own = set(owner.get("modes", [])) & set(modes)
            for mid in sorted(own & blocked):
                if not any(t in own and t not in blocked for t in edges.get(mid, [])):
                    add("LINK010", owner, f"날씨 {w['id']}가 모드 {mid}를 막는데, {mid}에서 막히지 않은 모드로 가는 전환이 없음")
    if weathers:
        first, ids = weathers[0]["id"], set(idx["weather"])
        forward = _reach(first, w_edges, ids)
        for w in weathers:
            if w["id"] not in forward or first not in _reach(w["id"], w_edges, ids):
                add("LINK009", w, f"날씨 전환 그래프에서 {first}와(과) 서로 오갈 수 없음")

    # 바이옴
    for b in idx["biomes"].values():
        for wid in b.get("weathers", []):
            ref("weather", wid, b, "weathers")
        total = sum(layer.get("density_per_100m2", 0) for layer in b.get("layers", []))
        limit = budgets.get("biome_density_per_100m2")
        if limit is not None and total > limit:
            add("LINK011", b, f"배치 밀도 합 {total}/100m²이 예산 {limit}을 넘음")
        for layer in b.get("layers", []):
            hi = budgets.get("non_nanite_density_per_100m2")
            if hi is not None and not layer.get("nanite") and layer.get("density_per_100m2", 0) > hi:
                add("LINK011", b, f"레이어 {layer.get('asset')}: Nanite가 아닌데 밀도 {layer['density_per_100m2']}/100m²이 {hi}를 넘음")

    # 같은 지적이 두 번 들어간 경우 제거
    uniq, seen = [], set()
    for f in findings:
        key = (f["rule"], f["file"], f["id"], f["message"])
        if key not in seen:
            seen.add(key)
            uniq.append(f)
    uniq.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["file"], str(f["id"]), f["rule"]))
    by_sev = Counter(f["severity"] for f in uniq)
    summary = {"passed": by_sev.get("error", 0) == 0,
               "counts": {k: len(idx[k]) for k in KINDS if idx[k]},
               "error": by_sev.get("error", 0), "warning": by_sev.get("warning", 0),
               "by_rule": dict(sorted(Counter(f["rule"] for f in uniq).items()))}
    matrix = {
        "mounts": {mid: {"modes": [m for m in mt.get("modes", []) if m in modes], "riders": riders.get(mid, [])}
                   for mid, mt in idx["mounts"].items()},
        "weather_blocks": {w["id"]: sorted(set(w.get("blocked_modes", [])) & set(modes)) for w in weathers},
    }
    return {"summary": summary, "findings": uniq, "matrix": matrix}


def to_markdown(report, max_rows=200):
    s = report["summary"]
    counts = ", ".join(f"{k} {n}" for k, n in s["counts"].items())
    lines = ["# 클라이언트 연결 규약 검사 보고서", "", f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 항목: {counts}", f"- error {s['error']} / warning {s['warning']}", "",
             "| 심각도 | 규칙 | 항목 | 내용 |", "|---|---|---|---|"]
    for f in report["findings"][:max_rows]:
        lines.append(f"| {f['severity']} | {f['rule']} | `{f['file']}` {f['id']} | {f['message']} |")
    return "\n".join(lines) + "\n"


def matrix_markdown(report):
    m = report["matrix"]
    lines = ["# 연결 표", "", "## 탈것", "", "| 탈것 | 이동 모드 | 탈 수 있는 캐릭터 |", "|---|---|---|"]
    for mid, v in sorted(m["mounts"].items()):
        lines.append(f"| {mid} | {', '.join(v['modes']) or '-'} | {', '.join(v['riders']) or '없음'} |")
    lines += ["", "## 날씨가 막는 이동 모드", "", "| 날씨 | 막는 모드 | 영향받는 탈것 |", "|---|---|---|"]
    for wid, blocked in sorted(m["weather_blocks"].items()):
        hit = sorted(mid for mid, v in m["mounts"].items() if set(v["modes"]) & set(blocked))
        lines.append(f"| {wid} | {', '.join(blocked) or '-'} | {', '.join(hit) or '-'} |")
    return "\n".join(lines) + "\n"


def _write(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("contract_dir")
    ap.add_argument("--out")
    ap.add_argument("--md")
    ap.add_argument("--matrix", help="탈것/날씨 연결 표를 마크다운으로 저장")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.contract_dir):
        print(f"규약 폴더 없음: {a.contract_dir}", file=sys.stderr)
        return 2
    try:
        data = load_dir(a.contract_dir)
    except json.JSONDecodeError as e:
        print(f"JSON을 읽지 못함: {e}", file=sys.stderr)
        return 2
    report = check(data)
    if a.out:
        _write(a.out, json.dumps(report, ensure_ascii=False, indent=2))
    if a.md:
        _write(a.md, to_markdown(report))
    if a.matrix:
        _write(a.matrix, matrix_markdown(report))
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
