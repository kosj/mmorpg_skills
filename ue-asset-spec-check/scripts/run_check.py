"""에디터 안 진입점: 수집 -> 판정 -> 보고서 저장.

MCP에서:      run_check.main(roots=["/Game/Environment/Props"])
커맨드릿에서: 환경변수 ASSET_SPEC_ROOTS="/Game/A,/Game/B", ASSET_SPEC_PATH="<spec.json>"
"""
import json
import os
import sys

import unreal

_HERE = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.join(
    unreal.Paths.project_dir(), "Skills", "ue-asset-spec-check", "scripts")
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import collect_assets  # noqa: E402
import validate  # noqa: E402


def main(roots=None, spec_path=None, limit=None, out_dir=None):
    spec_path = spec_path or os.environ.get("ASSET_SPEC_PATH") or os.path.join(
        _HERE, "..", "references", "asset-spec.json")
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    env_roots = os.environ.get("ASSET_SPEC_ROOTS")
    roots = roots or ([r.strip() for r in env_roots.split(",") if r.strip()] if env_roots else None) \
        or spec.get("roots", ["/Game"])

    facts = collect_assets.collect(roots, spec.get("exclude"), limit)
    findings = validate.validate(facts, spec)
    summary = validate.summarize(facts, findings, spec)

    out_dir = out_dir or os.path.join(unreal.Paths.project_saved_dir(), "AssetSpec")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "facts.json"), "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "findings": findings}, f, ensure_ascii=False, indent=2)
    with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
        f.write(validate.to_markdown(summary, findings))

    summary = dict(summary, roots=roots, report_dir=out_dir)
    unreal.log("[AssetSpec] " + json.dumps(summary, ensure_ascii=False))
    return summary


if __name__ == "__main__":
    result = main()
    if not result["passed"]:
        unreal.log_error("[AssetSpec] error {}건으로 실패".format(result["error"]))
