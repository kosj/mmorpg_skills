"""check_strings.py 단위 테스트: python -m unittest discover -s tests"""
import copy
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_strings as cs  # noqa: E402

EXAMPLE = os.path.join(ROOT, "references", "example", "strings.csv")
USED = os.path.join(ROOT, "references", "example", "used_keys.txt")
BASE = cs.read_csv(EXAMPLE, cs._cfg(None))


def rows(**changes):
    """changes: {키의 점을 밑줄로 바꾼 이름: {열: 값}}"""
    out = copy.deepcopy(BASE)
    for _, r in out:
        r.update(changes.get(r["key"].replace(".", "_"), {}))
    return out


def found(r, config=None, used=None):
    return sorted((f["rule"], f["key"], f["lang"]) for f in cs.check(r, config, used)["findings"])


class Helpers(unittest.TestCase):
    def test_width_counts_wide_chars_double_and_skips_placeholders(self):
        self.assertEqual(cs.width("확인"), 4)
        self.assertEqual(cs.width("OK"), 2)
        self.assertEqual(cs.width("<b>화염</b> {0}"), 5)      # 화염 4 + 공백 1

    def test_placeholders_ignore_order(self):
        self.assertEqual(cs.placeholders("{monster} {count}마리"), cs.placeholders("Defeat {count} {monster}"))
        self.assertEqual(cs.placeholders("%d개 100%% <b>x</b>"), ["%d", "</b>", "<b>"])

    def test_unbalanced(self):
        self.assertIsNone(cs.unbalanced("<b>{0}</b>"))
        self.assertIn("중괄호", cs.unbalanced("{0 피해"))
        self.assertIn("닫히지", cs.unbalanced("<b>화염"))
        self.assertIn("짝", cs.unbalanced("<b>화염</i>"))


class Rules(unittest.TestCase):
    def test_example_is_clean(self):
        rep = cs.check(rows())
        self.assertEqual(rep["findings"], [])
        self.assertEqual(rep["summary"]["coverage"], {"en": 1.0})

    def test_duplicate_and_empty_key(self):
        r = rows(ui_cancel={"key": "ui.ok"}, npc_greet={"key": ""})
        self.assertEqual([x[0] for x in found(r)], ["LOC001", "LOC001"])

    def test_missing_translation_required_vs_optional(self):
        rep = cs.check(rows(ui_ok={"en": ""}))
        self.assertEqual([(f["rule"], f["severity"]) for f in rep["findings"]], [("LOC002", "error")])
        rep = cs.check(rows(), {"optional_languages": ["ja"]})
        self.assertEqual({(f["rule"], f["severity"], f["lang"]) for f in rep["findings"]}, {("LOC002", "warning", "ja")})
        self.assertTrue(rep["summary"]["passed"])

    def test_placeholder_mismatch(self):
        rep = cs.check(rows(quest_kill={"en": "Defeat {count} {monstar}"}, item_count={"en": "%s owned"}))
        self.assertEqual([(f["rule"], f["key"]) for f in rep["findings"]], [("LOC003", "quest.kill"), ("LOC003", "item.count")])
        self.assertIn("빠짐: {monster}", rep["findings"][0]["message"])
        self.assertIn("원문에 없음: {monstar}", rep["findings"][0]["message"])

    def test_missing_format_tag(self):
        self.assertEqual(found(rows(skill_desc_fire={"en": "Deals {0} fire damage."})), [("LOC003", "skill.desc.fire", "en")])

    def test_unbalanced_translation(self):
        f = found(rows(skill_desc_fire={"en": "Deals {0} <b>fire damage."}))
        self.assertIn(("LOC007", "skill.desc.fire", "en"), f)

    def test_width_limit_and_expansion(self):
        self.assertEqual(found(rows(ui_cancel={"en": "Cancel order"})), [("LOC004", "ui.cancel", "en")])
        long = "You are not able to take off or keep flying while a storm is raging in this region right now."
        self.assertEqual(found(rows(mount_no_fly={"en": long})), [("LOC004", "mount.no_fly", "en")])

    def test_source_over_limit_is_reported_too(self):
        self.assertEqual(found(rows(ui_ok={"ko": "확인했습니다"})), [("LOC004", "ui.ok", "ko")])

    def test_untranslated(self):
        self.assertEqual(found(rows(npc_greet={"en": "어서 오세요, 모험가님."})), [("LOC005", "npc.greet", "en")])
        self.assertNotIn("LOC005", [x[0] for x in found(rows())])   # {0}%는 같아도 된다

    def test_whitespace(self):
        self.assertEqual(found(rows(ui_ok={"en": "OK "})), [("LOC006", "ui.ok", "en")])
        self.assertEqual(found(rows(npc_greet={"en": "Welcome,  adventurer."})), [("LOC006", "npc.greet", "en")])

    def test_used_keys(self):
        with open(USED, encoding="utf-8") as f:
            used = [k.strip() for k in f if k.strip()]
        rep = cs.check(rows(), None, used + ["ui.retry"])
        self.assertEqual([(f["rule"], f["key"]) for f in rep["findings"]], [("LOC008", "ui.retry")])
        self.assertEqual(cs.check(rows(), None, used[:5])["summary"]["unused_keys"], 3)


class Cli(unittest.TestCase):
    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            md = os.path.join(d, "o", "r.md")
            self.assertEqual(cs.main([EXAMPLE, "--used-keys", USED, "--md", md]), 0)
            with open(md, encoding="utf-8") as f:
                self.assertIn("번역률", f.read())
            bad = os.path.join(d, "bad.csv")
            with open(bad, "w", encoding="utf-8") as f:
                f.write("key,ko\nui.ok,확인\n")
            self.assertEqual(cs.main([bad]), 2)          # 필수 언어 열이 없다
        self.assertEqual(cs.main(["/nonexistent.csv"]), 2)


if __name__ == "__main__":
    unittest.main()
