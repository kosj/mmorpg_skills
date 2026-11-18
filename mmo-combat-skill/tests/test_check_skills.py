"""check_skills.py 단위 테스트: python -m unittest discover -s tests"""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_skills as cs  # noqa: E402

EXAMPLE = os.path.join(ROOT, "references", "example", "skills.csv")
BASE = cs.read_csv(EXAMPLE)


def rows(**changes):
    """changes: {스킬 id: {열: 값}}. 예시 데이터를 복사해 일부만 바꾼다."""
    out = []
    for line, row in BASE:
        row = dict(row)
        row.update(changes.get("s" + row["id"], {}))
        out.append((line, row))
    return out


SIM_RULES = {"SKILL009", "SKILL010", "SKILL011"}


def rules(r, config=None):
    """형식/규칙 지적만 본다. 시뮬레이션에서 나오는 지적은 Simulation 테스트에서 따로 본다."""
    return sorted(f["rule"] for f in cs.check(r, config)["findings"] if f["rule"] not in SIM_RULES)


class Example(unittest.TestCase):
    def test_example_is_clean_and_balanced(self):
        rep = cs.check(rows())
        self.assertEqual(rep["findings"], [])
        dps = rep["summary"]["dps"]
        self.assertEqual(set(dps), {"warrior", "mage", "ranger"})
        self.assertLess(max(dps.values()) / min(dps.values()), 1.15)


class Format(unittest.TestCase):
    def test_bad_number_missing_and_duplicate(self):
        r = rows(s1001={"coefficient": "abc"}, s1002={"name": ""}, s1003={"id": "1004"})
        self.assertEqual(rules(r), ["SKILL001"] * 3)

    def test_unknown_enums(self):
        r = rows(s1001={"target_type": "foe"}, s2001={"cost_type": "rage"}, s3001={"usable_modes": "ground|space"})
        self.assertEqual(rules(r), ["SKILL002"] * 3)
        self.assertIn("SKILL002", rules(rows(), {"classes": ["warrior", "mage"]}))   # ranger가 목록에 없음


class Rules(unittest.TestCase):
    def test_range(self):
        r = rows(s1005={"range_cm": "500"}, s2001={"range_cm": "0"}, s3002={"range_cm": "9000"})
        self.assertEqual(rules(r), ["SKILL003"] * 3)

    def test_infinite_rate_skill_is_error(self):
        f = cs.check(rows(s1001={"gcd": "false"}))["findings"]
        self.assertEqual([x["rule"] for x in f if x["severity"] == "error"], ["SKILL004"])
        self.assertIn("무한", f[0]["message"])

    def test_dot_timing(self):
        self.assertEqual(rules(rows(s1003={"dot_tick_ms": "0"})), ["SKILL004"])
        self.assertEqual(rules(rows(s1005={"cooldown_ms": "-1"})), ["SKILL004", "SKILL005"])

    def test_not_multiple_of_server_tick_is_warning(self):
        rep = cs.check(rows(s2001={"cast_time_ms": "1550"}))
        self.assertEqual([f["rule"] for f in rep["findings"]], ["SKILL005"])
        self.assertTrue(rep["summary"]["passed"])

    def test_cost(self):
        r = rows(s1002={"cost": "-10"}, s1001={"cost": "5"}, s2003={"cost": "5000"})
        self.assertEqual(rules(r), ["SKILL006"] * 3)

    def test_aoe_needs_radius_and_target_cap(self):
        r = rows(s1004={"aoe_radius_cm": "0"}, s2003={"max_targets": "0"})
        self.assertEqual(rules(r), ["SKILL007"] * 2)


class Simulation(unittest.TestCase):
    def test_damage_formula_by_hand(self):
        s = {"base_damage": 10.0, "coefficient": 2.0, "hits": 2, "dot_tick_ms": 3000, "dot_duration_ms": 12000,
             "dot_coefficient": 0.5}
        # (10 + 2.0*100) * 2 + 4틱 * 0.5 * 100 = 420 + 200
        self.assertEqual(cs.damage(s, 100), 620.0)

    def test_single_filler_dps_by_hand(self):
        # 전역 쿨다운 1초마다 공격력 100 * 계수 1.0 → DPS 100
        r = [(2, dict(BASE[0][1]))]
        self.assertEqual(cs.check(r)["summary"]["dps"], {"warrior": 100.0})

    def test_typo_in_coefficient_is_flagged(self):
        rep = cs.check(rows(s3002={"coefficient": "36"}))     # 3.6을 36으로 잘못 입력
        found = {f["rule"] for f in rep["findings"]}
        self.assertIn("SKILL010", found)   # 스킬 이상치
        self.assertIn("SKILL009", found)   # 직업 DPS 편차

    def test_dominated_skill_is_reported(self):
        # 시전 2초에 계수 1.2: 시전 없는 기본 공격(1초에 1.0)보다 항상 불리하다
        rep = cs.check(rows(s3002={"coefficient": "1.2"}))
        self.assertEqual([(f["rule"], f["id"]) for f in rep["findings"] if f["rule"] == "SKILL011"], [("SKILL011", "3002")])

    def test_resource_limits_dps(self):
        rich = cs.check(rows())["summary"]["dps"]["mage"]
        poor = cs.check(rows(), {"reference": {"resource_regen_per_sec": 0, "resource_pool": 300}})["summary"]["dps"]["mage"]
        self.assertLess(poor, rich * 0.3)

    def test_simulation_is_deterministic(self):
        self.assertEqual(cs.check(rows())["simulation"], cs.check(rows())["simulation"])


class Cli(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "o", "r.md")
            self.assertEqual(cs.main([EXAMPLE, "--md", md]), 0)
            with open(md, encoding="utf-8") as f:
                self.assertIn("warrior", f.read())
            bad = os.path.join(d, "bad.csv")
            with open(bad, "w") as f:
                f.write("id,name\n1,x\n")
            self.assertEqual(cs.main([bad]), 2)
        self.assertEqual(cs.main(["/nonexistent.csv"]), 2)


if __name__ == "__main__":
    unittest.main()
