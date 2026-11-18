"""스킬 팩 전체의 일관성을 검사한다: python check_pack.py

스킬마다: SKILL.md 형식, 본문이 가리키는 파일의 존재, 스크립트가 내는 규칙 ID가 문서에 설명되어 있는지.
팩 전체: 모든 스킬이 README와 라우터에 올라 있는지, 검사 스크립트가 파이프라인에 연결되어 있는지,
JSON 파일이 읽히는지. 종료 코드: 0 통과, 1 문제 있음.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ROUTER = "mmorpg-router"
# 판정 스크립트가 있지만 파이프라인에 넣지 않는 스킬과 그 이유
NOT_IN_PIPELINE = {
    "mmo-server-capacity": "시나리오를 주고 계산하는 도구라 통과/실패 검사가 아님",
    "mmo-ci-pipeline": "파이프라인 자신",
    "mmo-release-check": "릴리스 시점에 두 빌드의 매니페스트를 비교하는 도구. 파이프라인 보고서를 입력으로 받음",
}
RULE_ID = re.compile(r"\b([A-Z]{3,8}\d{3})\b")
FRONTMATTER = re.compile(r"---\nname: (.+)\ndescription: (.+)\n---\n")


def skills():
    return sorted(d for d in os.listdir(ROOT) if os.path.isfile(os.path.join(ROOT, d, "SKILL.md")))


def read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def check_skill(name):
    problems = []
    text = read(name, "SKILL.md")
    m = FRONTMATTER.match(text)
    if not m:
        return [f"{name}: SKILL.md의 머리말(name, description) 형식이 틀림"]
    if m.group(1) != name:
        problems.append(f"{name}: name '{m.group(1)}'이 폴더 이름과 다름")
    if len(m.group(2)) > 1024 or "<" in m.group(2) or ">" in m.group(2):
        problems.append(f"{name}: description이 1024자를 넘거나 꺾쇠를 포함함")
    if text.count("\n") > 500:
        problems.append(f"{name}: SKILL.md가 500줄을 넘음")
    for ref in sorted(set(re.findall(r"`((?:references|scripts)/[\w./-]+)`", text))):
        if not os.path.exists(os.path.join(ROOT, name, ref)):
            problems.append(f"{name}: SKILL.md가 가리키는 {ref}이(가) 없음")

    docs = text
    ref_dir = os.path.join(ROOT, name, "references")
    for dirpath, _, files in os.walk(ref_dir):
        for fn in files:
            path = os.path.join(dirpath, fn)
            if fn.endswith(".md"):
                with open(path, encoding="utf-8") as f:
                    docs += f.read()
            elif fn.endswith(".json"):
                try:
                    with open(path, encoding="utf-8") as f:
                        json.load(f)
                except ValueError as e:
                    problems.append(f"{name}: {os.path.relpath(path, ROOT)}을(를) 읽지 못함: {e}")
    documented = set(RULE_ID.findall(docs))
    script_dir = os.path.join(ROOT, name, "scripts")
    used = set()
    if os.path.isdir(script_dir):
        for fn in os.listdir(script_dir):
            if fn.endswith(".py"):
                used |= set(RULE_ID.findall(read(name, "scripts", fn)))
    for rule in sorted(used - documented):
        problems.append(f"{name}: 스크립트가 내는 규칙 {rule}이(가) 문서에 설명되어 있지 않음")
    if os.path.isdir(script_dir) and not os.path.isdir(os.path.join(ROOT, name, "tests")) \
            and any(fn.endswith(".py") for fn in os.listdir(script_dir)):
        problems.append(f"{name}: scripts는 있는데 tests가 없음")
    return problems


def check_pack():
    problems = []
    names = skills()
    for name in names:
        problems += check_skill(name)
    readme, router = read("README.md"), read(ROUTER, "SKILL.md")
    pipeline = read("mmo-ci-pipeline", "references", "pipeline.json") if "mmo-ci-pipeline" in names else ""
    for name in names:
        if f"`{name}`" not in readme:
            problems.append(f"{name}: README.md의 스킬 목록에 없음")
        if name != ROUTER and f"`{name}`" not in router:
            problems.append(f"{name}: 라우터의 안내 표에 없음")
        has_checker = os.path.isdir(os.path.join(ROOT, name, "scripts")) and os.path.isdir(os.path.join(ROOT, name, "tests"))
        if pipeline and has_checker and name not in NOT_IN_PIPELINE and f"/{name}/scripts/" not in pipeline:
            problems.append(f"{name}: 검사 스크립트가 파이프라인(pipeline.json)에 연결되어 있지 않음")
    for name in NOT_IN_PIPELINE:
        if name not in names:
            problems.append(f"check_pack.py의 예외 목록에 없는 스킬 {name}이(가) 있음")
    return names, problems


def main():
    names, problems = check_pack()
    for p in problems:
        print("문제: " + p)
    print(f"스킬 {len(names)}개 검사, 문제 {len(problems)}건")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
