# -*- coding: utf-8 -*-
"""Dual-view smoke: POST /api/cogsec/analyze for all three scenarios and
inspect plain_view / most_important_action in the response.

Ad-hoc verification script for the plain-view (通俗视图) refactor; not part
of the benchmark toolchain.
"""
import json
import os
import sys
import time
import urllib.request

BASE = "http://localhost:5001/api/cogsec/analyze"

CASES = {
    "fraud_im": (
        "来电者自称公安机关民警，称你的账户涉嫌洗钱案件，要求全程保密不要告诉任何人，"
        "现在必须把资金转入安全账户接受核查，并要求开启屏幕共享配合操作，"
        "还说案子马上要冻结你所有银行卡"
    ),
    "public_opinion": (
        "[话题]某小区附近化工厂夜间排放刺鼻气体\n[样本]\n"
        "群里有人发'化工厂毒气泄漏了，已经有人晕倒送医，快跑！'，转发很快；"
        "另有居民说只是正常检修的气味；当地环保账号表示'已关注，正在核实'但一整天没有后续。"
    ),
    "event_propagation": (
        "[事件]某市地铁施工路段路面塌陷\n[起点]最早由路过网友拍照发到微博，配文'大面积塌陷砸中多辆车'\n"
        "[节点描述]本地几个大号接连转发并加上'已致多人伤亡'，随后又有账号称'官方隐瞒死亡人数'；"
        "官方通报仅说'路面沉降，无人员伤亡，施工单位正在回填'，但通报没有进入主要转发链"
    ),
}


def run(scenario: str, text: str) -> dict:
    body = json.dumps({"scenario": text, "scenario_type": scenario}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE, data=body, headers={"Content-Type": "application/json"}, method="POST")
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - started
    out_dir = os.path.join(os.path.dirname(__file__), "..", "benchmark", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"smoke_dualview_{scenario}.json")
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=1)
    return {"payload": payload, "elapsed": elapsed, "out": out_path}


def main() -> int:
    only = sys.argv[1] if len(sys.argv) > 1 else None
    failures = 0
    for scenario, text in CASES.items():
        if only and scenario != only:
            continue
        print(f"\n{'=' * 24} {scenario} {'=' * 24}", flush=True)
        try:
            result = run(scenario, text)
        except Exception as exc:  # noqa: BLE001
            print(f"REQUEST FAILED: {type(exc).__name__}: {exc}")
            failures += 1
            continue
        data = result["payload"].get("data", {})
        prov = data.get("reporter_provenance") or {}
        print(f"success={result['payload'].get('success')}  latency={result['elapsed']:.1f}s  saved={result['out']}")
        print(f"provenance: backend={prov.get('backend')} model={prov.get('model')} "
              f"plain_view_generated={prov.get('plain_view_generated')} "
              f"plain_view_source={prov.get('plain_view_source')} "
              f"plain_view_reason={prov.get('plain_view_reason')} "
              f"finish={prov.get('finish_reason')} tokens={prov.get('completion_tokens')}")
        assistant = data.get("assistant_message") or ""
        plain = data.get("plain_view") or ""
        print(f"assistant_message: {len(assistant)} chars")
        print(f"plain_view: {len(plain)} chars")
        if plain:
            print("--- plain_view 前600字 ---")
            print(plain[:600])
        action = data.get("most_important_action")
        print(f"most_important_action: {action}")
        if not plain:
            failures += 1
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
