"""check_quests.py 단위 테스트: python -m unittest discover -s tests"""
import copy
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_quests as cq  # noqa: E402

EXAMPLE = os.path.join(ROOT, "references", "example")
BASE = cq.read_tables(EXAMPLE, cq._cfg(None))


def tables(**changes):
    """changes: {"q<퀘스트 id>": {열: 값}}"""
    t = copy.deepcopy(BASE)
    for _, r in t["quests"]:
        r.update(changes.get("q" + r["id"], {}))
    return t


def found(t, config=None):
    return sorted((f["rule"], f["id"]) for f in cq.check(t, config)["findings"])


class Example(unittest.TestCase):
    def test_example_is_clean(self):
        rep = cq.check(tables())
        self.assertEqual(rep["findings"], [])
        self.assertEqual(rep["summary"]["by_type"], {"daily": 1, "main": 7, "side": 2})

    def test_coverage_table_excludes_daily(self):
        cov = {c["level"]: c for c in cq.check(tables())["coverage"]}
        self.assertEqual(cov[1]["quest_exp"], 600)      # 100 + 300 + 200
        self.assertEqual(cov[5]["quest_exp"], 1500)     # 일일 퀘스트 400은 빼고
        self.assertEqual(cov[1]["share"], 0.67)


class Structure(unittest.TestCase):
    def test_format(self):
        t = tables(q3={"reward_exp": "many"}, q6={"type": "epic"}, q8={"id": "7"})
        self.assertEqual([r for r, _ in found(t)], ["QUEST001"] * 3)

    def test_unknown_and_self_prerequisite(self):
        self.assertEqual(found(tables(q4={"prev_quests": "99"}))[0], ("QUEST002", "4"))
        self.assertIn(("QUEST002", "3"), found(tables(q3={"prev_quests": "3"})))

    def test_cycle_is_reported_once_with_path(self):
        rep = cq.check(tables(q1={"prev_quests": "5"}))      # 1 → 5 → 4 → 2 → 1
        cyc = [f for f in rep["findings"] if f["rule"] == "QUEST003"]
        self.assertEqual(len(cyc), 1)
        self.assertEqual(cyc[0]["message"].split(": ")[1], "1 → 5 → 4 → 2 → 1")
        self.assertFalse(rep["summary"]["passed"])

    def test_two_separate_cycles(self):
        t = tables(q3={"prev_quests": "6"}, q6={"prev_quests": "3"}, q1={"prev_quests": "2"})
        self.assertEqual(len([f for f in cq.check(t)["findings"] if f["rule"] == "QUEST003"]), 2)

    def test_prerequisite_with_higher_level(self):
        self.assertEqual(found(tables(q6={"prev_quests": "7"})), [("QUEST004", "6")])


class Links(unittest.TestCase):
    def test_unknown_targets_and_rewards(self):
        t = tables(q2={"objective_target": "999"}, q3={"objective_target": "999"}, q5={"reward_items": "2003|8888"})
        self.assertEqual(found(t), [("QUEST005", "2"), ("QUEST005", "3"), ("QUEST008", "5")])

    def test_zero_count(self):
        self.assertEqual(found(tables(q2={"objective_count": "0"})), [("QUEST005", "2")])

    def test_collect_item_nobody_drops_or_sells(self):
        t = tables(q3={"objective_target": "1001"})
        t["drops"] = [(i, r) for i, r in t["drops"] if r["item_id"] != "1001"]
        self.assertEqual(found(t), [("QUEST006", "3")])

    def test_collect_item_sold_by_vendor_is_obtainable(self):
        self.assertEqual(found(tables(q3={"objective_target": "2001"})), [])   # 상점 판매 장비

    def test_collect_needs_too_many_kills(self):
        # 재료 1003의 최대 기대 개수는 마리당 0.4 * 1.5 = 0.6 → 60개면 평균 100마리
        rep = cq.check(tables(q6={"objective_count": "60"}))
        self.assertEqual([(f["rule"], f["id"]) for f in rep["findings"]], [("QUEST013", "6")])
        self.assertIn("100마리", rep["findings"][0]["message"])

    def test_target_level_mismatch(self):
        self.assertEqual(found(tables(q2={"objective_target": "208"})), [("QUEST007", "2")])


class Pacing(unittest.TestCase):
    def test_main_quest_level_gap(self):
        self.assertEqual(found(tables(q9={"level_req": "9"})), [("QUEST009", "9")])

    def test_second_main_root(self):
        self.assertEqual(found(tables(q7={"prev_quests": ""})), [("QUEST011", "7")])

    def test_exp_reward_too_large_for_level(self):
        # 레벨 1에서 2로 가는 데 900이 필요하다. 500은 56%
        rep = cq.check(tables(q2={"reward_exp": "500"}))
        self.assertEqual([(f["rule"], f["id"]) for f in rep["findings"]], [("QUEST010", "2")])
        self.assertIn("56%", rep["findings"][0]["message"])

    def test_levels_table_is_optional(self):
        t = tables(q2={"reward_exp": "500"})
        t["levels"] = []
        rep = cq.check(t)
        self.assertEqual(rep["findings"], [])
        self.assertEqual(rep["coverage"], [])


class Cli(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "o", "r.md")
            self.assertEqual(cq.main([EXAMPLE, "--md", md]), 0)
            with open(md, encoding="utf-8") as f:
                self.assertIn("레벨별 퀘스트 경험치", f.read())
            data = os.path.join(d, "data")
            shutil.copytree(EXAMPLE, data)
            os.remove(os.path.join(data, "levels.csv"))
            self.assertEqual(cq.main([data]), 0)             # levels는 없어도 된다
            os.remove(os.path.join(data, "quests.csv"))
            self.assertEqual(cq.main([data]), 2)
        self.assertEqual(cq.main(["/nonexistent-dir"]), 2)


if __name__ == "__main__":
    unittest.main()
