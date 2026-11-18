"""팩 안 모든 스킬의 단위 테스트와 팩 일관성 검사를 실행한다: python run_tests.py"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    failed = []
    for name in sorted(os.listdir(ROOT)):
        tests = os.path.join(ROOT, name, "tests")
        if not os.path.isdir(tests):
            continue
        print(f"== {name}")
        code = subprocess.call([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
                               cwd=os.path.join(ROOT, name), stdout=subprocess.DEVNULL)
        if code != 0:
            failed.append(name)
    print("== 팩 일관성 (check_pack.py)")
    if subprocess.call([sys.executable, os.path.join(ROOT, "check_pack.py")]) != 0:
        failed.append("check_pack")
    print("실패: " + ", ".join(failed) if failed else "모두 통과")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
