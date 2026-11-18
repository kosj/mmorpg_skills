"""MMORPG 서버 용량을 어림 계산한다. Unreal 없이 실행되는 순수 Python.

    python capacity_calc.py scenario.json --md report.md

설계 단계의 어림값이다. 실제 수치는 봇을 붙인 부하 테스트로 확인해야 한다.
종료 코드: 0 통과, 1 error 있음, 2 입력 문제.
"""
import argparse
import json
import math
import os
import sys

SECONDS_PER_MONTH = 30 * 24 * 3600
SEVERITY_ORDER = {"error": 0, "warning": 1, "info": 2}


def client_down_bps(visible_players, visible_npcs, r):
    payload = (visible_players * r["player_update_hz"] * r["bytes_per_player_update"]
               + visible_npcs * r["npc_update_hz"] * r["bytes_per_npc_update"])
    overhead = r["server_send_hz"] * r["packet_overhead_bytes"]
    return (payload + overhead) * 8


def client_up_bps(r):
    return r["client_send_hz"] * (r["bytes_per_client_input"] + r["packet_overhead_bytes"]) * 8


def case(players_on_server, visible_players, visible_npcs, r):
    visible_players = min(visible_players, max(players_on_server - 1, 0))
    down = client_down_bps(visible_players, visible_npcs, r)
    return {
        "players_on_server": players_on_server,
        "visible_players": visible_players,
        "visible_npcs": visible_npcs,
        "client_down_kbps": round(down / 1000, 1),
        "server_egress_mbps": round(down * players_on_server / 1e6, 2),
        "server_ingress_mbps": round(client_up_bps(r) * players_on_server / 1e6, 2),
        "entity_updates_per_sec": round(players_on_server * (visible_players * r["player_update_hz"]
                                                             + visible_npcs * r["npc_update_hz"])),
    }


def calculate(sc):
    r, aoi, budget = sc["rates"], sc["aoi"], sc.get("budget", {})
    cap = sc["players_per_server_cap"]
    ccu = sc["ccu_total"]
    servers = math.ceil(ccu / cap)
    servers_with_headroom = math.ceil(servers * (1 + sc.get("server_headroom", 0)))
    avg_players = min(cap, math.ceil(ccu / servers)) if servers else 0

    average = case(avg_players, aoi["avg_visible_players"], aoi["avg_visible_npcs"], r)
    crowd = case(cap, aoi["max_visible_players"], aoi["avg_visible_npcs"], r)
    no_aoi = case(cap, cap - 1, aoi["avg_visible_npcs"], r)

    avg_ccu = ccu * sc.get("avg_ccu_ratio", 0.5)
    # 반올림된 표시값이 아니라 원래 값으로 계산한다
    avg_down_bps = client_down_bps(average["visible_players"], average["visible_npcs"], r)
    monthly_tb = avg_down_bps / 8 * avg_ccu * SECONDS_PER_MONTH / 1e12

    findings = []

    def add(rule, severity, message):
        findings.append({"rule": rule, "severity": severity, "message": message})

    lim = budget.get("client_down_kbps_max")
    if lim and crowd["client_down_kbps"] > lim:
        add("CAP001", "error", f"밀집 상황의 클라이언트 수신량 {crowd['client_down_kbps']}kbps가 예산 {lim}kbps를 넘음")
    lim = budget.get("server_egress_mbps_max")
    if lim and crowd["server_egress_mbps"] > lim:
        add("CAP002", "warning", f"밀집 상황의 서버 송신량 {crowd['server_egress_mbps']}Mbps가 예산 {lim}Mbps를 넘음")
    if aoi["max_visible_players"] >= cap - 1:
        add("CAP003", "info", f"보이는 플레이어 상한({aoi['max_visible_players']})이 서버 정원({cap}) 이상이라 "
                              "관심 영역 상한이 전송량을 줄이지 못함")
    lim = budget.get("entity_updates_per_sec_max")
    if lim and crowd["entity_updates_per_sec"] > lim:
        add("CAP004", "warning", f"밀집 상황의 초당 갱신 {crowd['entity_updates_per_sec']:,}건이 "
                                 f"예산 {lim:,}건을 넘음. 서버 CPU 한계를 부하 테스트로 확인할 것")
    findings.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["rule"]))

    saving = (no_aoi["server_egress_mbps"] / crowd["server_egress_mbps"]) if crowd["server_egress_mbps"] else None
    summary = {
        "passed": not any(f["severity"] == "error" for f in findings),
        "ccu_total": ccu,
        "servers_needed": servers,
        "servers_with_headroom": servers_with_headroom,
        "client_up_kbps": round(client_up_bps(r) / 1000, 1),
        "monthly_egress_tb": round(monthly_tb, 2),
        "aoi_saving_ratio": round(saving, 1) if saving else None,
        "error": sum(1 for f in findings if f["severity"] == "error"),
        "warning": sum(1 for f in findings if f["severity"] == "warning"),
    }
    return {"summary": summary, "cases": {"average": average, "crowd": crowd, "no_aoi": no_aoi},
            "findings": findings}


def to_markdown(rep):
    s, c = rep["summary"], rep["cases"]
    lines = ["# 서버 용량 어림 계산", "",
             "설계 단계의 어림값이다. 부하 테스트 결과로 대체할 것.", "",
             f"- 결과: {'통과' if s['passed'] else '실패'}",
             f"- 동시 접속 {s['ccu_total']:,}명 → 서버 프로세스 {s['servers_needed']}개 "
             f"(여유분 포함 {s['servers_with_headroom']}개)",
             f"- 클라이언트 송신 {s['client_up_kbps']}kbps",
             f"- 월 송신량 약 {s['monthly_egress_tb']}TB",
             f"- 관심 영역 상한의 효과: 밀집 상황 송신량이 상한 없을 때의 1/{s['aoi_saving_ratio']}",
             "", "| 상황 | 서버 인원 | 보이는 플레이어 | 클라이언트 수신 | 서버 송신 | 초당 갱신 |",
             "|---|---|---|---|---|---|"]
    for label, key in (("평균", "average"), ("밀집", "crowd"), ("밀집, 상한 없음", "no_aoi")):
        k = c[key]
        lines.append(f"| {label} | {k['players_on_server']} | {k['visible_players']} | {k['client_down_kbps']}kbps "
                     f"| {k['server_egress_mbps']}Mbps | {k['entity_updates_per_sec']:,} |")
    if rep["findings"]:
        lines += ["", "## 지적 사항", ""]
        lines += [f"- [{f['severity']}] {f['rule']}: {f['message']}" for f in rep["findings"]]
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scenario")
    ap.add_argument("--out")
    ap.add_argument("--md")
    a = ap.parse_args(argv)
    try:
        with open(a.scenario, encoding="utf-8") as f:
            sc = json.load(f)
        rep = calculate(sc)
    except (OSError, KeyError, json.JSONDecodeError) as e:
        print(f"시나리오를 읽지 못함: {e!r}", file=sys.stderr)
        return 2
    for target, text in ((a.out, json.dumps(rep, ensure_ascii=False, indent=2)), (a.md, to_markdown(rep))):
        if target:
            os.makedirs(os.path.dirname(os.path.abspath(target)), exist_ok=True)
            with open(target, "w", encoding="utf-8") as f:
                f.write(text)
    print(json.dumps(rep["summary"], ensure_ascii=False))
    return 0 if rep["summary"]["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
