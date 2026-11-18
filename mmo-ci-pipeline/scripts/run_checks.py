"""프로젝트 검사들을 한 번에 실행한다. 순수 Python.

    python run_checks.py --pipeline pipeline.json --stage precommit --git-base origin/main
    python run_checks.py --pipeline pipeline.json --stage nightly --md report.md
    python run_checks.py --pipeline pipeline.json --stage precommit --changed-files changed.txt --list

바뀐 파일 목록을 주면 관련된 검사만 돌리고, 함께 바뀌어야 하는 파일 규칙(co_change)도 본다.
각 검사의 종료 코드 약속: 0 통과, 1 실패, 그 밖은 입력 문제.
이 스크립트의 종료 코드: 0 통과, 1 실패한 검사 있음, 2 설정 문제.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

STATUS_FAIL = {"fail", "error", "missing_input", "timeout"}


def glob_to_regex(pattern):
    """`**/`는 0개 이상의 폴더, `**`는 모든 문자, `*`는 `/`를 뺀 문자, `?`는 한 글자."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("^" + "".join(out) + "$")


def matches(path, patterns):
    path = path.replace("\\", "/")
    return any(glob_to_regex(p).match(path) for p in patterns)


def expand(value, variables):
    """{이름}을 변수 값으로 바꾼다. 변수 값 안의 {이름}도 한 번 더 바꾼다."""
    def once(s):
        return re.sub(r"\{(\w+)\}", lambda m: str(variables.get(m.group(1), m.group(0))), s)
    return once(once(value))


def load_pipeline(path, overrides=None):
    with open(path, encoding="utf-8") as f:
        pipe = json.load(f)
    variables = dict(pipe.get("vars", {}))
    variables.update(overrides or {})
    ids = [c.get("id") for c in pipe.get("checks", [])]
    if len(ids) != len(set(ids)) or None in ids:
        raise ValueError("checks의 id가 없거나 중복됨")
    for c in pipe.get("checks", []):
        if not c.get("command") or not c.get("stages"):
            raise ValueError(f"검사 {c.get('id')}에 command나 stages가 없음")
    return pipe, variables


def changed_from_git(base, cwd):
    out = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=cwd, capture_output=True, text=True)
    if out.returncode != 0:
        raise ValueError("git diff 실패: " + out.stderr.strip())
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def plan(pipe, variables, stage, changed=None, only=None):
    """실행 계획을 만든다. 각 항목: {id, status: run|not_triggered|missing_input, argv, ...}"""
    items = []
    for c in pipe.get("checks", []):
        if stage != "all" and stage not in c["stages"]:
            continue
        if only and c["id"] not in only:
            continue
        item = {"id": c["id"], "title": c.get("title", c["id"]), "required": c.get("required", True),
                "argv": [expand(a, variables) for a in c["command"]],
                "timeout": c.get("timeout_sec", 600), "status": "run"}
        triggers = [expand(t, variables) for t in c.get("triggers", [])]
        if changed is not None and triggers and not any(matches(f, triggers) for f in changed):
            item["status"] = "not_triggered"
        else:
            missing = [p for p in (expand(i, variables) for i in c.get("inputs", []))
                       if not os.path.exists(os.path.join(variables.get("root", "."), p))]
            if missing:
                item["status"] = "missing_input"
                item["detail"] = "없는 입력: " + ", ".join(missing)
        items.append(item)
    return items


def check_co_change(pipe, variables, changed):
    """when_changed에 맞는 파일이 바뀌었으면 must_also_change에 맞는 파일도 바뀌어야 한다."""
    problems = []
    for rule in pipe.get("co_change", []):
        when = [expand(p, variables) for p in rule["when_changed"]]
        also = [expand(p, variables) for p in rule["must_also_change"]]
        hit = [f for f in changed if matches(f, when)]
        if hit and not any(matches(f, also) for f in changed):
            problems.append({"id": rule["id"], "status": "fail", "title": rule.get("title", rule["id"]),
                             "detail": f"{rule['message']} (바뀐 파일: {', '.join(hit[:3])}"
                                       f"{' 외' if len(hit) > 3 else ''})", "required": True, "seconds": 0})
    return problems


