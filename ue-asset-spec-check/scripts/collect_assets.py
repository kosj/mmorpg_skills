"""Unreal 에디터 안에서 에셋의 사실 정보만 수집한다. 판정은 validate.py가 한다.

엔진 버전에 따라 Python API 이름이 다를 수 있어 모든 조회를 _try로 감싼다.
조회에 실패한 값은 None으로 남고, validate.py가 GEN001(검사 불가)로 보고한다.
"""
import unreal

# 세부 정보가 필요해 에셋을 로드해야 하는 클래스. 나머지는 이름과 클래스만 본다.
_LOADED_CLASSES = {"StaticMesh", "Texture2D"}


def _try(fn):
    try:
        return fn()
    except Exception:
        return None


def _class_name(asset_data):
    name = _try(lambda: str(asset_data.asset_class_path.asset_name))
    return name or _try(lambda: str(asset_data.asset_class)) or ""


def _enum_name(value):
    if value is None:
        return None
    return getattr(value, "name", None) or str(value).split(".")[-1]


def _texture_facts(tex):
    return {
        "width": _try(lambda: int(tex.blueprint_get_size_x())),
        "height": _try(lambda: int(tex.blueprint_get_size_y())),
        "srgb": _try(lambda: bool(tex.get_editor_property("srgb"))),
        "compression": _enum_name(_try(lambda: tex.get_editor_property("compression_settings"))),
    }


def _static_mesh_facts(mesh):
    sub = _try(lambda: unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem))
    return {
        "lods": _try(lambda: int(mesh.get_num_lods())),
        "tris_lod0": _try(lambda: int(mesh.get_num_triangles(0))),
        "nanite": _try(lambda: bool(mesh.get_editor_property("nanite_settings").enabled)),
        "simple_collision_count": _try(lambda: int(sub.get_simple_collision_count(mesh))),
        "material_slots": _try(lambda: len(mesh.get_editor_property("static_materials"))),
    }


def _excluded(path, excludes):
    return any(path == p or path.startswith(p.rstrip("/") + "/") for p in excludes or [])


def collect(roots, excludes=None, limit=None):
    """roots 아래 에셋의 사실 정보 리스트를 반환한다.

    limit: 수집할 최대 에셋 수. 큰 폴더를 시험 삼아 돌릴 때 쓴다.
    """
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    facts, seen = [], set()
    for root in roots:
        for ad in registry.get_assets_by_path(root, recursive=True) or []:
            path = str(ad.package_name)
            if path in seen or _excluded(path, excludes):
                continue
            seen.add(path)
            cls = _class_name(ad)
            fact = {"path": path, "name": str(ad.asset_name), "class": cls}
            if cls in _LOADED_CLASSES:
                asset = _try(ad.get_asset)
                if asset is not None:
                    fact.update(_texture_facts(asset) if cls == "Texture2D" else _static_mesh_facts(asset))
            facts.append(fact)
            if limit and len(facts) >= limit:
                return facts
    return facts
