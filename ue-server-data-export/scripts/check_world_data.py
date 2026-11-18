"""자체 서버에 넘길 월드 데이터 묶음을 만들고 검사한다. Unreal 없이 실행되는 순수 Python.

    python check_world_data.py build <내보내기 폴더> --map Field_01 [--client-versions map_versions.json]
    python check_world_data.py check <내보내기 폴더> [--client-versions map_versions.json]
                                     [--monsters-csv monsters.csv] [--config world-data-config.json]

build: 폴더의 파일을 해시해 manifest.json을 만든다. map_version은 파일 내용에서 계산한다.
check: 묶음이 온전한지, 클라이언트가 가진 맵 버전과 같은지, 스폰과 볼륨이 말이 되는지 본다.
종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter

DEFAULT_CONFIG = {
    "required_kinds": ["nav_geometry", "spawns", "volumes"],
    "kind_by_name": {"nav.obj": "nav_geometry", "spawns.json": "spawns", "volumes.json": "volumes",
                     "bounds.json": "bounds", "collision.obj": "collision"},
    "spawn_types": ["monster", "npc", "player_start", "gather"],
    "volume_types": ["no_fly", "safe_zone", "no_spawn", "trigger", "water"],
    "no_spawn_applies_to": ["monster", "gather"],
    "min_world_extent": 1000,
    "severity": {"WORLD001": "error", "WORLD002": "error", "WORLD003": "error", "WORLD004": "error",
                 "WORLD005": "error", "WORLD006": "error", "WORLD007": "error", "WORLD008": "error",
                 "WORLD009": "warning"},
}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}
MANIFEST = "manifest.json"


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _cfg(config):
    cfg = dict(DEFAULT_CONFIG)
    cfg.update(config or {})
    cfg["severity"] = dict(DEFAULT_CONFIG["severity"], **(config or {}).get("severity", {}))
    return cfg


def read_obj(path):
    """OBJ의 정점 수, 면 수, 정점 범위, 잘못된 면 인덱스 수를 돌려준다."""
    verts, faces, bad = 0, 0, 0
    lo, hi = [float("inf")] * 3, [float("-inf")] * 3
    face_idx = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            p = line.split()
            if not p:
                continue
            if p[0] == "v" and len(p) >= 4:
                try:
                    xyz = [float(p[1]), float(p[2]), float(p[3])]
                except ValueError:
                    continue
                verts += 1
                lo = [min(a, b) for a, b in zip(lo, xyz)]
                hi = [max(a, b) for a, b in zip(hi, xyz)]
            elif p[0] == "f":
                faces += 1
                for tok in p[1:]:
                    try:
                        face_idx.append(int(tok.split("/")[0]))
                    except ValueError:
                        bad += 1
    bad += sum(1 for i in face_idx if i == 0 or abs(i) > verts)
    return {"verts": verts, "faces": faces, "min": lo, "max": hi, "bad_indices": bad}


def build(folder, map_name, config=None):
    """폴더의 파일로 manifest를 만든다. map_version은 파일 이름과 내용 해시에서 계산하므로 재현된다."""
    cfg = _cfg(config)
    files = []
    for name in sorted(os.listdir(folder)):
        path = os.path.join(folder, name)
        if name == MANIFEST or not os.path.isfile(path):
            continue
        files.append({"name": name, "kind": cfg["kind_by_name"].get(name, "other"),
                      "sha256": sha256_of(path), "size": os.path.getsize(path)})
    version = hashlib.sha256("".join(f["name"] + f["sha256"] for f in files).encode()).hexdigest()[:16]
    manifest = {"format": 1, "map": map_name, "map_version": version, "unit": "cm", "files": files}
    bounds_path = os.path.join(folder, "bounds.json")
    if os.path.isfile(bounds_path):
        manifest["bounds"] = _load_json(bounds_path)
    with open(os.path.join(folder, MANIFEST), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    return manifest


def _inside(p, lo, hi):
    return all(a <= v <= b for v, a, b in zip(p, lo, hi))


def _vec3(v):
    return isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v)


def check(folder, config=None, client_versions=None, monster_ids=None):
    cfg = _cfg(config)
    findings = []

    def add(rule, where, message):
        findings.append({"rule": rule, "severity": cfg["severity"][rule], "where": where, "message": message})

    def done(manifest=None):
        findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"], f["where"]))
        by_sev = Counter(f["severity"] for f in findings)
        summary = {"passed": by_sev.get("error", 0) == 0, "map": (manifest or {}).get("map"),
                   "map_version": (manifest or {}).get("map_version"),
                   "error": by_sev.get("error", 0), "warning": by_sev.get("warning", 0),
                   "by_rule": dict(sorted(Counter(f["rule"] for f in findings).items()))}
        return {"summary": summary, "findings": findings}

    mpath = os.path.join(folder, MANIFEST)
    try:
        manifest = _load_json(mpath)
        assert manifest.get("format") == 1 and isinstance(manifest.get("files"), list) and manifest.get("map")
    except (OSError, ValueError, AssertionError, AttributeError):
        add("WORLD001", MANIFEST, "manifest.json이 없거나 읽을 수 없음. build를 먼저 실행")
        return done()

    by_kind = {}
    for f in manifest["files"]:
        path = os.path.join(folder, f["name"])
        if not os.path.isfile(path):
            add("WORLD002", f["name"], "manifest에 있는 파일이 없음")
            continue
        if os.path.getsize(path) != f.get("size") or sha256_of(path) != f.get("sha256"):
            add("WORLD002", f["name"], "파일 내용이 manifest와 다름. 내보낸 뒤 고쳤거나 build를 다시 하지 않았음")
        by_kind.setdefault(f.get("kind"), path)
    for kind in cfg["required_kinds"]:
        if kind not in by_kind:
            add("WORLD003", MANIFEST, f"필수 데이터 '{kind}'이(가) 묶음에 없음")

    if client_versions is not None:
        cv = client_versions.get(manifest["map"])
        if cv is None:
            add("WORLD004", manifest["map"], "클라이언트 버전 정보에 이 맵이 없음")
        elif cv != manifest.get("map_version"):
            add("WORLD004", manifest["map"], f"서버 데이터 버전 {manifest.get('map_version')}과(와) 클라이언트가 가진 "
                                             f"버전 {cv}이(가) 다름. 맵을 고친 뒤 내보내기를 다시 하지 않았음")

    bounds = manifest.get("bounds") or {}
    lo, hi = bounds.get("min"), bounds.get("max")
    has_bounds = _vec3(lo) and _vec3(hi)
    if has_bounds and max(b - a for a, b in zip(lo, hi)) < cfg["min_world_extent"]:
        add("WORLD008", "bounds.json", f"월드 범위가 {cfg['min_world_extent']}보다 작음. 단위가 cm가 아닐 수 있음")

    # 볼륨
    volumes, no_spawn = [], []
    if "volumes" in by_kind:
        try:
            volumes = _load_json(by_kind["volumes"]).get("volumes", [])
        except (ValueError, AttributeError):
            add("WORLD007", "volumes.json", "JSON을 읽을 수 없음")
    seen = set()
    for v in volumes:
        vid = str(v.get("id"))
        if vid in seen:
            add("WORLD007", vid, "볼륨 id 중복")
        seen.add(vid)
        if v.get("type") not in cfg["volume_types"]:
            add("WORLD007", vid, f"알 수 없는 볼륨 종류 '{v.get('type')}'")
        if not (_vec3(v.get("min")) and _vec3(v.get("max"))):
            add("WORLD007", vid, "min/max가 숫자 3개가 아님")
            continue
        if any(a > b for a, b in zip(v["min"], v["max"])):
            add("WORLD007", vid, "min이 max보다 큼")
            continue
        if has_bounds and not (_inside(v["min"], lo, hi) or _inside(v["max"], lo, hi)):
            add("WORLD007", vid, "볼륨이 월드 범위 밖에 있음")
        if v.get("type") == "no_spawn":
            no_spawn.append(v)

    # 스폰
    spawns = []
    if "spawns" in by_kind:
        try:
            spawns = _load_json(by_kind["spawns"]).get("spawns", [])
        except (ValueError, AttributeError):
            add("WORLD005", "spawns.json", "JSON을 읽을 수 없음")
    seen = set()
    for s in spawns:
        sid = str(s.get("id"))
        if sid in seen:
            add("WORLD005", sid, "스폰 id 중복")
        seen.add(sid)
        if s.get("type") not in cfg["spawn_types"]:
            add("WORLD005", sid, f"알 수 없는 스폰 종류 '{s.get('type')}'")
        if isinstance(s.get("count", 1), bool) or not isinstance(s.get("count", 1), int) or s.get("count", 1) < 1:
            add("WORLD005", sid, "count가 1 이상의 정수가 아님")
        if not _vec3(s.get("pos")):
            add("WORLD005", sid, "pos가 숫자 3개가 아님")
            continue
        if has_bounds and not _inside(s["pos"], lo, hi):
            add("WORLD005", sid, "스폰 위치가 월드 범위 밖에 있음")
        for v in no_spawn:
            # 스폰 금지 볼륨은 몬스터와 채집물에만 적용한다. 플레이어 시작점과 NPC는 마을 안에 있다
            if s.get("type") in cfg["no_spawn_applies_to"] and _inside(s["pos"], v["min"], v["max"]):
                add("WORLD005", sid, f"스폰 금지 볼륨 {v.get('id')} 안에 있음")
        if monster_ids is not None and s.get("type") == "monster" and str(s.get("ref_id")) not in monster_ids:
            add("WORLD006", sid, f"몬스터 {s.get('ref_id')}이(가) 기획 데이터에 없음")
    if "spawns" in by_kind and not any(s.get("type") == "player_start" for s in spawns):
        add("WORLD009", "spawns.json", "player_start 스폰이 없음")

    # 내비 지오메트리
    if "nav_geometry" in by_kind:
        obj = read_obj(by_kind["nav_geometry"])
        name = os.path.basename(by_kind["nav_geometry"])
        if obj["verts"] == 0 or obj["faces"] == 0:
            add("WORLD008", name, "정점이나 면이 없음. 내비메시가 빌드되지 않은 상태로 내보냈을 수 있음")
        else:
            if obj["bad_indices"]:
                add("WORLD008", name, f"잘못된 면 인덱스 {obj['bad_indices']}개")
            if max(b - a for a, b in zip(obj["min"], obj["max"])) < cfg["min_world_extent"]:
                add("WORLD008", name, f"지오메트리 크기가 {cfg['min_world_extent']}보다 작음. 단위가 cm가 아닐 수 있음")
    return done(manifest)


def to_markdown(report):
    s = report["summary"]
    lines = ["# 서버용 월드 데이터 검사 보고서", "", f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 맵: {s['map']} (버전 {s['map_version']})", f"- error {s['error']} / warning {s['warning']}", "",
             "| 심각도 | 규칙 | 위치 | 내용 |", "|---|---|---|---|"]
    lines += [f"| {f['severity']} | {f['rule']} | {f['where']} | {f['message']} |" for f in report["findings"]]
    return "\n".join(lines) + "\n"


def read_ids(csv_path, column):
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        return {(row.get(column) or "").strip() for row in csv.DictReader(f)} - {""}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("folder")
    b.add_argument("--map", required=True)
    b.add_argument("--client-versions", help="클라이언트에 넣을 map_versions.json. 이 맵의 버전을 갱신한다")
    b.add_argument("--config")
    c = sub.add_parser("check")
    c.add_argument("folder")
    c.add_argument("--client-versions")
    c.add_argument("--monsters-csv")
    c.add_argument("--id-column", default="id")
    c.add_argument("--config")
    c.add_argument("--out")
    c.add_argument("--md")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.folder):
        print(f"폴더 없음: {a.folder}", file=sys.stderr)
        return 2
    try:
        config = _load_json(a.config) if a.config else None
        if a.cmd == "build":
            manifest = build(a.folder, a.map, config)
            if a.client_versions:
                versions = _load_json(a.client_versions) if os.path.isfile(a.client_versions) else {}
                versions[a.map] = manifest["map_version"]
                with open(a.client_versions, "w", encoding="utf-8") as f:
                    json.dump(versions, f, ensure_ascii=False, indent=2, sort_keys=True)
            print(json.dumps({"map": a.map, "map_version": manifest["map_version"], "files": len(manifest["files"])},
                             ensure_ascii=False))
            return 0
        client = _load_json(a.client_versions) if a.client_versions else None
        monsters = read_ids(a.monsters_csv, a.id_column) if a.monsters_csv else None
    except (OSError, ValueError) as e:
        print(f"입력을 읽지 못함: {e}", file=sys.stderr)
        return 2
    report = check(a.folder, config, client, monsters)
    for target, text in ((a.out, json.dumps(report, ensure_ascii=False, indent=2)), (a.md, to_markdown(report))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