def run(items, cwd, python=None):
    results = []
    for item in items:
        res = {k: item[k] for k in ("id", "title", "required", "status")}
        res["detail"] = item.get("detail", "")
        res["seconds"] = 0
        if item["status"] == "run":
            argv = [python or sys.executable if a == "{python}" else a for a in item["argv"]]
            start = time.time()
            try:
                p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=item["timeout"])
                res["status"] = "pass" if p.returncode == 0 else ("fail" if p.returncode == 1 else "error")
                tail = (p.stdout.strip().splitlines() or [""])[-1] if p.returncode in (0, 1) else \
                       (p.stderr.strip().splitlines() or p.stdout.strip().splitlines() or [""])[-1]
                res["detail"] = tail[:300]
                res["exit_code"] = p.returncode
            except subprocess.TimeoutExpired:
                res["status"] = "timeout"
                res["detail"] = f"{item['timeout']}초 안에 끝나지 않음"
            except OSError as e:
                res["status"] = "error"
                res["detail"] = f"실행하지 못함: {e}"
            res["seconds"] = round(time.time() - start, 2)
        results.append(res)
    return results


def summarize(results, stage):
    failed = [r for r in results if r["status"] in STATUS_FAIL and (r["required"] or r["status"] != "missing_input")]
    counts = {}
    for r in results:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return {"passed": not failed, "stage": stage, "counts": counts, "failed": [r["id"] for r in failed],
            "seconds": round(sum(r["seconds"] for r in results), 2)}


def to_markdown(summary, results):
    label = {"pass": "통과", "fail": "실패", "error": "실행 오류", "timeout": "시간 초과",
             "missing_input": "입력 없음", "not_triggered": "해당 없음"}
    lines = ["# 검사 실행 보고서", "", f"- 결과: {'통과' if summary['passed'] else '실패'} ({summary['stage']})",
             f"- 걸린 시간: {summary['seconds']}초", "", "| 검사 | 결과 | 시간 | 내용 |", "|---|---|---|---|"]
    for r in results:
        note = "" if r["required"] or r["status"] != "missing_input" else " (선택 검사)"
        lines.append(f"| {r['title']} | {label.get(r['status'], r['status'])}{note} | {r['seconds']}s | {r['detail']} |")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pipeline", required=True)
    ap.add_argument("--stage", default="precommit", help="precommit, nightly, all 또는 pipeline에 정의한 단계 이름")
    ap.add_argument("--changed-files", help="바뀐 파일 경로가 한 줄에 하나씩 적힌 파일")
    ap.add_argument("--git-base", help="이 기준과 HEAD 사이에 바뀐 파일을 git으로 구한다")
    ap.add_argument("--only", help="쉼표로 구분한 검사 id만 실행")
    ap.add_argument("--var", action="append", default=[], help="이름=값. pipeline의 vars를 덮어쓴다")
    ap.add_argument("--list", action="store_true", help="실행하지 않고 계획만 출력")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    try:
        overrides = dict(v.split("=", 1) for v in a.var)
        pipe, variables = load_pipeline(a.pipeline, overrides)
        root = os.path.abspath(variables.get("root", "."))
        variables["root"] = root
        changed = None
        if a.changed_files:
            with open(a.changed_files, encoding="utf-8") as f:
                changed = [line.strip() for line in f if line.strip()]
        elif a.git_base:
            changed = changed_from_git(a.git_base, root)
    except (OSError, ValueError) as e:
        print(f"설정을 읽지 못함: {e}", file=sys.stderr)
        return 2

    items = plan(pipe, variables, a.stage, changed, set(a.only.split(",")) if a.only else None)
    if a.list:
        for item in items:
            print(f"{item['status']:14} {item['id']:20} {' '.join(item['argv'])}")
        return 0
    results = run(items, root)
    if changed is not None and not a.only:
        results += check_co_change(pipe, variables, changed)
    summary = summarize(results, a.stage)
    for target, text in ((a.out, json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2)),
                         (a.md, to_markdown(summary, results))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
