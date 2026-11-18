"""check_protocol.py 단위 테스트: python -m unittest discover -s tests"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import check_protocol as cp  # noqa: E402

EXAMPLE_DIR = os.path.join(ROOT, "references", "example")
with open(os.path.join(EXAMPLE_DIR, "game.fbs"), encoding="utf-8") as f:
    EXAMPLE = f.read()


def run(text=EXAMPLE, lock=None, lock_given=False):
    report, schema, pk = cp.check({"game.fbs": text}, None, lock, lock_given)
    return report, schema, pk


def rules(text=EXAMPLE, lock=None):
    return sorted(f["rule"] for f in run(text, lock)[0]["findings"])


def lock_of(text=EXAMPLE):
    _, schema, pk = run(text)
    return cp.make_lock(schema, pk)


class Parsing(unittest.TestCase):
    def test_example_is_clean(self):
        report, schema, pk = run()
        self.assertEqual(report["findings"], [])
        s = report["summary"]
        self.assertEqual((s["packets"], s["c2s"], s["s2c"]), (8, 4, 4))
        self.assertIn("Game.Protocol.C2S_Move", schema.decls)
        self.assertEqual(schema.decls["Game.Protocol.EChatChannel"]["values"]["World"], 3)

    def test_comment_text_is_not_parsed(self):
        text = EXAMPLE + "\n// table C2S_Fake (packet_id: 1001) { x: int; }\n"
        self.assertEqual(rules(text), [])

    def test_union_takes_two_slots(self):
        text = ("union U { A, B }\ntable A { x: int; }\ntable B { y: int; }\n"
                "table T { first: int; u: U; last: int; }\n")
        schema = cp.Schema({"a.fbs": text})
        self.assertEqual(schema.slots(schema.decls["T"]), [0, 2, 3])


class PacketRules(unittest.TestCase):
    def test_duplicate_id(self):
        text = EXAMPLE.replace("packet_id: 1002", "packet_id: 1001")
        self.assertEqual(rules(text), ["PROTO001", "PROTO001"])

    def test_missing_id_and_out_of_range(self):
        self.assertEqual(rules(EXAMPLE.replace("(packet_id: 2001)", "")), ["PROTO002"])
        self.assertEqual(rules(EXAMPLE.replace("packet_id: 2001", "packet_id: 70000")), ["PROTO002"])

    def test_unknown_direction(self):
        text = EXAMPLE + "\ntable Ping (packet_id: 3001) { t: uint; }\n"
        self.assertEqual(rules(text), ["PROTO002"])
        text = EXAMPLE + '\ntable Ping (packet_id: 3001, dir: "s2c") { t: uint; }\n'
        self.assertEqual(rules(text), [])

    def test_client_sends_result_value(self):
        text = EXAMPLE.replace("  skill_id: uint;\n  target_id: ulong;\n  aim: Vec3;",
                               "  skill_id: uint;\n  target_id: ulong;\n  aim: Vec3;\n  damage: int;")
        report = run(text)[0]
        self.assertEqual([f["rule"] for f in report["findings"]], ["PROTO004"])
        self.assertIn("C2S_UseSkill.damage", report["findings"][0]["message"])

    def test_server_may_send_result_value(self):
        self.assertNotIn("PROTO004", rules())  # S2C_SkillResult.damage, EntityState.hp

    def test_nested_table_in_c2s_is_checked(self):
        text = EXAMPLE + ("\ntable TradeOffer { item_ids: [ulong]; gold_amount: ulong; }\n"
                          "table C2S_Trade (packet_id: 1005, rate: 2) { target_id: ulong; offer: TradeOffer; }\n")
        report = run(text)[0]
        self.assertEqual(sorted(f["rule"] for f in report["findings"]), ["PROTO004", "PROTO005"])
        self.assertTrue(all("C2S_Trade에서 사용" in f["message"] for f in report["findings"]))

    def test_unbounded_string_and_missing_rate(self):
        self.assertEqual(rules(EXAMPLE.replace("text: string (max_len: 200);", "text: string;")), ["PROTO005"])
        self.assertEqual(rules(EXAMPLE.replace("(packet_id: 1003, rate: 3)", "(packet_id: 1003)")), ["PROTO006"])

    def test_undeclared_attribute(self):
        self.assertEqual(rules(EXAMPLE.replace('attribute "rate";', "")), ["PROTO008"] * 4)

    def test_ignore_comment(self):
        text = EXAMPLE.replace("  count: ushort;", "  // protolint:ignore PROTO004 UI 정렬용 값\n  sort_cost: ushort;")
        self.assertEqual(rules(text), [])


class Compatibility(unittest.TestCase):
    def test_unchanged_schema_passes(self):
        self.assertEqual(rules(lock=lock_of()), [])

    def test_append_field_is_ok(self):
        text = EXAMPLE.replace("  input_flags: ubyte;", "  input_flags: ubyte;\n  mount_id: uint;")
        self.assertEqual(rules(text, lock_of()), [])

    def test_remove_field(self):
        text = EXAMPLE.replace("  input_flags: ubyte;\n", "")
        self.assertEqual(rules(text, lock_of()), ["PROTO007"])

    def test_deprecate_instead_of_remove_is_ok(self):
        text = EXAMPLE.replace("  input_flags: ubyte;", "  input_flags: ubyte (deprecated);")
        self.assertEqual(rules(text, lock_of()), [])

    def test_insert_in_middle_shifts_slots(self):
        text = EXAMPLE.replace("  seq: uint;            // 클라이언트 입력 순번", "  tick: ulong;\n  seq: uint;            // 클라이언트 입력 순번")
        found = rules(text, lock_of())
        self.assertIn("PROTO007", found)

    def test_rename_is_info(self):
        text = EXAMPLE.replace("  from_slot: ushort;", "  source_slot: ushort;")
        report = run(text, lock_of())[0]
        self.assertEqual([(f["rule"], f["severity"]) for f in report["findings"]], [("PROTO009", "info")])
        self.assertTrue(report["summary"]["passed"])

    def test_struct_cannot_change(self):
        text = EXAMPLE.replace("  z: float;\n}", "  z: float;\n  w: float;\n}")
        self.assertEqual(rules(text, lock_of()), ["PROTO007"])

    def test_enum_value_change(self):
        text = EXAMPLE.replace("Guild = 2, World = 3", "World = 2, Guild = 3")
        self.assertEqual(rules(text, lock_of()), ["PROTO007", "PROTO007"])
        self.assertEqual(rules(EXAMPLE.replace("World = 3", "World = 3, Trade = 4"), lock_of()), [])

    def test_packet_id_reuse_after_removal(self):
        lock = lock_of()
        start = EXAMPLE.index("table C2S_MoveItem")
        end = EXAMPLE.index("// ---- 서버 → 클라이언트")
        removed = EXAMPLE[:start] + EXAMPLE[end:]
        self.assertEqual(rules(removed, lock), [])
        reused = removed + "\ntable C2S_Emote (packet_id: 1004, rate: 2) { emote_id: ushort; }\n"
        self.assertEqual(rules(reused, lock), ["PROTO003"])
        # lock을 갱신해도 예전 ID는 남아 있어야 한다
        _, schema, pk = run(removed, lock)
        self.assertEqual(cp.make_lock(schema, pk, lock)["packets"]["1004"], "Game.Protocol.C2S_MoveItem")

    def test_packet_id_change(self):
        self.assertEqual(rules(EXAMPLE.replace("packet_id: 2004", "packet_id: 2005"), lock_of()), ["PROTO003"])

    def test_missing_lock_is_info(self):
        report = run(lock_given=True)[0]
        self.assertEqual([f["rule"] for f in report["findings"]], ["PROTO010"])
        self.assertTrue(report["summary"]["passed"])


class Cli(unittest.TestCase):
    def test_lock_lifecycle_and_header(self):
        with tempfile.TemporaryDirectory() as d:
            src = os.path.join(d, "schema")
            shutil.copytree(EXAMPLE_DIR, src)
            lock, header = os.path.join(d, "protocol.lock.json"), os.path.join(d, "gen", "PacketMeta.generated.h")
            self.assertEqual(cp.main([src, "--lock", lock, "--update-lock", "--emit-header", header]), 0)
            with open(lock, encoding="utf-8") as f:
                self.assertEqual(json.load(f)["packets"]["1001"], "Game.Protocol.C2S_Move")
            with open(header, encoding="utf-8") as f:
                h = f.read()
            self.assertIn("C2S_Move = 1001,", h)
            self.assertIn('{ 1003, "C2S_Chat", true, 3 },', h)
            self.assertIn("C2S_Chat_text = 200;", h)

            # 호환을 깨는 변경은 실패하고 lock을 건드리지 않는다
            path = os.path.join(src, "game.fbs")
            with open(path, "w", encoding="utf-8") as f:
                f.write(EXAMPLE.replace("  input_flags: ubyte;\n", ""))
            before = os.path.getmtime(lock)
            self.assertEqual(cp.main([src, "--lock", lock, "--update-lock"]), 1)
            self.assertEqual(os.path.getmtime(lock), before)
        self.assertEqual(cp.main(["/nonexistent-dir"]), 2)

    @unittest.skipUnless(shutil.which("g++"), "g++ 없음")
    def test_generated_header_compiles(self):
        _, _, pk = run()
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "PacketMeta.generated.h"), "w", encoding="utf-8") as f:
                f.write(cp.emit_header(pk))
            with open(os.path.join(d, "main.cpp"), "w", encoding="utf-8") as f:
                f.write('#include "PacketMeta.generated.h"\n'
                        "static_assert(PacketMeta::Find(1003)->MaxPerSecond == 3);\n"
                        "static_assert(PacketMeta::Find(1001)->bClientToServer && !PacketMeta::Find(2001)->bClientToServer);\n"
                        "static_assert(PacketMeta::Find(9999) == nullptr);\n"
                        "static_assert(PacketMeta::MaxLen::C2S_Chat_text == 200);\n"
                        "int main() { return static_cast<int>(PacketMeta::EPacketId::C2S_Move) == 1001 ? 0 : 1; }\n")
            exe = os.path.join(d, "a.out")
            r = subprocess.run(["g++", "-std=c++17", "-Wall", "-Wextra", "-Werror", "main.cpp", "-o", exe],
                               cwd=d, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(subprocess.run([exe]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
