"""LLM story summary for the simulation-map page.

Combines the user's original dialog/text with a compact simulation snapshot
(propagation graph, FORK branches, intervention hints) and asks the main LLM
to write event-specific people/relationship and two-path prediction copy.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from ..runtime import get_runtime
from ..utils.logger import get_logger
from ..utils.llm_client import clone_llm_client_with_thinking

logger = get_logger("mirofish.story_summarizer")

_MAX_INPUT = 2800
_MAX_NODES = 22
_MAX_EDGES = 22


def summarize_simulation_story(payload: Dict[str, Any]) -> Dict[str, Any]:
    snapshot = _compact_snapshot(payload)
    client = _llm_client()
    if client is None:
        raise RuntimeError("llm_unavailable")
    parsed = client.chat_json(
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)},
        ],
        temperature=0.35,
        max_tokens=1800,
    )
    return _normalize_story(parsed, snapshot)


def explain_fork_steps(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Explain each counterfactual step using original input + FORK logs."""
    snapshot = _compact_step_payload(payload)
    client = _llm_client()
    if client is None:
        raise RuntimeError("llm_unavailable")
    parsed = client.chat_json(
        messages=[
            {"role": "system", "content": _STEP_SYSTEM},
            {"role": "user", "content": json.dumps(snapshot, ensure_ascii=False)},
        ],
        temperature=0.2,
        max_tokens=2200,
    )
    return _normalize_step_explanations(parsed, snapshot)


