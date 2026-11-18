"""check_economy.py 단위 테스트: python -m unittest discover -s tests"""
import copy
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_economy as ce  # noqa: E402

EXAMPLE = os.path.join(ROOT, "references", "example")
BASE = ce.read_tables(EXAMPLE, ce._cfg(None))


def tables():
    return copy.deepcopy(BASE)


def row(t, name, id_col, id_):
    return next(r for _, r in t[name] if r[id_col] == str(id_))


def rules(t, config=None):
    return sorted(f["rule"] for f in ce.analyze(t, config)["findings"])


def table(name, header, *rows_):
    return [(i, dict(zip(header, map(str, r)))) for i, r in enumerate(rows_, start=2)]


class Model(unittest.TestCase):
    def test_single_monster_by_hand(self):
        # 체력 100, 플레이어 DPS 10, 처치 사이 4초 → 14초에 한 마리 → 시간당 3600/14 마리
        t = {"monsters": table("m", ["id", "level", "hp", "exp_reward", "gold_min", "gold_max", "drop_group"],
                               [1, 1, 100, 7, 2, 4, 10]),
             "drops": table("d", ["group_id", "item_id", "prob", "min_count", "max_count"], [10, 5, 0.5, 1, 3]),
             "items": table("i", ["id", "grade", "level_req", "price_buy", "price_sell"], [5, "common", 1, 0, 4]),
             "levels": table("l", ["level", "exp_required"], [1, 0], [2, 1800])}
        c = ce.analyze(t)["curve"][0]
        kills = 3600 / 14
        self.assertEqual(c["exp_per_hour"], round(7 * kills))            # 1800
        self.assertEqual(c["gold_per_hour"], round((3 + 0.5 * 2 * 4) * kills))   # 골드 3 + 드롭 기대값 4
        self.assertEqual(c["hours"], 1.0)

    def test_example_is_clean(self):
        rep = ce.analyze(tables())
        self.assertEqual(rep["findings"], [])
        hours = [c["hours"] for c in rep["curve"]]
        self.assertEqual(hours, sorted(hours))          # 레벨이 오를수록 오래 걸린다
        self.assertEqual(rep["summary"]["levels"], 10)

    def test_deterministic(self):
        self.assertEqual(ce.analyze(tables()), ce.analyze(tables()))


class Findings(unittest.TestCase):
    def test_gold_farm_spot(self):
        t = tables()
        row(t, "monsters", "id", 105)["gold_max"] = "400"
        f = ce.analyze(t)["findings"]
        self.assertEqual({x["rule"] for x in f}, {"ECON002"})
        self.assertEqual({x["where"] for x in f}, {"몬스터 105"})   # 여러 레벨에서 걸려도 한 번만 보고

    def test_exp_exploit(self):
        t = tables()
        row(t, "monsters", "id", 105)["exp_reward"] = "500"
        r = rules(t)
        self.assertIn("ECON003", r)
        self.assertIn("ECON005", r)      # 그 구간의 레벨업 시간이 급감한다

    def test_level_gap_without_monsters(self):
        t = tables()
        t["monsters"] = [(i, r) for i, r in t["monsters"] if int(r["level"]) not in (5, 6, 7, 8)]
        rep = ce.analyze(t)
        gaps = [f["where"] for f in rep["findings"] if f["rule"] == "ECON004"]
        self.assertEqual(gaps, ["레벨 7"])     # 5~8이 비면 레벨 7만 사냥감이 없다 (범위 5~8)
        self.assertFalse(rep["summary"]["passed"])

    def test_leveling_wall(self):
        t = tables()
        base = int(row(t, "levels", "level", 7)["exp_required"])
        for lv in (7, 8, 9, 10, 11):
            r = row(t, "levels", "level", lv)
            r["exp_required"] = str(int(r["exp_required"]) + 60000) if lv > 6 and int(r["exp_required"]) >= base else r["exp_required"]
        f = [x for x in ce.analyze(t)["findings"] if x["rule"] == "ECON005"]
        self.assertEqual([x["where"] for x in f][:1], ["레벨 6"])

    def test_item_price_out_of_band(self):
        t = tables()
        row(t, "items", "id", 2006)["price_buy"] = "9000000"
        row(t, "items", "id", 2010)["price_buy"] = "10"
        f = [x for x in ce.analyze(t)["findings"] if x["rule"] == "ECON006"]
        self.assertEqual(sorted(x["where"] for x in f), ["아이템 2006", "아이템 2010"])

    def test_bad_number_is_excluded_and_reported(self):
        t = tables()
        row(t, "monsters", "id", 203)["hp"] = "abc"
        self.assertIn("ECON001", rules(t))

    def test_faster_player_levels_faster(self):
        slow = ce.analyze(tables())["summary"]["hours_to_max"]
        fast = ce.analyze(tables(), {"player": {"base_dps": 20.0}})["summary"]["hours_to_max"]
        self.assertLess(fast, slow)


class Cli(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "o", "r.md")
            self.assertEqual(ce.main([EXAMPLE, "--md", md]), 0)
            with open(md, encoding="utf-8") as f:
                self.assertIn("레벨별 곡선", f.read())
            broken = os.path.join(d, "data")
            shutil.copytree(EXAMPLE, broken)
            os.remove(os.path.join(broken, "levels.csv"))
            self.assertEqual(ce.main([broken]), 2)
        self.assertEqual(ce.main(["/nonexistent-dir"]), 2)


if __name__ == "__main__":
    unittest.main()
