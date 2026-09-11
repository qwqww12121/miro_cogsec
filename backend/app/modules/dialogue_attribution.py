"""把一段粘贴文本切成可解释的发言归属。

一次性输入框里经常没有「受害人：」「客服：」这类标记。系统必须说明：
哪一段被当成施害者在说、有没有受害人发言、依据是什么——而不是默默把整段
都当成双方对话。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any, Dict, List


_ROLE_PREFIX = [
    (re.compile(r"^(攻击者|骗子|嫌疑人|对方|诈骗者|冒充者|客服|警官|警察|领导)[：:]"), "suspect", "命中角色前缀"),
    (re.compile(r"^(受害人|受害者|事主|用户|我方)[：:]"), "victim", "命中角色前缀"),
    (re.compile(r"^(旁观者|证人|家人|朋友)[：:]"), "witness", "命中角色前缀"),
]

_SUSPECT_CUES = (
    "我是秦始皇", "我是公安", "我是警察", "我是客服", "我是纪委",
    "打钱", "转账", "汇款", "安全账户", "验证码", "共享屏幕",
    "立即处理", "否则", "冻结", "征信异常",
)
_VICTIM_CUES = (
    "好的", "我同意", "是真的吗", "我有点怕", "我转了", "已转账",
    "我该怎么办", "能再等等吗", "我不想",
)


@dataclass
class Utterance:
    speaker: str
    speaker_label: str
    text: str
    confidence: float
    reason: str
    evidence: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AttributionResult:
    utterances: List[Utterance] = field(default_factory=list)
    victim_present: bool = False
    suspect_present: bool = False
    split_method: str = "undivided"
    summary: str = ""
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "utterances": [item.to_dict() for item in self.utterances],
            "victim_present": self.victim_present,
            "suspect_present": self.suspect_present,
            "split_method": self.split_method,
            "summary": self.summary,
            "caveats": list(self.caveats),
        }


_SPEAKER_LABEL = {
    "suspect": "疑似施害者",
    "victim": "受害人",
    "witness": "旁观者",
    "unknown": "未判定说话人",
}


def attribute_dialogue(text: str) -> AttributionResult:
    raw = (text or "").strip()
    if not raw:
        return AttributionResult(summary="输入为空，没有可切分的发言。")

    labeled = _split_labeled_lines(raw)
    if labeled:
        return labeled
    return _infer_undivided(raw)


def build_thinking_steps(
    text: str,
    attribution: AttributionResult,
    classification: Dict[str, Any],
) -> List[Dict[str, Any]]:
    utterances = attribution.utterances
    split_detail = [
        f"{item.speaker_label}：{item.text}" for item in utterances
    ] or ["未能切出独立发言。"]
    role_detail = [f"{item.speaker_label}（把握 {int(item.confidence * 100)}%）：{item.reason}" for item in utterances]
    scenario = classification.get("scenario_type") or "unknown"
    scenario_name = {
        "fraud_im": "诈骗即时通讯",
        "public_opinion": "舆情分析",
        "event_propagation": "事件传播分析",
    }.get(scenario, "尚未可靠归类")
    graph_nodes = []
    if attribution.suspect_present:
        graph_nodes.append("疑似施害者")
    if attribution.victim_present:
        graph_nodes.append("受害人")
    else:
        graph_nodes.append("受害人（本段未发言）")
    if scenario == "fraud_im":
        graph_nodes.append("身份/索财话术")
    elif scenario == "public_opinion":
        graph_nodes.append("舆论场")
    elif scenario == "event_propagation":
        graph_nodes.append("传播节点")

    live_graph = classification.get("propagation_graph") or classification.get("graph_payload") or {}
    live_nodes = live_graph.get("nodes") if isinstance(live_graph, dict) else None
    use_live_graph = scenario in {"public_opinion", "event_propagation"} and isinstance(live_nodes, list) and len(live_nodes) >= 2
    agent_count = (
        (classification.get("core_analysis") or {}).get("agent_count")
        or (live_graph.get("agent_count") if isinstance(live_graph, dict) else None)
    )
    steps = [
        {
            "id": "split",
            "title": "切分对话双方",
            "summary": attribution.summary,
            "details": split_detail,
        },
        {
            "id": "role",
            "title": "判定发言归属",
            "summary": (
                "本段出现了受害人发言。"
                if attribution.victim_present
                else "本段没有可核对的受害人发言，不能把整段默认为双方对话。"
            ),
            "details": role_detail or ["没有足够标记来区分说话人。"],
        },
        {
            "id": "scene",
            "title": "识别认知安全场景",
            "summary": f"当前更接近「{scenario_name}」。",
            "details": [
                classification.get("reason") or "依据文本中的场景线索判断。",
                classification.get("extracted_summary") or "",
            ],
        },
    ]
    if use_live_graph:
        steps.append({
            "id": "graph",
            "title": "生成传播关系骨架",
            "summary": f"已按演示规模生成 {agent_count or len(live_nodes)} 个代理节点。",
            "details": [
                f"拓扑：{(classification.get('core_analysis') or {}).get('topology_type') or live_graph.get('topology_type') or 'campus_local'}",
                f"图中展示 {len(live_nodes)} 个关键节点。",
            ],
            "graph": live_graph,
        })
        steps.append({
            "id": "next",
            "title": "下一步：进入场景分析",
            "summary": "对话层已给出关系骨架。覆盖仿真、干预对比和对照路径在场景分析页继续。",
            "details": [
                "打开「传播关系图」可查看这张代理关系。",
            ],
        })
        return steps

    preview_graph = build_preview_graph(text, attribution, classification)
    steps.append({
        "id": "graph",
        "title": "整理本轮线索",
        "summary": "先抽出本轮能站得住的节点。完整对照路径或传播关系要进入对应场景分析。",
        "details": [f"本轮节点：{' → '.join(graph_nodes)}", f"原文长度 {len(text or '')} 字。"],
        "graph": preview_graph,
    })
    if scenario == "fraud_im":
        steps.append({
            "id": "fork",
            "title": "下一步：进入场景分析",
            "summary": "对话层只做场景识别。进入诈骗分析后会生成「继续被诱导 / 及时止损」对照。",
            "details": [
                "打开场景分析可查看完整证据和对照路径。",
            ],
        })
    else:
        steps.append({
            "id": "next",
            "title": "下一步：进入场景分析",
            "summary": "进入舆情或事件分析后会画出代理网络。",
            "details": ["打开场景分析可查看完整证据和传播关系。"],
        })
    return steps


def build_preview_graph(
    text: str,
    attribution: AttributionResult | Dict[str, Any],
    classification: Dict[str, Any],
) -> Dict[str, Any]:
    """给对话层用的中文线索图。舆情/事件优先使用真实代理关系，不再画示意星图。"""
    live = classification.get("propagation_graph") or classification.get("graph_payload")
    if isinstance(live, dict) and len(live.get("nodes") or []) >= 2 and live.get("source") in {
        "lightweight_propagation", "oasis",
    }:
        return live
    if hasattr(attribution, "to_dict"):
        payload = attribution.to_dict()
    else:
        payload = dict(attribution or {})
    utterances = list(payload.get("utterances") or [])
    scenario = classification.get("scenario_type") or classification.get("scenario") or "unknown"
    scenario_name = {
        "fraud_im": "诈骗即时通讯",
        "public_opinion": "舆情分析",
        "event_propagation": "事件传播分析",
    }.get(scenario, "待澄清场景")
    raw_excerpt = " ".join((text or "").split())
    excerpt = f"{raw_excerpt[:16]}…" if len(raw_excerpt) > 16 else (raw_excerpt or "原文")

    nodes: List[Dict[str, Any]] = [
        {"id": "input", "label": "输入材料", "desc": f"{excerpt}…", "kind": "input", "source": "原文可见"},
    ]
    edges: List[Dict[str, Any]] = []
    last_id = "input"
    for index, item in enumerate(utterances[:4]):
        node_id = f"发言{index + 1}"
        nodes.append({
            "id": node_id,
            "label": item.get("speaker_label") or "未判定说话人",
            "desc": str(item.get("text") or "")[:18],
            "kind": "evidence" if item.get("speaker") == "suspect" else (
                "profile" if item.get("speaker") == "victim" else "result"
            ),
            "source": "原文可见",
        })
        edges.append({"source": last_id, "target": node_id, "relation": "切分发言"})
        last_id = node_id
    if not payload.get("victim_present"):
        nodes.append({
            "id": "受害人空位",
            "label": "受害人（未发言）",
            "desc": "原文没有可核对的原话",
            "kind": "risk",
            "source": "判定说明",
        })
        edges.append({"source": last_id, "target": "受害人空位", "relation": "未见应答"})
        last_id = "受害人空位"
    nodes.append({
        "id": "场景判断",
        "label": scenario_name,
        "desc": str(classification.get("extracted_summary") or classification.get("reason") or "")[:18],
        "kind": "result",
        "source": "场景识别",
    })
    edges.append({"source": last_id, "target": "场景判断", "relation": "识别场景"})
    nodes.append({
        "id": "专业视图",
        "label": "场景分析",
        "desc": "条目式证据与建议",
        "kind": "action",
        "source": "下一层",
    })
    edges.append({"source": "场景判断", "target": "专业视图", "relation": "进入分析"})
    return {"nodes": nodes, "edges": edges, "directed": True, "source": "clue"}


def _split_labeled_lines(text: str) -> AttributionResult | None:
    utterances: List[Utterance] = []
    for raw_line in re.split(r"[\n\r]+", text):
        line = raw_line.strip()
        if not line:
            continue
        matched = False
        for pattern, speaker, why in _ROLE_PREFIX:
            hit = pattern.match(line)
            if not hit:
                continue
            body = pattern.sub("", line).strip()
            utterances.append(Utterance(
                speaker=speaker,
                speaker_label=_SPEAKER_LABEL[speaker],
                text=body or line,
                confidence=0.92,
                reason=f"{why}「{hit.group(1)}」，因此按标记切分，而不是猜测语气。",
                evidence=hit.group(1),
            ))
            matched = True
            break
        if not matched and utterances:
            # Continuation of the previous speaker.
            prev = utterances[-1]
            prev.text = f"{prev.text}\n{line}".strip()
        elif not matched:
            return None
    if not utterances:
        return None
    return _finalize(utterances, "role_prefix", "按角色前缀切分了对话。")


def _infer_undivided(text: str) -> AttributionResult:
    compact = re.sub(r"\s+", "", text)
    suspect_hits = [cue for cue in _SUSPECT_CUES if cue in compact]
    victim_hits = [cue for cue in _VICTIM_CUES if cue in compact]
    has_second_voice = bool(re.search(r"[？?].+[\n]|是真的吗|我同意|好的，", text))

    if suspect_hits and not victim_hits and not has_second_voice:
        reason = (
            "原文没有「受害人：」之类标记，也没有应答、追问或同意的痕迹；"
            f"同时出现了施害话术线索（{ '、'.join(suspect_hits[:3]) }），"
            "因此整段只记为疑似施害者单方发言。"
        )
        utterances = [Utterance(
            speaker="suspect",
            speaker_label=_SPEAKER_LABEL["suspect"],
            text=text,
            confidence=0.86 if len(suspect_hits) > 1 else 0.78,
            reason=reason,
            evidence="、".join(suspect_hits[:4]),
        )]
        return _finalize(
            utterances,
            "suspect_only",
            "没有切出第二说话人。受害人在本段没有说话。",
            extra_caveats=["未观察到受害人原话，分析时不会把沉默编成受害人已经配合。"],
        )

    if victim_hits and suspect_hits:
        utterances = [Utterance(
            speaker="unknown",
            speaker_label=_SPEAKER_LABEL["unknown"],
            text=text,
            confidence=0.55,
            reason="同时出现施害话术和疑似受害人应答，但没有角色前缀，无法可靠拆成两轮。",
            evidence="、".join((suspect_hits + victim_hits)[:4]),
        )]
        return _finalize(utterances, "mixed_unlabeled", "可能含双方内容，但缺少明确切分标记。")

    utterances = [Utterance(
        speaker="unknown",
        speaker_label=_SPEAKER_LABEL["unknown"],
        text=text,
        confidence=0.4,
        reason="没有角色前缀，也没有足够的单方话术标记，先整段保留，不强行分配说话人。",
    )]
    return _finalize(utterances, "undivided", "按整段保留，等待更多上下文后再切分。")


def _finalize(
    utterances: List[Utterance],
    method: str,
    summary: str,
    extra_caveats: List[str] | None = None,
) -> AttributionResult:
    victim_present = any(item.speaker == "victim" for item in utterances)
    suspect_present = any(item.speaker == "suspect" for item in utterances)
    caveats = list(extra_caveats or [])
    if not victim_present:
        caveats.append("受害人原话缺失：不能把系统推断写成受害人已经开口。")
    return AttributionResult(
        utterances=utterances,
        victim_present=victim_present,
        suspect_present=suspect_present,
        split_method=method,
        summary=summary,
        caveats=caveats,
    )
