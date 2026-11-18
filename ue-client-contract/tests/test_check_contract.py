"""check_contract.py 단위 테스트: python -m unittest discover -s tests"""
import copy
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_contract as cc  # noqa: E402

EXAMPLE_DIR = os.path.join(ROOT, "references", "example")
BASE = cc.load_dir(EXAMPLE_DIR)


def data():
    return copy.deepcopy(BASE)


def item(d, kind, id_):
    return next(x for x in d[kind] if x["id"] == id_)


def rules(d):
    return sorted(f["rule"] for f in cc.check(d)["findings"])


class Example(unittest.TestCase):
    def test_example_is_clean(self):
        r = cc.check(data())
        self.assertEqual(r["findings"], [])
        self.assertEqual(r["matrix"]["mounts"]["M_Pegasus"], {"modes": ["ground", "fly"], "riders": ["C_Human"]})
        self.assertEqual(r["matrix"]["weather_blocks"]["storm"], ["fly", "glide"])


class References(unittest.TestCase):
    def test_duplicate_id(self):
        d = data()
        d["parts"].append(dict(item(d, "parts", "P_Robe_Full"), _file="dlc.json"))
        self.assertEqual(rules(d), ["LINK000"])

    def test_unknown_references(self):
        d = data()
        item(d, "parts", "P_Robe_Full")["slot"] = "Torso"
        item(d, "mounts", "M_Horse")["anim_set"] = "AS_Pony"
        item(d, "weather", "rain")["vfx"] = ["FX_Drizzle"]
        self.assertEqual(rules(d), ["LINK001", "LINK001", "LINK001"])

    def test_missing_socket(self):
        d = data()
        item(d, "skeletons", "SK_Quadruped")["sockets"].remove("wing_tip_l")
        self.assertEqual(rules(d), ["LINK002"])            # 날개 이펙트를 쓰는 페가수스만
        d = data()
        item(d, "skeletons", "SK_Quadruped")["sockets"].remove("stirrup_l")
        self.assertEqual(rules(d), ["LINK002", "LINK002"])  # 스켈레톤을 공유하는 탈것 모두
        d = data()
        item(d, "parts", "P_Sword_Frost")["vfx"][0]["socket"] = "pommel"
        self.assertEqual(rules(d), ["LINK002"])

    def test_part_vfx_may_use_socket_the_part_provides(self):
        self.assertNotIn("LINK002", rules(data()))  # cloak_tip, blade_tip


class Animation(unittest.TestCase):
    def test_mode_needs_states(self):
        d = data()
        item(d, "anim_sets", "AS_Quadruped")["states"].remove("fly_land")
        f = cc.check(d)["findings"]
        self.assertEqual([x["rule"] for x in f], ["LINK003"])
        self.assertIn("fly_land", f[0]["message"])

    def test_rider_needs_states_for_each_mount_mode(self):
        d = data()
        item(d, "anim_sets", "AS_Human_Ride_Quadruped")["states"].remove("ride_fly")
        f = cc.check(d)["findings"]
        self.assertEqual([x["rule"] for x in f], ["LINK003"])
        self.assertIn("ride_fly", f[0]["message"])

    def test_skeleton_mismatch(self):
        d = data()
        item(d, "mounts", "M_Horse")["anim_set"] = "AS_Human"
        self.assertEqual(rules(d), ["LINK004"])

    def test_mount_without_compatible_rider(self):
        d = data()
        item(d, "anim_sets", "AS_Human_Ride_Quadruped")["skeleton"] = "SK_Quadruped"
        self.assertEqual(rules(d), ["LINK005", "LINK005"])


