"""클라이언트와 서버 빌드가 같은 프로토콜, 데이터, 맵을 담고 있는지 확인한다. 순수 Python.

    python check_release.py make --name client --build 1.2.0 --protocol-version 7 \
        --schema-dir Protocol --data-dir Data/Tables --map-versions map_versions.json --out client.manifest.json
    python check_release.py compare client.manifest.json server.manifest.json \
        [--previous prev_client.manifest.json] [--pipeline-report nightly.json] --md report.md

make: 빌드에 들어가는 프로토콜 정의, 기획 데이터, 맵 버전을 해시해 매니페스트를 만든다.
compare: 클라이언트와 서버의 매니페스트를 비교하고, 이전 릴리스와 견줘 버전 올림을 확인한다.
종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import hashlib
import json
import os
import sys
from collections import Counter

SEVERITY = {"REL001": "error", "REL002": "error", "REL003": "error", "REL004": "error",
            "REL005": "error", "REL006": "error", "REL007": "error", "REL008": "warning"}
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def _file_hash(path):
    """줄 끝 차이(CRLF/LF)로 해시가 달라지지 않게 텍스트 파일은 줄 끝을 맞춰 해시한다."""
    with open(path, "rb") as f:
        data = f.read()
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def hash_dir(folder, extensions):
    """{상대 경로: 해시}. 확장자가 맞는 파일만 본다."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames.sort()
        for fn in sorted(filenames):
            if fn.lower().endswith(tuple(extensions)):
                path = os.path.join(dirpath, fn)
                out[os.path.relpath(path, folder).replace(os.sep, "/")] = _file_hash(path)
    return out


def combined(files):
    return hashlib.sha256("".join(k + v for k, v in sorted(files.items())).encode()).hexdigest()[:16]


def make(name, build, protocol_version, schema_dir, data_dir, map_versions_path):
    protocol = hash_dir(schema_dir, (".fbs", "protocol.lock.json"))
    data = hash_dir(data_dir, (".csv", ".json"))
    with open(map_versions_path, encoding="utf-8-sig") as f:
        maps = json.load(f)
    return {"format": 1, "name": name, "build": build, "protocol_version": protocol_version,
            "protocol_hash": combined(protocol), "protocol_files": protocol,
            "data_hash": combined(data), "data_files": data, "map_versions": maps}


def _diff(a, b):
    """두 {이름: 값}의 차이를 사람이 읽을 문자열 목록으로."""
    out = []
    for k in sorted(set(a) | set(b)):
        if k not in a:
            out.append(f"{k} (한쪽에만 있음)")
        elif k not in b:
            out.append(f"{k} (한쪽에만 있음)")
        elif a[k] != b[k]:
            out.append(f"{k} (내용 다름)")
    return out


def compare(client, server, previous=None, pipeline_report=None):
    findings = []

    def add(rule, message):
        findings.append({"rule": rule, "severity": SEVERITY[rule], "message": message})

    for side, m in (("클라이언트", client), ("서버", server)):
        if not isinstance(m, dict) or m.get("format") != 1 or "protocol_hash" not in m or "data_hash" not in m:
            add("REL001", f"{side} 매니페스트를 읽을 수 없음. make로 다시 만들 것")
    if findings:
        return _done(findings, client, server)

    if client["protocol_hash"] != server["protocol_hash"]:
        d = _diff(client.get("protocol_files", {}), server.get("protocol_files", {}))
        add("REL002", "프로토콜 정의가 다름: " + ", ".join(d[:5]) + (" 외" if len(d) > 5 else ""))
    if client.get("protocol_version") != server.get("protocol_version"):
        add("REL002", f"프로토콜 버전이 다름: 클라이언트 {client.get('protocol_version')}, 서버 {server.get('protocol_version')}")
    if client["data_hash"] != server["data_hash"]:
        d = _diff(client.get("data_files", {}), server.get("data_files", {}))
        add("REL003", "기획 데이터가 다름: " + ", ".join(d[:5]) + (" 외" if len(d) > 5 else ""))
    d = _diff(client.get("map_versions", {}), server.get("map_versions", {}))
    if d:
        add("REL004", "맵 버전이 다름: " + ", ".join(d[:5]) + (" 외" if len(d) > 5 else ""))

    if previous is not None:
        if not isinstance(previous, dict) or previous.get("format") != 1:
            add("REL001", "이전 릴리스 매니페스트를 읽을 수 없음")
        else:
            changed = any(previous.get(k) != client.get(k) for k in ("protocol_hash", "data_hash", "map_versions"))
            if previous.get("build") == client.get("build") and changed:
                add("REL005", f"빌드 번호가 이전 릴리스와 같은데({client.get('build')}) 내용이 다름. 빌드 번호를 올릴 것")
            if previous.get("protocol_hash") != client.get("protocol_hash") \
                    and previous.get("protocol_version") == client.get("protocol_version"):
                add("REL007", f"프로토콜 정의가 바뀌었는데 프로토콜 버전이 그대로임 ({client.get('protocol_version')}). "
                              "옛 클라이언트가 접속을 거부당하지 않고 깨진 패킷을 주고받게 됨")
            if not changed and previous.get("build") != client.get("build"):
                add("REL008", "이전 릴리스와 프로토콜, 데이터, 맵이 모두 같음. 코드만 바뀐 릴리스인지 확인")

    if pipeline_report is not None:
        summary = pipeline_report.get("summary") if isinstance(pipeline_report, dict) else None
        if not summary:
            add("REL006", "검사 파이프라인 보고서를 읽을 수 없음")
        elif not summary.get("passed"):
            add("REL006", "검사 파이프라인이 통과하지 않음: " + ", ".join(summary.get("failed", [])))
    return _done(findings, client, server)


