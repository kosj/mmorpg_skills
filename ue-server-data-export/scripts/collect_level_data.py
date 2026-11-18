"""Unreal 에디터 안에서 실행: 현재 레벨의 스폰 지점, 볼륨, 월드 범위를 JSON으로 내보낸다.

액터 태그 규칙 (액터의 Tags에 적는다):
    ServerSpawn:<종류>:<ref_id>:<count>:<radius>     예) ServerSpawn:monster:101:3:300
    ServerVolume:<종류>                              예) ServerVolume:no_fly

볼륨은 액터 경계를 축에 정렬된 상자(min, max)로 내보낸다. 회전된 볼륨은 그만큼 크게 잡힌다.
내비 지오메트리(nav.obj)는 이 스크립트가 만들지 않는다. references/world-data-guide.md 참조.

에디터에서 실행해 검증하지 않은 코드다. 조회에 실패한 액터는 건너뛰고 skipped에 이름을 남긴다.
"""
import json
import os

import unreal

SPAWN_TAG, VOLUME_TAG = "ServerSpawn:", "ServerVolume:"


def _vec(v):
    return [round(float(v.x), 1), round(float(v.y), 1), round(float(v.z), 1)]


def collect():
    sub = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    spawns, volumes, skipped = [], [], []
    lo, hi = [float("inf")] * 3, [float("-inf")] * 3
    for actor in sub.get_all_level_actors():
        try:
            name = actor.get_name()
            tags = [str(t) for t in actor.tags]
            origin, extent = actor.get_actor_bounds(False)
            o, e = _vec(origin), _vec(extent)
            if any(e):
                lo = [min(a, c - d) for a, c, d in zip(lo, o, e)]
                hi = [max(a, c + d) for a, c, d in zip(hi, o, e)]
            for tag in tags:
                if tag.startswith(SPAWN_TAG):
                    parts = tag[len(SPAWN_TAG):].split(":")
                    spawns.append({
                        "id": name, "type": parts[0],
                        "ref_id": int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None,
                        "count": int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1,
                        "radius": float(parts[3]) if len(parts) > 3 else 0.0,
                        "pos": _vec(actor.get_actor_location()),
                    })
                elif tag.startswith(VOLUME_TAG):
                    volumes.append({"id": name, "type": tag[len(VOLUME_TAG):],
                                    "min": [round(c - d, 1) for c, d in zip(o, e)],
                                    "max": [round(c + d, 1) for c, d in zip(o, e)]})
        except Exception as ex:  # 엔진 버전에 따라 API가 다를 수 있다
            skipped.append("{}: {}".format(getattr(actor, "get_name", lambda: "?")(), ex))
    bounds = {"min": lo, "max": hi} if lo[0] != float("inf") else {}
    return spawns, volumes, bounds, skipped


def main(out_dir=None):
    out_dir = out_dir or os.path.join(unreal.Paths.project_saved_dir(), "ServerWorldData")
    os.makedirs(out_dir, exist_ok=True)
    spawns, volumes, bounds, skipped = collect()
    for name, doc in (("spawns.json", {"spawns": sorted(spawns, key=lambda s: s["id"])}),
                      ("volumes.json", {"volumes": sorted(volumes, key=lambda v: v["id"])}),
                      ("bounds.json", bounds)):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=2, sort_keys=True)
    summary = {"out_dir": out_dir, "spawns": len(spawns), "volumes": len(volumes), "skipped": skipped[:20]}
    unreal.log("[ServerWorldData] " + json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    main()