class Movement(unittest.TestCase):
    def test_mode_without_way_back(self):
        d = data()
        item(d, "movement_modes", "fly")["transitions"] = []
        r = rules(d)
        self.assertIn("LINK006", r)   # 페가수스가 비행에서 내려올 수 없다
        self.assertIn("LINK010", r)   # 폭풍이 비행을 막는데 내려올 전환이 없다

    def test_unreachable_mode(self):
        d = data()
        item(d, "movement_modes", "ground")["transitions"] = ["swim", "glide"]
        f = [x for x in cc.check(d)["findings"] if x["rule"] == "LINK006"]
        self.assertEqual([x["id"] for x in f], ["M_Pegasus"])

    def test_same_family_mount_gets_flight_without_new_animation(self):
        # 네발 계열은 스켈레톤과 세트를 공유하므로, 말에 비행을 추가해도 새 애니메이션이 필요 없다
        d = data()
        item(d, "mounts", "M_Horse")["modes"].append("fly")
        self.assertEqual(rules(d), [])

    def test_new_movement_mode_reports_everything_missing(self):
        # 확장 시나리오: 급강하 모드를 추가하면 무엇이 더 필요한지 알려 준다
        d = data()
        d["movement_modes"].append({"id": "dive", "foot_ik": False, "airborne": True, "transitions": ["fly"],
                                    "required_states": ["dive_start", "dive_loop"], "rider_states": ["ride_dive"]})
        item(d, "movement_modes", "fly")["transitions"].append("dive")
        item(d, "mounts", "M_Pegasus")["modes"].append("dive")
        f = cc.check(d)["findings"]
        self.assertEqual(sorted(x["rule"] for x in f), ["LINK003", "LINK003"])
        text = " ".join(x["message"] for x in f)
        self.assertIn("dive_start", text)
        self.assertIn("ride_dive", text)

    def test_foot_ik_rules(self):
        d = data()
        item(d, "movement_modes", "fly")["foot_ik"] = True
        self.assertEqual(rules(d), ["LINK007"])
        d = data()
        item(d, "ik_profiles", "IK_Quadruped")["foot_placement"] = False
        self.assertEqual(rules(d), ["LINK007", "LINK007"])


class VfxWeatherBiome(unittest.TestCase):
    def test_vfx_budget_and_attachment(self):
        d = data()
        item(d, "vfx", "FX_Wing_Trail")["cost"] = 6       # 날개 2개 = 12 > 10
        self.assertEqual(rules(d), ["LINK008"])
        d = data()
        item(d, "vfx", "FX_Hoof_Dust")["pooled"] = False
        self.assertEqual(rules(d), ["LINK008"])   # 같은 이펙트를 두 소켓에 써도 지적은 한 번
        d = data()
        item(d, "parts", "P_Cloak_Flame")["vfx"][0]["effect"] = "FX_Rain"   # 월드 이펙트를 소켓에
        self.assertIn("LINK008", rules(d))

    def test_mount_vfx_budget_is_per_mode(self):
        d = data()
        d["budgets"]["vfx_cost_per_mount"] = 5
        f = [x for x in cc.check(d)["findings"] if x["rule"] == "LINK008"]
        self.assertEqual(len(f), 1)
        self.assertIn("fly", f[0]["message"])   # 지상 모드에는 날개 이펙트가 없다

    def test_weather_param_set_must_match(self):
        d = data()
        del item(d, "weather", "snow")["params"]["wetness"]
        self.assertEqual(rules(d), ["LINK009"])

    def test_weather_graph(self):
        d = data()
        item(d, "weather", "snow")["transitions"] = []
        self.assertEqual(rules(d), ["LINK009"])

    def test_biome_budgets(self):
        d = data()
        item(d, "biomes", "B_Forest")["layers"][1]["density_per_100m2"] = 500
        self.assertEqual(rules(d), ["LINK011"])
        d = data()
        item(d, "biomes", "B_Forest")["layers"][1]["nanite"] = False
        self.assertEqual(rules(d), ["LINK011"])
        d = data()
        item(d, "biomes", "B_Snowfield")["weathers"].append("blizzard")
        self.assertEqual(rules(d), ["LINK001"])


class Cli(unittest.TestCase):
    def test_split_files_and_matrix(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "contract")
            shutil.copytree(EXAMPLE_DIR, src)
            # 콘텐츠 팩: 새 탈것을 별도 파일로 추가한다
            pack = {"mounts": [{"id": "M_Warhorse", "skeleton": "SK_Quadruped", "anim_set": "AS_Quadruped",
                                "modes": ["ground"], "default_mode": "ground",
                                "seats": [{"socket": "saddle", "rider_anim_set": "AS_Human_Ride_Quadruped"}]}]}
            with open(os.path.join(src, "pack_warhorse.json"), "w", encoding="utf-8") as f:
                json.dump(pack, f)
            matrix = os.path.join(d, "out", "matrix.md")
            self.assertEqual(cc.main([src, "--matrix", matrix, "--md", os.path.join(d, "out", "r.md")]), 0)
            with open(matrix, encoding="utf-8") as f:
                text = f.read()
            self.assertIn("| M_Warhorse | ground | C_Human |", text)
            self.assertIn("| storm | fly, glide | M_Pegasus |", text)
            with open(os.path.join(src, "broken.json"), "w") as f:
                f.write("{")
            self.assertEqual(cc.main([src]), 2)
        self.assertEqual(cc.main(["/nonexistent-dir"]), 2)


if __name__ == "__main__":
    unittest.main()
