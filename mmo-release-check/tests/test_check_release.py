"""check_release.py 단위 테스트: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_release as cr  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = self.tmp.name
        self.write("Protocol/game.fbs", "table C2S_Move (packet_id: 1001) { seq: uint; }\n")
        self.write("Protocol/protocol.lock.json", '{"version": 1}\n')
        self.write("Protocol/notes.txt", "해시에 들어가지 않는 파일\n")
        self.write("Data/items.csv", "id,name\n1,Sword\n")
        self.write("Data/monsters.csv", "id,name\n1,Slime\n")
        self.write("map_versions.json", '{"Field_01": "aaaa", "Town_01": "bbbb"}')

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, rel):
        return os.path.join(self.d, rel)

    def write(self, rel, text, mode="w"):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), mode, **({} if "b" in mode else {"encoding": "utf-8"})) as f:
            f.write(text)

    def make(self, name="client", build="1.0.0", proto=1):
        return cr.make(name, build, proto, self.path("Protocol"), self.path("Data"), self.path("map_versions.json"))

    def rules(self, *args, **kw):
        return sorted(f["rule"] for f in cr.compare(*args, **kw)["findings"])


class Manifest(Base):
    def test_same_inputs_same_hashes(self):
        a, b = self.make("client"), self.make("server")
        self.assertEqual((a["protocol_hash"], a["data_hash"]), (b["protocol_hash"], b["data_hash"]))
        self.assertEqual(sorted(a["protocol_files"]), ["game.fbs", "protocol.lock.json"])   # notes.txt 제외

    def test_line_endings_do_not_change_hash(self):
        before = self.make()["data_hash"]
        self.write("Data/items.csv", b"id,name\r\n1,Sword\r\n", "wb")
        self.assertEqual(self.make()["data_hash"], before)

    def test_content_change_changes_hash(self):
        before = self.make()
        self.write("Data/items.csv", "id,name\n1,Blade\n")
        after = self.make()
        self.assertNotEqual(after["data_hash"], before["data_hash"])
        self.assertEqual(after["protocol_hash"], before["protocol_hash"])


class Compare(Base):
    def test_matching_builds_pass(self):
        rep = cr.compare(self.make("client"), self.make("server"))
        self.assertEqual(rep["findings"], [])
        self.assertTrue(rep["summary"]["passed"])

    def test_protocol_mismatch_names_the_file(self):
        client = self.make("client")
        self.write("Protocol/game.fbs", "table C2S_Move (packet_id: 1001) { seq: uint; yaw: short; }\n")
        rep = cr.compare(client, self.make("server"))
        self.assertEqual([f["rule"] for f in rep["findings"]], ["REL002"])
        self.assertIn("game.fbs (내용 다름)", rep["findings"][0]["message"])

    def test_protocol_version_mismatch(self):
        self.assertEqual(self.rules(self.make("client", proto=2), self.make("server", proto=1)), ["REL002"])

    def test_data_mismatch_and_extra_file(self):
        client = self.make("client")
        self.write("Data/items.csv", "id,name\n1,Blade\n")
        self.write("Data/quests.csv", "id\n1\n")
        rep = cr.compare(client, self.make("server"))
        self.assertEqual([f["rule"] for f in rep["findings"]], ["REL003"])
        self.assertIn("quests.csv (한쪽에만 있음)", rep["findings"][0]["message"])

    def test_map_version_mismatch(self):
        client = self.make("client")
        self.write("map_versions.json", '{"Field_01": "cccc", "Town_01": "bbbb"}')
        rep = cr.compare(client, self.make("server"))
        self.assertEqual([f["rule"] for f in rep["findings"]], ["REL004"])
        self.assertIn("Field_01", rep["findings"][0]["message"])
        self.assertNotIn("Town_01", rep["findings"][0]["message"])

    def test_bad_manifest(self):
        self.assertEqual(self.rules({}, self.make("server")), ["REL001"])


class Previous(Base):
    def test_same_build_number_with_changes(self):
        prev = self.make(build="1.0.0")
        self.write("Data/items.csv", "id,name\n1,Blade\n")
        cur_c, cur_s = self.make("client", "1.0.0"), self.make("server", "1.0.0")
        self.assertEqual(self.rules(cur_c, cur_s, previous=prev), ["REL005"])
        self.assertEqual(self.rules(self.make("client", "1.0.1"), self.make("server", "1.0.1"), previous=prev), [])

    def test_protocol_changed_without_version_bump(self):
        prev = self.make(build="1.0.0", proto=1)
        self.write("Protocol/game.fbs", "table C2S_Move (packet_id: 1001) { seq: uint; yaw: short; }\n")
        same = (self.make("client", "1.1.0", 1), self.make("server", "1.1.0", 1))
        self.assertEqual(self.rules(*same, previous=prev), ["REL007"])
        bumped = (self.make("client", "1.1.0", 2), self.make("server", "1.1.0", 2))
        self.assertEqual(self.rules(*bumped, previous=prev), [])

    def test_nothing_changed_is_warning(self):
        prev = self.make(build="1.0.0")
        rep = cr.compare(self.make("client", "1.0.1"), self.make("server", "1.0.1"), previous=prev)
        self.assertEqual([(f["rule"], f["severity"]) for f in rep["findings"]], [("REL008", "warning")])
        self.assertTrue(rep["summary"]["passed"])


class Pipeline(Base):
    def test_pipeline_report_must_pass(self):
        c, s = self.make("client"), self.make("server")
        self.assertEqual(self.rules(c, s, pipeline_report={"summary": {"passed": True, "failed": []}}), [])
        rep = cr.compare(c, s, pipeline_report={"summary": {"passed": False, "failed": ["protocol", "world"]}})
        self.assertEqual([f["rule"] for f in rep["findings"]], ["REL006"])
        self.assertIn("protocol, world", rep["findings"][0]["message"])
        self.assertEqual(self.rules(c, s, pipeline_report={}), ["REL006"])


class Cli(Base):
    def test_make_and_compare(self):
        args = ["--protocol-version", "1", "--schema-dir", self.path("Protocol"), "--data-dir", self.path("Data"),
                "--map-versions", self.path("map_versions.json")]
        c, s = self.path("out/client.json"), self.path("out/server.json")
        self.assertEqual(cr.main(["make", "--name", "client", "--build", "1.0.0", "--out", c] + args), 0)
        self.write("Data/items.csv", "id,name\n1,Blade\n")
        self.assertEqual(cr.main(["make", "--name", "server", "--build", "1.0.0", "--out", s] + args), 0)
        md = self.path("out/r.md")
        self.assertEqual(cr.main(["compare", c, s, "--md", md]), 1)
        with open(md, encoding="utf-8") as f:
            self.assertIn("REL003", f.read())
        self.assertEqual(cr.main(["compare", c, c]), 0)
        self.assertEqual(cr.main(["compare", c, self.path("none.json")]), 2)
        self.assertEqual(cr.main(["make", "--name", "x", "--build", "1", "--out", c, "--protocol-version", "1",
                                  "--schema-dir", self.path("Nope"), "--data-dir", self.path("Data"),
                                  "--map-versions", self.path("map_versions.json")]), 2)


if __name__ == "__main__":
    unittest.main()
