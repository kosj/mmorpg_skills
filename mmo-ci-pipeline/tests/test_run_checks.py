"""run_checks.py 단위 테스트: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.dirname(ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import run_checks as rc  # noqa: E402

REAL_PIPELINE = os.path.join(ROOT, "references", "pipeline.json")


def exit_with(code, text="done"):
    return ["{python}", "-c", f"import sys; print({text!r}); sys.exit({code})"]


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "Data"))
        self.pipe = {
            "vars": {"root": self.root, "data": "Data"},
            "checks": [
                {"id": "ok", "stages": ["precommit", "nightly"], "triggers": ["{data}/**"], "inputs": ["{data}"],
                 "command": exit_with(0, '{"passed": true}')},
                {"id": "bad", "stages": ["precommit"], "triggers": ["Source/**/*.cpp"], "command": exit_with(1, "2 errors")},
                {"id": "broken", "stages": ["nightly"], "command": exit_with(2)},
                {"id": "optional", "stages": ["nightly"], "required": False, "inputs": ["Saved/none.json"],
                 "command": exit_with(0)},
                {"id": "needs", "stages": ["nightly"], "inputs": ["Missing/dir"], "command": exit_with(0)},
            ],
            "co_change": [{"id": "map-needs-data", "when_changed": ["Content/**/*.umap"],
                           "must_also_change": ["ServerData/**"], "message": "서버 데이터 갱신 필요"}],
        }

    def tearDown(self):
        self.tmp.cleanup()

    def path(self, name, content):
        p = os.path.join(self.root, name)
        with open(p, "w", encoding="utf-8") as f:
            f.write(content if isinstance(content, str) else json.dumps(content))
        return p

    def run_main(self, *args, changed=None):
        argv = ["--pipeline", self.path("pipeline.json", self.pipe), "--out", os.path.join(self.root, "r.json")]
        if changed is not None:
            argv += ["--changed-files", self.path("changed.txt", "\n".join(changed))]
        code = rc.main(argv + list(args))
        with open(os.path.join(self.root, "r.json"), encoding="utf-8") as f:
            rep = json.load(f)
        return code, {r["id"]: r["status"] for r in rep["results"]}, rep


class Glob(unittest.TestCase):
    def test_patterns(self):
        self.assertTrue(rc.matches("Data/Tables/items.csv", ["Data/**"]))
        self.assertTrue(rc.matches("Source/Game/Net/Hero.cpp", ["Source/**/*.cpp"]))
        self.assertTrue(rc.matches("Source/Hero.cpp", ["Source/**/*.cpp"]))        # 폴더 0개
        self.assertFalse(rc.matches("Source/Game/Hero.h", ["Source/**/*.cpp"]))
        self.assertFalse(rc.matches("Data2/items.csv", ["Data/**"]))
        self.assertFalse(rc.matches("Data/a/b.csv", ["Data/*.csv"]))               # *는 폴더를 넘지 않는다
        self.assertTrue(rc.matches("Data\\Tables\\items.csv", ["Data/**"]))        # 윈도우 경로

    def test_expand_nested_vars(self):
        self.assertEqual(rc.expand("{a}/x", {"a": "{b}/y", "b": "root"}), "root/y/x")
        self.assertEqual(rc.expand("{unknown}", {}), "{unknown}")


class Stages(Base):
    def test_precommit_without_change_list_runs_everything_in_stage(self):
        code, st, _ = self.run_main("--stage", "precommit")
        self.assertEqual((code, st), (1, {"ok": "pass", "bad": "fail"}))

    def test_only_triggered_checks_run(self):
        code, st, _ = self.run_main("--stage", "precommit", changed=["Data/items.csv"])
        self.assertEqual((code, st), (0, {"ok": "pass", "bad": "not_triggered"}))
        code, st, _ = self.run_main("--stage", "precommit", changed=["Source/Net/Hero.cpp"])
        self.assertEqual((code, st), (1, {"ok": "not_triggered", "bad": "fail"}))

    def test_nightly_statuses(self):
        code, st, rep = self.run_main("--stage", "nightly")
        self.assertEqual(st, {"ok": "pass", "broken": "error", "optional": "missing_input", "needs": "missing_input"})
        self.assertEqual(code, 1)
        # 선택 검사의 입력 없음은 실패로 세지 않는다
        self.assertEqual(sorted(rep["summary"]["failed"]), ["broken", "needs"])

    def test_detail_keeps_last_output_line(self):
        _, _, rep = self.run_main("--stage", "precommit")
        detail = {r["id"]: r["detail"] for r in rep["results"]}
        self.assertEqual(detail["bad"], "2 errors")

    def test_only_and_list(self):
        code, st, _ = self.run_main("--stage", "all", "--only", "ok")
        self.assertEqual((code, st), (0, {"ok": "pass"}))
        self.assertEqual(rc.main(["--pipeline", self.path("pipeline.json", self.pipe), "--stage", "all", "--list"]), 0)

    def test_timeout(self):
        self.pipe["checks"] = [{"id": "slow", "stages": ["precommit"], "timeout_sec": 1,
                                "command": ["{python}", "-c", "import time; time.sleep(5)"]}]
        code, st, _ = self.run_main("--stage", "precommit")
        self.assertEqual((code, st), (1, {"slow": "timeout"}))


class CoChange(Base):
    def test_map_change_without_server_data_fails(self):
        code, st, rep = self.run_main("--stage", "precommit", changed=["Content/Maps/Field_01.umap"])
        self.assertEqual(code, 1)
        self.assertEqual(st["map-needs-data"], "fail")
        self.assertIn("Field_01.umap", [r for r in rep["results"] if r["id"] == "map-needs-data"][0]["detail"])

    def test_map_change_with_server_data_passes(self):
        code, st, _ = self.run_main("--stage", "precommit",
                                    changed=["Content/Maps/Field_01.umap", "ServerData/World/Field_01/manifest.json"])
        self.assertEqual(code, 0)
        self.assertNotIn("map-needs-data", st)

    def test_not_checked_without_change_list(self):
        _, st, _ = self.run_main("--stage", "nightly")
        self.assertNotIn("map-needs-data", st)


class Config(Base):
    def test_bad_config(self):
        self.pipe["checks"].append({"id": "ok", "stages": ["precommit"], "command": exit_with(0)})
        self.assertEqual(rc.main(["--pipeline", self.path("pipeline.json", self.pipe)]), 2)
        self.assertEqual(rc.main(["--pipeline", os.path.join(self.root, "none.json")]), 2)


class RealPipeline(unittest.TestCase):
    """references/pipeline.json의 명령줄이 실제 스킬 스크립트와 맞는지, 스킬들의 예시 데이터로 확인한다."""

    def test_commands_work_against_example_data(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "r.json")
            code = rc.main([
                "--pipeline", REAL_PIPELINE, "--stage", "all", "--only", "combat,protocol,contract,skill-tests",
                "--var", f"root={PACK}", "--var", "skills=.", "--var", f"reports={d}",
                "--var", "skills_csv=mmo-combat-skill/references/example/skills.csv",
                "--var", "schema_dir=mmo-protocol-check/references/example",
                "--var", "contract_dir=ue-client-contract/references/example",
                "--var", "data_dir=mmo-quest-check/references/example",
                "--var", "quests_csv=mmo-quest-check/references/example/quests.csv",
                "--only", "data,economy,quest,combat,protocol,contract", "--out", out])
            with open(out, encoding="utf-8") as f:
                rep = json.load(f)
            self.assertEqual({r["id"]: r["status"] for r in rep["results"]},
                             {"data": "pass", "combat": "pass", "economy": "pass", "quest": "pass", "protocol": "pass",
                              "contract": "pass"}, rep["results"])
            self.assertEqual(code, 0)
            self.assertTrue(os.path.isfile(os.path.join(d, "contract-matrix.md")))

    def test_every_check_script_exists(self):
        pipe, variables = rc.load_pipeline(REAL_PIPELINE, {"skills": "."})
        for c in pipe["checks"]:
            script = rc.expand(c["command"][1], variables)
            self.assertTrue(os.path.isfile(os.path.join(PACK, script)), script)

    def test_real_co_change_rules(self):
        pipe, variables = rc.load_pipeline(REAL_PIPELINE)
        ids = lambda changed: [p["id"] for p in rc.check_co_change(pipe, variables, changed)]  # noqa: E731
        self.assertEqual(ids(["Content/Maps/Field_01.umap"]), ["map-needs-server-data"])
        self.assertEqual(ids(["Protocol/combat.fbs"]), ["schema-needs-lock"])
        self.assertEqual(ids(["Protocol/combat.fbs", "Protocol/protocol.lock.json"]), [])
        self.assertEqual(ids(["Content/Maps/Field_01.umap", "ServerData/World/Field_01/manifest.json"]),
                         ["server-data-needs-client-version"])
        self.assertEqual(ids(["Content/Maps/Field_01.umap", "ServerData/World/Field_01/manifest.json",
                              "Content/Data/map_versions.json"]), [])


if __name__ == "__main__":
    unittest.main()
