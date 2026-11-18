"""analyze_csv.py 단위 테스트: python -m unittest discover -s tests"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import analyze_csv as ac  # noqa: E402

with open(os.path.join(ROOT, "references", "perf-budget.json"), encoding="utf-8") as f:
    BUDGET = json.load(f)

HEADER = ["EVENTS", "FrameTime", "GameThreadTime", "RenderThreadTime", "GPUTime", "RHI/DrawCalls"]


def rows(n, ft=12.0, gt=6.0, rt=5.0, gpu=10.0, dc=2000, slow_every=0, slow_ft=40.0):
    out = []
    for i in range(n):
        f = slow_ft if slow_every and i % slow_every == 0 else ft
        out.append(["", str(f), str(gt), str(rt), str(gpu), str(dc)])
    # 실제 캡처처럼 끝에 헤더 반복 행과 메타데이터 행을 붙인다
    out.append(list(HEADER))
    out.append(["[Platform]", "Windows", "[HasHeaderRowAtEnd]", "1"])
    return out


def failed(report):
    return sorted(f["rule"] for f in report["findings"])


class Parsing(unittest.TestCase):
    def test_trailing_header_and_metadata_ignored(self):
        r = ac.evaluate(HEADER, rows(1000), BUDGET)
        self.assertEqual(r["summary"]["frames"], 1000 - BUDGET["warmup_frames"])

    def test_column_lookup(self):
        self.assertEqual(ac.find_column(HEADER, ["frametime"]), 1)
        self.assertEqual(ac.find_column(HEADER, ["DrawCalls"]), 5)  # Category/Name의 Name
        self.assertIsNone(ac.find_column(HEADER, ["Nope"]))

    def test_percentile_interpolates(self):
        self.assertAlmostEqual(ac.percentile([0, 10], 50), 5.0)
        self.assertAlmostEqual(ac.stat([1, 2, 3, 4], "pct_over", 2), 50.0)


class Judging(unittest.TestCase):
    def test_pass(self):
        r = ac.evaluate(HEADER, rows(1000), BUDGET)
        self.assertTrue(r["summary"]["passed"])
        self.assertAlmostEqual(r["summary"]["avg_fps"], 83.3, places=1)
        # 메모리 열이 없으므로 건너뜀(info)만 남는다
        self.assertEqual(failed(r), ["GEN001"])

    def test_slow_average_fails(self):
        r = ac.evaluate(HEADER, rows(1000, ft=20.0), BUDGET)
        self.assertFalse(r["summary"]["passed"])
        self.assertIn("PERF001", failed(r))
        self.assertIn("PERF003", failed(r))

    def test_hitches_fail_even_when_average_ok(self):
        r = ac.evaluate(HEADER, rows(1000, slow_every=50), BUDGET)  # 2%가 40ms
        f = failed(r)
        self.assertIn("PERF004", f)
        self.assertIn("PERF002", f)
        self.assertNotIn("PERF001", f)

    def test_thread_budget_is_warning_only(self):
        r = ac.evaluate(HEADER, rows(1000, gpu=15.0), BUDGET)
        self.assertTrue(r["summary"]["passed"])
        self.assertIn("PERF012", failed(r))
        self.assertEqual(r["summary"]["bottleneck"]["name"], "GPU")

    def test_too_few_frames(self):
        r = ac.evaluate(HEADER, rows(300), BUDGET)
        self.assertIn("GEN002", failed(r))

    def test_missing_column_suggests_similar(self):
        header = [h if h != "GPUTime" else "GPU/Total" for h in HEADER]
        r = ac.evaluate(header, rows(1000), BUDGET)
        msg = [f["message"] for f in r["findings"] if "PERF012" in f["message"]][0]
        self.assertIn("GPU/Total", msg)

    def test_regression_against_baseline(self):
        base = ac.evaluate(HEADER, rows(1000, ft=10.0), BUDGET)
        cur = ac.evaluate(HEADER, rows(1000, ft=12.0), BUDGET, baseline=base)
        self.assertIn("PERF900", failed(cur))
        same = ac.evaluate(HEADER, rows(1000, ft=10.5), BUDGET, baseline=base)
        self.assertNotIn("PERF900", failed(same))


class Cli(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "cap.csv")
            with open(p, "w", encoding="utf-8") as f:
                f.write(",".join(HEADER) + "\n")
                f.writelines(",".join(r) + "\n" for r in rows(1000, ft=20.0))
            budget = os.path.join(ROOT, "references", "perf-budget.json")
            md = os.path.join(d, "out", "report.md")
            code = ac.main(["--latest", d, "--budget", budget, "--md", md, "--label", "test"])
            self.assertEqual(code, 1)
            with open(md, encoding="utf-8") as f:
                self.assertIn("실패", f.read())
            self.assertEqual(ac.main([os.path.join(d, "none.csv"), "--budget", budget]), 2)


if __name__ == "__main__":
    unittest.main()
