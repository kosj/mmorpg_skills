"""capacity_calc.py 단위 테스트: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import capacity_calc as cc  # noqa: E402

SCENARIO_PATH = os.path.join(ROOT, "references", "scenario.json")


def scenario(**over):
    with open(SCENARIO_PATH, encoding="utf-8") as f:
        sc = json.load(f)
    for k, v in over.items():
        if isinstance(v, dict):
            sc[k].update(v)
        else:
            sc[k] = v
    return sc


class Capacity(unittest.TestCase):
    def test_bandwidth_formula_by_hand(self):
        r = scenario()["rates"]
        # 20명*10Hz*40B + 30마리*5Hz*24B + 30Hz*28B = 8000 + 3600 + 840 = 12440 B/s = 99.52 kbps
        self.assertEqual(cc.client_down_bps(20, 30, r), 12440 * 8)
        # 30Hz * (32 + 28)B = 1800 B/s = 14.4 kbps
        self.assertEqual(cc.client_up_bps(r), 1800 * 8)

    def test_default_scenario(self):
        rep = cc.calculate(scenario())
        s, c = rep["summary"], rep["cases"]
        self.assertEqual(s["servers_needed"], 20)            # 3000 / 150
        self.assertEqual(s["servers_with_headroom"], 26)     # 20 * 1.3
        self.assertEqual(c["average"]["client_down_kbps"], 99.5)
        # 밀집: 60*10*40 + 3600 + 840 = 28440 B/s = 227.5 kbps, 서버 150명 → 34.13 Mbps
        self.assertEqual(c["crowd"]["client_down_kbps"], 227.5)
        self.assertEqual(c["crowd"]["server_egress_mbps"], 34.13)
        self.assertEqual(c["crowd"]["entity_updates_per_sec"], 150 * (600 + 150))
        self.assertTrue(s["passed"])
        self.assertEqual(rep["findings"], [])

    def test_monthly_traffic(self):
        s = cc.calculate(scenario())["summary"]
        # 12440 B/s * 1500명 * 2,592,000초 = 48.37 TB
        self.assertAlmostEqual(s["monthly_egress_tb"], 48.37, places=2)

    def test_crowd_over_client_budget_fails(self):
        rep = cc.calculate(scenario(aoi={"max_visible_players": 100}))
        self.assertFalse(rep["summary"]["passed"])
        # 100명*10Hz*40B + 3600 + 840 = 44440 B/s = 355.5 kbps (예산 256), 서버 53.33 Mbps (예산 50),
        # 초당 갱신 150 * (1000 + 150) = 172,500 (예산 150,000)
        self.assertEqual(rep["cases"]["crowd"]["client_down_kbps"], 355.5)
        self.assertEqual([f["rule"] for f in rep["findings"]], ["CAP001", "CAP002", "CAP004"])

    def test_aoi_cap_above_server_cap_is_flagged(self):
        rep = cc.calculate(scenario(aoi={"max_visible_players": 200}, budget={"client_down_kbps_max": 9999,
                                                                             "server_egress_mbps_max": 9999}))
        self.assertIn("CAP003", [f["rule"] for f in rep["findings"]])
        # 보이는 인원은 서버 인원 - 1을 넘을 수 없다
        self.assertEqual(rep["cases"]["crowd"]["visible_players"], 149)

    def test_aoi_saving_ratio(self):
        rep = cc.calculate(scenario())
        c = rep["cases"]
        self.assertAlmostEqual(rep["summary"]["aoi_saving_ratio"],
                               c["no_aoi"]["server_egress_mbps"] / c["crowd"]["server_egress_mbps"], places=1)
        self.assertGreater(rep["summary"]["aoi_saving_ratio"], 2)

    def test_update_budget(self):
        rep = cc.calculate(scenario(budget={"entity_updates_per_sec_max": 100000}))
        self.assertEqual([f["rule"] for f in rep["findings"]], ["CAP004"])
        self.assertTrue(rep["summary"]["passed"])  # warning이라 통과

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "o", "r.md")
            self.assertEqual(cc.main([SCENARIO_PATH, "--md", md]), 0)
            with open(md, encoding="utf-8") as f:
                self.assertIn("밀집", f.read())
            bad = os.path.join(d, "bad.json")
            with open(bad, "w") as f:
                f.write("{}")
            self.assertEqual(cc.main([bad]), 2)


if __name__ == "__main__":
    unittest.main()