def _compact_log(raw: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    items = raw if isinstance(raw, list) else []
    for index, item in enumerate(items[:6]):
        if not isinstance(item, dict):
            continue
        world = item.get("world_state") if isinstance(item.get("world_state"), dict) else {}
        rows.append({
            "step": item.get("step") or index + 1,
            "action": str(item.get("action") or item.get("agent_action") or "")[:160],
            "risk": world.get("posterior_risk"),
        })
    return rows


def _compact_step_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    steps_in = data.get("steps") if isinstance(data.get("steps"), list) else []
    steps = []
    for item in steps_in[:6]:
        if not isinstance(item, dict):
            continue
        steps.append({
            "step": item.get("step"),
            "name": str(item.get("name") or item.get("hopName") or "")[:16],
            "people": str(item.get("people") or "")[:48],
            "continue": str(item.get("continueAction") or "")[:120],
            "stoploss": str(item.get("stoplossAction") or "")[:120],
            "quote": str(item.get("inputQuote") or "")[:80],
        })
    return {
        "scenario": str(data.get("scenario") or "")[:40],
        "input_text": str(data.get("input_text") or "")[:_MAX_INPUT],
        "continue_name": str(data.get("continue_name") or "继续走")[:16],
        "stoploss_name": str(data.get("stoploss_name") or "及时止损")[:16],
        "branch_a": _compact_log(data.get("branch_a_log")),
        "branch_b": _compact_log(data.get("branch_b_log")),
        "steps": steps,
    }


_STEP_SYSTEM = """你是 MiroCogSec 的对照说明员。用户会给你：1) 这次输入的原文；2) 对照路径左右两侧每一步的动作（branch_a=继续走，branch_b=及时止损）；3) 六个阶段名称。
请用简体中文解释「这一次材料里」每一步具体指什么，不要空泛套模板。

要求：
- 必须结合原文里的具体话术、要求、人物或事件，点名但不要编造原文没有的人名、金额、链接。
- 诈骗六步含义：施压=用权威/时限逼迫；隔离=要求保密、切断家人或官网核验；关键操作=验证码/转账/点链接/屏幕共享；加码=已经配合后继续加码；不可逆=资金或凭证可能已出去；事后=对照整理还能核对的证据。
- 舆情/事件六步对齐跳数：源头、第一跳、扩散、更远接收。点名 steps.people 里出现的人。
- 每一步都要写：这一步在这次材料里是什么；原文依据（没有就写没有单独抽到原句）；继续走会怎样；及时止损会怎样。
- 禁止写 OASIS、Gemma、API、模型名、Fork 英文、函数名、snake_case。

输出严格 JSON：
{
  "steps": [
    {
      "step": 1,
      "meaning": "4-7句，解释这次材料里这一步具体指什么",
      "quote": "从原文摘一句，没有则空字符串",
      "continue": "2-4句，继续走在这一步会发生什么",
      "stoploss": "2-4句，及时止损在这一步会做什么",
      "intervene": "2-3句，这时介入意味着什么"
    }
  ]
}
必须正好覆盖用户给的每一个 step 编号。
"""


def _normalize_step_explanations(parsed: Any, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    data = parsed if isinstance(parsed, dict) else {}
    raw_steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    by_step = {}
    for item in raw_steps:
        if not isinstance(item, dict):
            continue
        try:
            step = int(item.get("step"))
        except (TypeError, ValueError):
            continue
        by_step[step] = {
            "step": step,
            "meaning": str(item.get("meaning") or "").strip()[:700],
            "quote": str(item.get("quote") or "").strip()[:120],
            "continue": str(item.get("continue") or "").strip()[:400],
            "stoploss": str(item.get("stoploss") or "").strip()[:400],
            "intervene": str(item.get("intervene") or "").strip()[:400],
        }
    expected = snapshot.get("steps") if isinstance(snapshot.get("steps"), list) else []
    steps = []
    for item in expected:
        step = item.get("step")
        try:
            step = int(step)
        except (TypeError, ValueError):
            continue
        row = by_step.get(step) or {}
        meaning = str(row.get("meaning") or "").strip()
        if not meaning:
            continue
        steps.append({
            "step": step,
            "meaning": meaning,
            "quote": str(row.get("quote") or item.get("quote") or "").strip()[:120],
            "continue": str(row.get("continue") or item.get("continue") or "").strip()[:400],
            "stoploss": str(row.get("stoploss") or item.get("stoploss") or "").strip()[:400],
            "intervene": str(row.get("intervene") or "").strip()[:400],
        })
    if len(steps) < min(3, len(expected) or 3):
        raise ValueError("incomplete_step_explanations")
    return {"source": "llm", "steps": steps}


def _llm_client():
    runtime = get_runtime()
    raw = None
    getter = getattr(runtime, "get_reporter_client", None)
    if callable(getter):
        raw = getter()
    if raw is None:
        raw = runtime.get_llm_client()
    if raw is None:
        return None
    try:
        return clone_llm_client_with_thinking(raw, enable_thinking=False)
    except Exception:
        return raw


def _compact_snapshot(payload: Dict[str, Any]) -> Dict[str, Any]:
    data = payload if isinstance(payload, dict) else {}
    snapshot = data.get("snapshot") if isinstance(data.get("snapshot"), dict) else {}
    input_text = str(data.get("input_text") or snapshot.get("input_text") or "")[:_MAX_INPUT]
    nodes_in = snapshot.get("nodes") if isinstance(snapshot.get("nodes"), list) else []
    edges_in = snapshot.get("edges") if isinstance(snapshot.get("edges"), list) else []
    nodes: List[Dict[str, Any]] = []
    for item in nodes_in[:_MAX_NODES]:
        if not isinstance(item, dict):
            continue
        nodes.append({
            "label": str(item.get("label") or "")[:16],
            "hop": item.get("hop"),
            "role": str(item.get("role") or "")[:24],
            "place": str(item.get("place") or "")[:24],
            "action": str(item.get("action") or "")[:16],
            "content": str(item.get("content") or "")[:40],
        })
    edges: List[Dict[str, Any]] = []
    for item in edges_in[:_MAX_EDGES]:
        if not isinstance(item, dict):
            continue
        edges.append({
            "from": str(item.get("from") or item.get("source") or "")[:16],
            "to": str(item.get("to") or item.get("target") or "")[:16],
            "relation": str(item.get("relation") or "")[:12],
        })
    return {
        "scenario": str(data.get("scenario") or snapshot.get("scenario") or "")[:40],
        "feature_key": str(data.get("feature_key") or snapshot.get("feature_key") or "")[:32],
        "input_text": input_text,
        "agent_count": snapshot.get("agent_count"),
        "sim_note": str(snapshot.get("sim_note") or "")[:120],
        "attack_summary": str(snapshot.get("attack_summary") or "")[:280],
        "defense_summary": str(snapshot.get("defense_summary") or "")[:280],
        "interventions": [
            str(item)[:80]
            for item in (snapshot.get("interventions") or [])
            if item
        ][:4],
        "intervene_at": _compact_intervene_at(snapshot.get("intervene_at")),
        "hop_guide": _compact_hop_guide(snapshot.get("hop_guide")),
        "nodes": nodes,
        "edges": edges,
    }


def _compact_hop_guide(raw: Any) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    rows_in = data.get("rows") if isinstance(data.get("rows"), list) else []
    rows = []
    for item in rows_in[:6]:
        if not isinstance(item, dict):
            continue
        rows.append({
            "step": item.get("step"),
            "where": str(item.get("where") or "")[:32],
            "ifIntervene": str(item.get("ifIntervene") or "")[:80],
        })
    return {
        "title": str(data.get("title") or "")[:40],
        "prefer": str(data.get("prefer") or "")[:120],
        "minImpact": str(data.get("minImpact") or "")[:160],
        "maxGain": str(data.get("maxGain") or "")[:160],
        "rows": rows,
    }


def _compact_intervene_at(raw: Any) -> Dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    hop = data.get("hop")
    try:
        hop = int(hop) if hop is not None and str(hop) != "" else None
    except (TypeError, ValueError):
        hop = None
    return {
        "clock": str(data.get("clock") or "propagation_hop")[:24],
        "hop": hop,
        "hop_name": str(data.get("hop_name") or "第一跳")[:16],
        "nodes": str(data.get("nodes") or "")[:48],
        "action": str(data.get("action") or "")[:80],
        "stage": str(data.get("stage") or "")[:24],
    }


_SYSTEM = """你是 MiroCogSec 的事件说明员。用户会给你：1) 对话框里的原始材料；2) 本次仿真压缩结果（人物节点、跳数、交互、对照路径、干预）。
请只根据这些材料写一份贴合「这一次具体事件」的中文说明，不要套空泛角色模板。

必须覆盖：
- 这是什么事（用原文里的具体话题、场所、要求或话术，点名但不要编造原文没有的人名或数字）
- 哪些人/角色会有什么反应（结合节点上的转发、澄清、通报、讨论、施压等动作）
- 在哪一跳/哪个节点干预
- 干预之后的具体结果

干预时机（硬性）：
- 舆情/事件必须用 snapshot.intervene_at：写成「在{hop_name}」并点名 nodes 里的人
- hop_name 只能是：源头 / 第一跳 / 扩散 / 更远接收
- 禁止写「第4步」「第 4 步」「第四步」，除非 intervene_at.clock 是 fork_step 且明确给了 fork 步数
- 不要照抄 interventions 标题里的步数；那些标题不是传播跳数
- 没有 intervene_at 时默认写「第一跳」，不要默认第4步
- hop_guide 给出了每一步对齐星图哪一跳、在那里介入会发生什么；预测二要写清：影响最小在第一跳/源头，ΔR 最大只是最后窗口不是动手时间

输出严格 JSON：
{
  "people_title": "短标题",
  "people_body": "两到三段，每段3-5句。写人物关系与这次事件里谁对谁做了什么。",
  "futures_title": "短标题",
  "futures_lead": "一句说明这是同一起点上的两种后续，不是既成事实。",
  "prediction_one_title": "预测一的短名",
  "prediction_one_body": "6-9句。不干预/继续扩散或继续被诱导：点出具体节点、反应、可能结果。",
  "prediction_two_title": "预测二的短名",
  "prediction_two_body": "6-9句。及时干预：写清在哪个节点做什么、拦住什么、结果如何。"
}

禁止：编造原文没有的事实；写 OASIS/Gemma/API/模型名；写「轻量降级」；空泛只列角色名而不提这件事。
诈骗场景预测一=继续被诱导，预测二=及时止损。舆情/事件预测一=继续扩散，预测二=澄清或处置介入。
"""


def _rewrite_wrong_step(text: str, snapshot: Dict[str, Any]) -> str:
    intervene = snapshot.get("intervene_at") if isinstance(snapshot.get("intervene_at"), dict) else {}
    if str(intervene.get("clock") or "") == "fork_step":
        return text
    hop_name = str(intervene.get("hop_name") or "第一跳").strip() or "第一跳"
    nodes = str(intervene.get("nodes") or "").strip()
    where = f"在{hop_name}" + (f"（{nodes}）" if nodes else "")
    rewritten = re.sub(r"在第\s*[123456一二三四五六]\s*步", where, text)
    rewritten = re.sub(r"第\s*[123456一二三四五六]\s*步", hop_name, rewritten)
    return rewritten


def _normalize_story(parsed: Any, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    data = parsed if isinstance(parsed, dict) else {}
    feature = str(snapshot.get("feature_key") or "")
    one_title = "继续被诱导" if feature == "counterfactual" else "继续扩散"
    two_title = "及时止损" if feature == "counterfactual" else "澄清或处置介入"
    people_title = _rewrite_wrong_step(str(data.get("people_title") or "").strip(), snapshot)
    one_title_raw = _rewrite_wrong_step(str(data.get("prediction_one_title") or "").strip(), snapshot)
    two_title_raw = _rewrite_wrong_step(str(data.get("prediction_two_title") or "").strip(), snapshot)
    people_body = _rewrite_wrong_step(str(data.get("people_body") or "").strip(), snapshot)
    one_body = _rewrite_wrong_step(str(data.get("prediction_one_body") or "").strip(), snapshot)
    two_body = _rewrite_wrong_step(str(data.get("prediction_two_body") or "").strip(), snapshot)
    if not people_body or not one_body or not two_body:
        raise ValueError("incomplete_story")
    return {
        "source": "llm",
        "people": {
            "title": (people_title or "这次事件里谁和谁有关")[:40],
            "body": people_body[:1800],
        },
        "futures": {
            "title": str(data.get("futures_title") or "这件事接下来可能怎么走").strip()[:40],
            "lead": str(data.get("futures_lead") or "下面两条从同一起点出发，是预测而不是已经发生的事。").strip()[:160],
            "items": [
                {
                    "label": "预测一",
                    "title": (one_title_raw or one_title)[:24],
                    "body": one_body[:1200],
                },
                {
                    "label": "预测二",
                    "title": (two_title_raw or two_title)[:24],
                    "body": two_body[:1200],
                },
            ],
        },
    }
