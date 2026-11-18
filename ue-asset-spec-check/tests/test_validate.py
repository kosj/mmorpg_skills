"""validate.py 단위 테스트. 에디터 없이 실행: python -m unittest discover -s tests"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import validate  # noqa: E402

with open(os.path.join(ROOT, "references", "asset-spec.json"), encoding="utf-8") as f:
    SPEC = json.load(f)


def tex(path, w=1024, h=1024, srgb=True, comp="TC_DEFAULT"):
    return {"path": path, "name": path.rsplit("/", 1)[-1], "class": "Texture2D",
            "width": w, "height": h, "srgb": srgb, "compression": comp}


def mesh(path, lods=3, tris=5000, nanite=False, col=1, slots=1):
    return {"path": path, "name": path.rsplit("/", 1)[-1], "class": "StaticMesh", "lods": lods,
            "tris_lod0": tris, "nanite": nanite, "simple_collision_count": col, "material_slots": slots}


def rules(facts):
    return sorted(f["rule"] for f in validate.validate(facts, SPEC))


class Naming(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(rules([mesh("/Game/Env/SM_Rock")]), [])

    def test_missing_prefix(self):
        self.assertEqual(rules([mesh("/Game/Env/Rock")]), ["NAME001"])

    def test_bad_chars(self):
        self.assertEqual(rules([mesh("/Game/Env/SM_바위")]), ["NAME002"])

    def test_unknown_class_has_no_prefix_rule(self):
        self.assertEqual(rules([{"path": "/Game/X/Foo", "name": "Foo", "class": "SomeNewClass"}]), [])

    def test_excluded_path_skipped(self):
        self.assertEqual(rules([mesh("/Game/Developers/kim/Rock")]), [])

    def test_exclude_is_not_plain_string_prefix(self):
        self.assertEqual(rules([mesh("/Game/DevelopersX/Rock")]), ["NAME001"])


class Texture(unittest.TestCase):
    def test_ok(self):
        self.assertEqual(rules([tex("/Game/Env/T_Rock_D")]), [])

    def test_non_pow2(self):
        self.assertEqual(rules([tex("/Game/Env/T_Rock_D", w=1000)]), ["TEX001"])

    def test_pow2_exempt_in_ui(self):
        self.assertEqual(rules([tex("/Game/UI/T_Icon", w=300, h=200)]), [])

    def test_too_big(self):
        self.assertEqual(rules([tex("/Game/Env/T_Rock_D", w=8192, h=8192)]), ["TEX002"])

    def test_override_raises_limit(self):
        self.assertEqual(rules([tex("/Game/Characters/Hero/T_Face_D", w=8192, h=8192)]), [])

    def test_override_lowers_limit(self):
        self.assertEqual(rules([tex("/Game/UI/T_Bg", w=4096, h=4096)]), ["TEX002"])

    def test_normal_map_settings(self):
        self.assertEqual(rules([tex("/Game/Env/T_Rock_N", srgb=True, comp="TC_DEFAULT")]), ["TEX003", "TEX004"])
        self.assertEqual(rules([tex("/Game/Env/T_Rock_N", srgb=False, comp="TC_NORMALMAP")]), [])

    def test_longest_suffix_wins(self):
        # _ORM은 _M보다 먼저 일치해야 한다 (둘 다 TC_MASKS라 설정으로 구분)
        suffix, _ = validate._suffix_rule("T_Rock_ORM", SPEC["texture"])
        self.assertEqual(suffix, "_ORM")

    def test_missing_fact_is_info_not_violation(self):
        t = tex("/Game/Env/T_Rock_D")
        t["width"] = None
        found = validate.validate([t], SPEC)
        self.assertEqual([f["rule"] for f in found], ["GEN001"])
        self.assertEqual(found[0]["severity"], "info")


class StaticMesh(unittest.TestCase):
    def test_too_few_lods(self):
        self.assertEqual(rules([mesh("/Game/Env/SM_Rock", lods=1)]), ["SM001"])

    def test_small_mesh_lod_exempt(self):
        self.assertEqual(rules([mesh("/Game/Env/SM_Pebble", lods=1, tris=200)]), [])

    def test_nanite_skips_lod_rule(self):
        self.assertEqual(rules([mesh("/Game/Env/SM_Cliff", lods=1, tris=2000000, nanite=True)]), [])

    def test_tri_budget(self):
        self.assertEqual(rules([mesh("/Game/Env/SM_Rock", tris=150000)]), ["SM002"])
        self.assertEqual(rules([mesh("/Game/Env/SM_Cliff", tris=6000000, nanite=True)]), ["SM002"])

    def test_collision(self):
        self.assertEqual(rules([mesh("/Game/Env/SM_Rock", col=0)]), ["SM003"])
        self.assertEqual(rules([mesh("/Game/Environment/Foliage/SM_Grass", col=0)]), [])

    def test_material_slots(self):
        self.assertEqual(rules([mesh("/Game/Env/SM_Rock", slots=6)]), ["SM004"])


class Report(unittest.TestCase):
    def test_summary_and_sorting(self):
        facts = [mesh("/Game/Env/Rock", slots=6), tex("/Game/Env/T_Rock_D")]
        found = validate.validate(facts, SPEC)
        self.assertEqual([f["severity"] for f in found], ["error", "warning"])
        s = validate.summarize(facts, found, SPEC)
        self.assertEqual((s["checked"], s["error"], s["warning"], s["passed"]), (2, 1, 1, False))
        self.assertIn("NAME001", validate.to_markdown(s, found))

    def test_severity_override(self):
        spec = json.loads(json.dumps(SPEC))
        spec["severity"]["NAME001"] = "warning"
        found = validate.validate([mesh("/Game/Env/Rock")], spec)
        self.assertEqual(found[0]["severity"], "warning")


if __name__ == "__main__":
    unittest.main()
