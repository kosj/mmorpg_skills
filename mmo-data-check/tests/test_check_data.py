"""check_data.py 단위 테스트: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_data as cd  # noqa: E402

with open(os.path.join(ROOT, "references", "data-schema.json"), encoding="utf-8") as f:
    SCHEMA = json.load(f)

GOOD = {
    "items.csv": "id,name,grade,level_req,price_buy,price_sell,max_stack\n"
                 "1,Sword,common,1,100,25,1\n2,Potion,common,1,10,2,99\n",
    "monsters.csv": "id,name,level,hp,exp_reward,gold_min,gold_max,drop_group\n"
                    "1,Slime,1,50,5,1,3,10\n2,Dummy,1,1,0,0,0,0\n",
    "drops.csv": "group_id,item_id,prob,min_count,max_count\n10,1,0.1,1,1\n10,2,0.5,1,3\n",
    "levels.csv": "level,exp_required\n1,0\n2,100\n3,250\n",
}


def run(overrides=None, remove=()):
    files = dict(GOOD)
    files.update(overrides or {})
    with tempfile.TemporaryDirectory() as d:
        for name, text in files.items():
            if name not in remove:
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(text)
        return cd.check(d, SCHEMA)


def rules(report):
    return sorted(f["rule"] for f in report["findings"])


class DataCheck(unittest.TestCase):
    def test_good_data_passes(self):
        r = run()
        self.assertEqual(rules(r), [])
        self.assertTrue(r["summary"]["passed"])
        self.assertEqual(r["summary"]["rows"], 9)

    def test_missing_file(self):
        self.assertEqual(rules(run(remove=("levels.csv",))), ["DATA001"])

    def test_missing_column(self):
        r = run({"levels.csv": "level,exp\n1,0\n"})
        self.assertEqual(rules(r), ["DATA002"])

    def test_duplicate_key(self):
        r = run({"levels.csv": "level,exp_required\n1,0\n2,100\n2,200\n"})
        self.assertEqual(rules(r), ["DATA003", "DATA003"])

    def test_type_range_enum_required(self):
        r = run({"items.csv": "id,name,grade,level_req,price_buy,price_sell,max_stack\n"
                              "1,Sword,common,abc,100,25,1\n"
                              "2,,mythic,500,10,2,99\n"})
        self.assertEqual(rules(r), ["DATA004", "DATA005", "DATA006", "DATA008"])

    def test_broken_reference(self):
        r = run({"drops.csv": "group_id,item_id,prob,min_count,max_count\n10,999,0.1,1,1\n"})
        self.assertEqual(rules(r), ["DATA007"])
        self.assertIn("999", r["findings"][0]["message"])

    def test_ref_allow_zero_means_none(self):
        self.assertNotIn("DATA007", rules(run()))  # Dummy의 drop_group 0

    def test_drop_probability_sum(self):
        r = run({"drops.csv": "group_id,item_id,prob,min_count,max_count\n10,1,0.6,1,1\n10,2,0.5,1,1\n"})
        self.assertEqual(rules(r), ["DATA009"])

    def test_sell_above_buy_is_economy_exploit(self):
        r = run({"items.csv": "id,name,grade,level_req,price_buy,price_sell,max_stack\n"
                              "1,Sword,common,1,100,150,1\n2,Potion,common,1,10,2,99\n"})
        self.assertEqual(rules(r), ["DATA010"])
        self.assertIn("무한", r["findings"][0]["message"])

    def test_level_curve(self):
        r = run({"levels.csv": "level,exp_required\n1,0\n2,100\n3,90\n5,300\n"})
        self.assertEqual(rules(r), ["DATA011", "DATA012"])
        self.assertFalse(r["summary"]["passed"])

    def test_list_column_with_separator(self):
        schema = json.loads(json.dumps(SCHEMA))
        schema["tables"]["monsters"]["columns"]["drop_group"] = {
            "type": "int", "ref": "drops.group_id", "sep": "|"}
        with tempfile.TemporaryDirectory() as d:
            files = dict(GOOD)
            files["monsters.csv"] = ("id,name,level,hp,exp_reward,gold_min,gold_max,drop_group\n"
                                     "1,Slime,1,50,5,1,3,10|77\n")
            for name, text in files.items():
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(text)
            r = cd.check(d, schema)
        self.assertEqual(rules(r), ["DATA007"])
        self.assertIn("77", r["findings"][0]["message"])

    def test_cli_exit_codes(self):
        schema = os.path.join(ROOT, "references", "data-schema.json")
        with tempfile.TemporaryDirectory() as d:
            for name, text in GOOD.items():
                with open(os.path.join(d, name), "w", encoding="utf-8") as f:
                    f.write(text)
            self.assertEqual(cd.main([d, "--schema", schema, "--md", os.path.join(d, "o", "r.md")]), 0)
            os.remove(os.path.join(d, "items.csv"))
            self.assertEqual(cd.main([d, "--schema", schema]), 1)
        self.assertEqual(cd.main(["/nonexistent-dir", "--schema", schema]), 2)


if __name__ == "__main__":
    unittest.main()
