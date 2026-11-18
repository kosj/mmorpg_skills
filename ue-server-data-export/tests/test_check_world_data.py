"""check_world_data.py 단위 테스트: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_world_data as wd  # noqa: E402

NAV = "v 0 0 0\nv 50000 0 0\nv 0 50000 100\nv 50000 50000 100\nf 1 2 3\nf 2/1/1 4/2/1 3/3/1\n"
SPAWNS = {"spawns": [
    {"id": "start", "type": "player_start", "pos": [1000, 1000, 50], "count": 1},
    {"id": "slimes", "type": "monster", "ref_id": 1, "pos": [20000, 20000, 60], "count": 3, "radius": 300},
]}
VOLUMES = {"volumes": [
    {"id": "town_safe", "type": "safe_zone", "min": [0, 0, -100], "max": [5000, 5000, 3000]},
    {"id": "town_no_spawn", "type": "no_spawn", "min": [0, 0, -100], "max": [5000, 5000, 3000]},
    {"id": "castle_no_fly", "type": "no_fly", "min": [30000, 30000, 0], "max": [40000, 40000, 20000]},
]}
BOUNDS = {"min": [0, 0, -500], "max": [50000, 50000, 20000]}


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = os.path.join(self.tmp.name, "export")
        os.makedirs(self.dir)
        self.write("nav.obj", NAV)
        self.write("spawns.json", SPAWNS)
        self.write("volumes.json", VOLUMES)
        self.write("bounds.json", BOUNDS)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, content):
        with open(os.path.join(self.dir, name), "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))

    def build(self):
        return wd.build(self.dir, "Field_01")

    def rules(self, **kw):
        return sorted(f["rule"] for f in wd.check(self.dir, **kw)["findings"])


class Package(Base):
    def test_good_package(self):
        m = self.build()
        self.assertEqual(self.rules(), [])
        self.assertEqual({f["kind"] for f in m["files"]}, {"nav_geometry", "spawns", "volumes", "bounds"})

    def test_version_is_reproducible_and_content_based(self):
        v1 = self.build()["map_version"]
        self.assertEqual(self.build()["map_version"], v1)
        self.write("nav.obj", NAV + "v 1 1 1\n")
        self.assertNotEqual(self.build()["map_version"], v1)

    def test_no_manifest(self):
        self.assertEqual(self.rules(), ["WORLD001"])

    def test_edited_after_build(self):
        self.build()
        self.write("spawns.json", {"spawns": SPAWNS["spawns"][:1]})
        self.assertEqual(self.rules(), ["WORLD002"])

    def test_missing_file_and_kind(self):
        self.build()
        os.remove(os.path.join(self.dir, "nav.obj"))
        self.assertEqual(self.rules(), ["WORLD002", "WORLD003"])

    def test_client_version(self):
        m = self.build()
        self.assertEqual(self.rules(client_versions={"Field_01": m["map_version"]}), [])
        self.assertEqual(self.rules(client_versions={"Field_01": "old"}), ["WORLD004"])
        self.assertEqual(self.rules(client_versions={}), ["WORLD004"])


class Content(Base):
    def test_spawn_problems(self):
        bad = {"spawns": SPAWNS["spawns"] + [
            {"id": "slimes", "type": "monster", "ref_id": 1, "pos": [100, 100, 0]},          # 중복 + 스폰 금지 안
            {"id": "far", "type": "monster", "ref_id": 1, "pos": [999999, 0, 0]},            # 범위 밖
            {"id": "odd", "type": "boss", "pos": [20000, 20000, 0], "count": 0},             # 종류, count
            {"id": "nopos", "type": "npc"},
        ]}
        self.write("spawns.json", bad)
        self.build()
        self.assertEqual(self.rules(), ["WORLD005"] * 6)

    def test_spawn_must_reference_known_monster(self):
        self.build()
        self.assertEqual(self.rules(monster_ids={"1", "2"}), [])
        self.assertEqual(self.rules(monster_ids={"2"}), ["WORLD006"])

    def test_volume_problems(self):
        self.write("volumes.json", {"volumes": [
            {"id": "a", "type": "lava", "min": [0, 0, 0], "max": [10, 10, 10]},
            {"id": "b", "type": "no_fly", "min": [10, 0, 0], "max": [0, 10, 10]},
            {"id": "c", "type": "no_fly", "min": [900000, 0, 0], "max": [900010, 10, 10]},
            {"id": "c", "type": "no_fly", "min": [0, 0, 0]},
        ]})
        self.build()
        self.assertEqual(self.rules(), ["WORLD007"] * 5)

    def test_no_player_start_is_warning(self):
        self.write("spawns.json", {"spawns": SPAWNS["spawns"][1:]})
        self.build()
        r = wd.check(self.dir)
        self.assertEqual([f["rule"] for f in r["findings"]], ["WORLD009"])
        self.assertTrue(r["summary"]["passed"])

    def test_nav_geometry_sanity(self):
        self.write("nav.obj", "# empty\n")
        self.build()
        self.assertEqual(self.rules(), ["WORLD008"])
        self.write("nav.obj", "v 0 0 0\nv 50000 0 0\nv 0 50000 0\nf 1 2 9\n")
        self.build()
        self.assertEqual(self.rules(), ["WORLD008"])
        self.write("nav.obj", "v 0 0 0\nv 500 0 0\nv 0 500 0\nf 1 2 3\n")   # 미터 단위로 보이는 크기
        self.build()
        self.assertEqual(self.rules(), ["WORLD008"])


class Cli(Base):
    def test_build_then_check(self):
        versions = os.path.join(self.tmp.name, "client", "map_versions.json")
        os.makedirs(os.path.dirname(versions))
        monsters = os.path.join(self.tmp.name, "monsters.csv")
        with open(monsters, "w", encoding="utf-8") as f:
            f.write("id,name\n1,Slime\n")
        self.assertEqual(wd.main(["build", self.dir, "--map", "Field_01", "--client-versions", versions]), 0)
        md = os.path.join(self.tmp.name, "out", "r.md")
        args = ["check", self.dir, "--client-versions", versions, "--monsters-csv", monsters, "--md", md]
        self.assertEqual(wd.main(args), 0)
        # 맵을 고치고 서버 데이터만 다시 만들면 클라이언트 버전과 어긋난다
        self.write("nav.obj", NAV + "v 2 2 2\n")
        wd.build(self.dir, "Field_01")
        self.assertEqual(wd.main(args), 1)
        with open(md, encoding="utf-8") as f:
            self.assertIn("WORLD004", f.read())
        self.assertEqual(wd.main(["check", "/nonexistent-dir"]), 2)


if __name__ == "__main__":
    unittest.main()
