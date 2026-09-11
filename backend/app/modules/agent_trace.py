"""对话层与场景层共用的多智能体路径记录。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List


_ROLE_NAME = {
    "ingest": "输入解析器",
    "split": "发言切分器",
    "classify": "场景判定器",
    "graph": "图谱线索员",
    "fork": "FORK 推演器",
    "threat": "施害者智能体",
    "twin": "受害人孪生",
    "verifier": "核验智能体",
}


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def build_classify_trace(
    text: str,
    classification: Dict[str, Any],
    attribution: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """对话层真实调用过的角色。未运行的模块不要写入用户可见记录。"""
    scenario = classification.get("scenario_type") or "unknown"
    utterances = list(attribution.get("utterances") or [])
    events = [
        {
            "time": utc_stamp(),
            "actor": _ROLE_NAME["ingest"],
            "target": _ROLE_NAME["split"],
            "action": "提交材料",
            "content": f"收到 {len(text or '')} 字原文，开始切分。",
            "amplify": "",
        },
        {
            "time": utc_stamp(),
            "actor": _ROLE_NAME["split"],
            "target": _ROLE_NAME["classify"],
            "action": "回报切分",
            "content": attribution.get("summary") or "按原文切分发言。",
            "amplify": f"{len(utterances)} 段发言",
        },
        {
            "time": utc_stamp(),
            "actor": _ROLE_NAME["classify"],
            "target": _ROLE_NAME["graph"],
            "action": "判定场景",
            "content": classification.get("reason") or "完成场景识别。",
            "amplify": scenario,
        },
    ]
    graph = classification.get("propagation_graph") or classification.get("graph_payload") or {}
    agent_count = (classification.get("core_analysis") or {}).get("agent_count") or graph.get("agent_count")
    if scenario in {"public_opinion", "event_propagation"}:
        events.append({
            "time": utc_stamp(),
            "actor": "传播关系生成器",
            "target": "对话层",
            "action": "生成关系骨架",
            "content": f"已生成 {agent_count or len(graph.get('nodes') or [])} 个轻量传播代理。",
            "amplify": str(agent_count or ""),
        })
    else:
        events.append({
            "time": utc_stamp(),
            "actor": _ROLE_NAME["graph"],
            "target": "对话层",
            "action": "给出线索图",
            "content": "只画出本轮能站得住的节点。",
            "amplify": "",
        })
    return events


def fork_status_for_classify() -> Dict[str, Any]:
    return {
        "ran": False,
        "stage": "classify_only",
        "reason": "对话层完成场景识别。",
    }