def _done(findings, client, server):
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"]))
    by_sev = Counter(f["severity"] for f in findings)

    def brief(m):
        return {k: m.get(k) for k in ("name", "build", "protocol_version", "protocol_hash", "data_hash")} \
            if isinstance(m, dict) else None
    return {"summary": {"passed": by_sev.get("error", 0) == 0, "error": by_sev.get("error", 0),
                        "warning": by_sev.get("warning", 0), "client": brief(client), "server": brief(server)},
            "findings": findings}


def to_markdown(report):
    s = report["summary"]
    lines = ["# 릴리스 일치 검사 보고서", "", f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- error {s['error']} / warning {s['warning']}", "",
             "| | 빌드 | 프로토콜 버전 | 프로토콜 해시 | 데이터 해시 |", "|---|---|---|---|---|"]
    for label, m in (("클라이언트", s["client"]), ("서버", s["server"])):
        if m:
            lines.append(f"| {label} | {m['build']} | {m['protocol_version']} | {m['protocol_hash']} | {m['data_hash']} |")
    lines += ["", "| 심각도 | 규칙 | 내용 |", "|---|---|---|"]
    lines += [f"| {f['severity']} | {f['rule']} | {f['message']} |" for f in report["findings"]]
    return "\n".join(lines) + "\n"


def _load(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def _write(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("make")
    m.add_argument("--name", required=True)
    m.add_argument("--build", required=True)
    m.add_argument("--protocol-version", required=True, type=int)
    m.add_argument("--schema-dir", required=True)
    m.add_argument("--data-dir", required=True)
    m.add_argument("--map-versions", required=True)
    m.add_argument("--out", required=True)
    c = sub.add_parser("compare")
    c.add_argument("client")
    c.add_argument("server")
    c.add_argument("--previous")
    c.add_argument("--pipeline-report")
    c.add_argument("--out")
    c.add_argument("--md")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "make":
            for d in (a.schema_dir, a.data_dir):
                if not os.path.isdir(d):
                    raise ValueError(f"폴더 없음: {d}")
            manifest = make(a.name, a.build, a.protocol_version, a.schema_dir, a.data_dir, a.map_versions)
            _write(a.out, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({k: manifest[k] for k in ("name", "build", "protocol_version", "protocol_hash", "data_hash")},
                             ensure_ascii=False))
            return 0
        client, server = _load(a.client), _load(a.server)
        previous = _load(a.previous) if a.previous else None
        pipeline = _load(a.pipeline_report) if a.pipeline_report else None
    except (OSError, ValueError) as e:
        print(f"입력을 읽지 못함: {e}", file=sys.stderr)
        return 2
    report = compare(client, server, previous, pipeline)
    if a.out:
        _write(a.out, json.dumps(report, ensure_ascii=False, indent=2))
    if a.md:
        _write(a.md, to_markdown(report))
    print(json.dumps(report["summary"], ensure_ascii=False))
    return 0 if report["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
