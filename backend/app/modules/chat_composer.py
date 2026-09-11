"""对话页用的三种场景回复稿。

主对话要像正常助手一样把事情讲清楚，并且用三种场景各自的口吻各写一段。
条目式专业视图留给场景分析页，星图再下一层。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from .opinion_shaping import looks_like_opinion_shaping as _looks_like_opinion_shaping
from .platform_context import detect_platform, public_opinion_lens


_SCENE_NAME = {
    "fraud_im": "诈骗即时通讯",
    "public_opinion": "舆情分析",
    "event_propagation": "事件传播分析",
}


def compose_chat_reply(
    text: str,
    classification: Dict[str, Any],
    attribution: Any,
) -> Dict[str, Any]:
    attribution = _as_dict(attribution)
    scenario = (
        classification.get("scenario_type")
        or classification.get("scenario")
        or "unknown"
    )
    if classification.get("model") == "deterministic_guard":
        return _greeting_reply()
    if classification.get("model") == "deterministic_out_of_scope" or classification.get("recognition_status") == "out_of_scope":
        return _out_of_scope_reply(text, classification)
    if classification.get("recognition_status") == "unavailable":
        return _unavailable_reply(classification)
    if scenario == "unknown":
        # ``_triptych_reply`` already contains the dedicated unknown-scene
        # response.  Calling the removed ``_unknown_reply`` helper here made
        # every low-confidence/unknown classification fail with HTTP 500.
        return _triptych_reply(text, classification, attribution, scenario)
    return _triptych_reply(text, classification, attribution, scenario)


def _as_dict(value: Any) -> Dict[str, Any]:
    if value is None:
        return {}
    if hasattr(value, "to_dict"):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    return {}


def _greeting_reply() -> Dict[str, Any]:
    return {
        "style": "greeting",
        "lead": "你好，我是 MiroCogSec，一套面向认知安全的多智能体分析系统。",
        "paragraphs": [
            "我不是通用闲聊机器人。你可以把一段可疑对话、舆情材料或事件传播过程交给我；我会先用自然语言把判断讲清楚，再请你进入对应的场景分析和推演星图。",
            "眼下我可以帮你做三件事：识别诈骗即时通讯中的话术与脆弱点，解读公共舆情里的情绪和极化，以及把事件如何扩散画成一张可解释的中文关系星图。",
        ],
        "sections": [],
        "closing": "有什么我可以帮你的吗？可以直接打招呼，也可以把材料贴过来。",
        "show_feature_cards": True,
        "suggested_followups": ["帮我看一段可疑聊天", "这像舆情还是传播？", "先看看你的三个能力"],
        "primary_scene": "",
    }


def _triptych_reply(
    text: str,
    classification: Dict[str, Any],
    attribution: Dict[str, Any],
    scenario: str,
) -> Dict[str, Any]:
    excerpt = _excerpt(text)
    summary = classification.get("extracted_summary") or "原文里已经出现了可核对的场景线索。"
    reason = classification.get("reason") or "依据文本中的场景线索判断。"
    confidence = classification.get("confidence")
    confidence_text = (
        f"当前把握大约 {int(float(confidence) * 100)}%。"
        if _is_number(confidence)
        else "当前把握还需要更多上下文。"
    )
    if scenario == "fraud_im":
        return _fraud_conversation(text, classification, attribution, excerpt, summary, reason, confidence_text)
    if scenario == "public_opinion":
        return _opinion_conversation(text, classification, attribution, excerpt, summary, reason, confidence_text)
    if scenario == "event_propagation":
        return _event_conversation(text, classification, attribution, excerpt, summary, reason, confidence_text)

    victim_present = bool(attribution.get("victim_present"))
    lead = "我读到了你的输入，但还不能把它稳妥地只放进三个任务场景里的某一个。"
    opening = [
        f"先把原文按原样读一遍：{excerpt}",
        f"{reason} 所以我不会强行打上高把握标签，而是告诉你如果往那边看会看到什么、现在又缺什么。",
    ]
    sections = [
        _fraud_lens(text, classification, attribution, scenario, excerpt, reason),
        _opinion_lens(text, classification, attribution, scenario, excerpt, reason),
        _event_lens(text, classification, attribution, scenario, excerpt, reason),
    ]
    return {
        "style": "unknown",
        "lead": lead,
        "paragraphs": opening,
        "sections": sections,
        "closing": "可以补充对话原文、传播过程或事件细节。有什么我可以继续帮你的吗？",
        "show_feature_cards": False,
        "primary_scene": scenario,
        "suggested_followups": _followups(scenario, victim_present),
    }


def _looks_like_student(text: str) -> bool:
    return bool(re.search(r"同学|学生|奖学金|助学金|教务|大学|校园", text or ""))


def _fraud_conversation(
    text: str,
    classification: Dict[str, Any],
    attribution: Dict[str, Any],
    excerpt: str,
    summary: str,
    reason: str,
    confidence_text: str,
) -> Dict[str, Any]:
    victim_present = bool(attribution.get("victim_present"))
    fields = classification.get("extracted_fields") or {}
    identity = fields.get("suspect_identity") or "未具名身份"
    student = _looks_like_student(text)
    lead = (
        "先说结论：这很像针对在校学生的奖学金或教务诈骗，不是物流客服，也不是中老年理财套路。"
        if student
        else "先说结论：这是冲着个人来的诈骗即时通讯，不是普通通知。"
    )
    spoken = (
        "受害人已经有原话。后面要盯紧有没有验证码、转账，或被要求离开官方渠道。"
        if victim_present
        else "原文里受害人还没有开口，所以我不会编造已经答应或已经转账。分析页上的保护因子只是根据受害人背景做的先验，不是这次对话测出来的顺从度。"
    )
    paragraphs = [
        f"{summary} {confidence_text} 对方自称「{identity}」，能直接核对的句子是：「{excerpt}」。",
        spoken,
        f"{reason} 正规发放奖学金或公务通知，不会要求你私下发验证码、去支付宝搜一个认证中心，更不会禁止你问辅导员或家人。下面可以打开场景分析和星图；对话里我先把最危险的下一步拦住。",
    ]
    items = (
        [
            "不要发送任何短信验证码。",
            "不要按对方给的搜索词去填身份证、银行卡。",
            "不要交所谓验证费或转入安全账户。",
            "用学校官网或公开电话回拨教务处，不要回拨聊天里的号码。",
        ]
        if student
        else [
            "先停下来，不要转账、下载指定 App 或开屏幕共享。",
            "向家人或官方渠道核实身份，不要回拨对方给的号码。",
            "完整证据、保护因子和干预建议在场景分析页按条目展开。",
        ]
    )
    return {
        "style": "fraud_im",
        "lead": lead,
        "paragraphs": paragraphs,
        "sections": [
            {
                "heading": "现在最该做的几件事",
                "title": "现在最该做的几件事",
                "emphasis": True,
                "body": "这些比打开分析页更紧急。卡片可以随后再点。",
                "items": items,
            }
        ],
        "closing": "有什么我可以继续帮你的吗？你可以直接说自己准备怎么回复对方。",
        "show_feature_cards": False,
        "primary_scene": "fraud_im",
        "suggested_followups": _followups("fraud_im", victim_present),
    }


def _opinion_conversation(
    text: str,
    classification: Dict[str, Any],
    attribution: Dict[str, Any],
    excerpt: str,
    summary: str,
    reason: str,
    confidence_text: str,
) -> Dict[str, Any]:
    if _looks_like_opinion_shaping(text):
        platform = detect_platform(text)
        lens, recs = public_opinion_lens(platform)
        place = f"当前材料里的观察场是{platform}。" if platform else ""
        return {
            "style": "public_opinion",
            "lead": f"先说结论：{place}这不是普通吐槽，而是一份「怎么把话题做成校园舆情」的操盘说明。我不会按它去写爆款帖。",
            "paragraphs": [
                f"{summary} {confidence_text} 原文摘录：「{excerpt}」。",
                "它要求冲击力标题、暗示学校长期故意、允许没有来源的故事、用滑坡说法吓人，并指导转发到班级群和表白墙。还要求写得不像造谣，并预埋评论区话术。",
                "这些步骤的目标写得很清楚：两到三天内形成可见的校园压力。对认知安全分析来说，这就是需要拆开说明的传播操盘，而不是代写文案。",
                lens,
            ],
            "sections": [
                {
                    "heading": "一眼能看懂的步骤",
                    "title": "一眼能看懂的步骤",
                    "emphasis": True,
                    "body": "每一条都对应原文里的要求，翻译成人话。",
                    "items": [
                        "先抓标题：让人还没核对就点开。",
                        "再给现成结论：涨价被说成学校长期故意。",
                        "然后用听起来合理的故事补情绪，即使没有来源。",
                        "接着用「以后住宿费水电费也会涨」把讨论扩大。",
                        "最后教人转发到群和表白墙，并在评论区把「成本上涨」拽回「管理有问题」。",
                        *recs[:2],
                    ],
                }
            ],
            "closing": "要看条目式证据和扩散结构，进入舆情分析或打开星图。我可以继续用自然语言解释每一步，但不会代写那篇操盘文。",
            "show_feature_cards": False,
            "primary_scene": "public_opinion",
            "suggested_followups": _followups("public_opinion", False),
        }
    return {
        "style": "public_opinion",
        "lead": "先说结论：这段材料更接近公共舆情，而不是一对一诈骗对话。",
        "paragraphs": [
            f"{summary} {confidence_text}",
            f"我关心的是话题怎么被讨论、情绪往哪边走，而不是某一个人有没有把钱转出去。摘录：「{excerpt}」。",
            f"{reason} 极化、关键意见和异常账号会放到舆情分析页按条目核对；星图用来看节点关系。",
        ],
        "sections": [
            {
                "heading": "可以这样读",
                "title": "可以这样读",
                "emphasis": True,
                "body": "先把话题、事实和情绪分开，再决定转不转。",
                "items": [
                    "用一句话概括话题，不要直接复制最冲的那句。",
                    "标出哪些是能核对的事实，哪些还只是情绪。",
                    "完整条目放进舆情分析页，星图用来看谁在放大。",
                ],
            }
        ],
        "closing": "若要看条目式证据，进入舆情分析；若要看结构，打开星图。",
        "show_feature_cards": False,
        "primary_scene": "public_opinion",
        "suggested_followups": _followups("public_opinion", bool(attribution.get("victim_present"))),
    }


def _event_conversation(
    text: str,
    classification: Dict[str, Any],
    attribution: Dict[str, Any],
    excerpt: str,
    summary: str,
    reason: str,
    confidence_text: str,
) -> Dict[str, Any]:
    victim_present = bool(attribution.get("victim_present"))
    hop = "已经出现可核对的接收者应答，传播至少有了第一跳。" if victim_present else "目前只看到源头节点，第二跳还没有发生，我不会把空位画成已经传开。"
    return {
        "style": "event_propagation",
        "lead": "先说结论：这段材料更适合看成事件如何一层层传开。",
        "paragraphs": [
            f"{summary} {confidence_text}",
            f"{hop} 摘录：「{excerpt}」。",
            f"{reason} 完整路径和干预窗口进事件传播分析后再分条核对。",
        ],
        "sections": [
            {
                "heading": "传播上现在能确定的",
                "title": "传播上现在能确定的",
                "emphasis": True,
                "body": "星图会把未发言的接收者留成空位。",
                "items": ["先分清源头、中介和尚未开口的节点。", "不要把推测扩散写成已经发生的转发。"],
            }
        ],
        "closing": "若要看扩散路径，进入事件传播分析或打开星图。",
        "show_feature_cards": False,
        "primary_scene": "event_propagation",
        "suggested_followups": _followups("event_propagation", victim_present),
    }


def _fraud_lens(
    text: str,
    classification: Dict[str, Any],
    attribution: Dict[str, Any],
    scenario: str,
    excerpt: str,
    reason: str,
) -> Dict[str, Any]:
    fields = classification.get("extracted_fields") or {}
    identity = fields.get("suspect_identity") or "未具名身份"
    victim_present = bool(attribution.get("victim_present"))
    primary = scenario == "fraud_im"
    reasons = [item.get("reason") for item in attribution.get("utterances") or [] if item.get("reason")]
    body = (
        f"从即时通讯诈骗的角度看，这段材料更像一次针对个人的接触，而不是公共讨论。"
        f"原文摘录是「{excerpt}」。我把它当成「谁在对谁说话、想让对方立刻做什么」。"
        f"{'当前判断也把这一幕作为主场景。' if primary else '它不一定是主场景，但这个口吻能帮你检查有没有被私下话术牵着走。'}"
        f"{'目前还缺另一侧原话，所以分析停在已给出的这一侧，不会把缺失的发言编出来。' if not victim_present else '两侧都有原话时，后续要核对的是有没有同意、转账或交出验证码。'}"
    )
    items = [
        f"自称或暗示的身份：{identity}。",
        reasons[0] if reasons else reason,
        "完整的保护因子、话术证据和干预建议，会在诈骗即时通讯分析页按条目展开，而不是堆在这一层对话里。",
    ]
    return {
        "heading": "即时通讯诈骗视角",
        "title": "即时通讯诈骗视角",
        "emphasis": primary,
        "body": body,
        "items": [item for item in items if item],
    }


def _opinion_lens(
    text: str,
    classification: Dict[str, Any],
    attribution: Dict[str, Any],
    scenario: str,
    excerpt: str,
    reason: str,
) -> Dict[str, Any]:
    primary = scenario == "public_opinion"
    body = (
        f"从舆情分析的角度看，我关心的不是某一个人有没有把钱转出去，而是这段话会不会进入公共讨论、情绪往哪边走、有没有被围观放大。"
        f"{'当前材料更像公众讨论或舆论场，所以这一段是主视角。' if primary else '就现有原文来看，它还不太像已经形成舆论场的材料。'}"
        f"摘录仍是「{excerpt}」。如果没有转发、评论、对立阵营或公众情绪，我不会把私下试探写成已经发酵的舆情事件。"
    )
    items = [
        reason if primary else "若要按舆情来做，还需要更多公众反应样本，而不是单句索财或单方自称。",
        "极化、关键意见和异常账号，会放到舆情分析页用条目核对。",
        "若这段话随后被截图传播，再从舆情口吻重看一次会更合适。",
    ]
    return {
        "heading": "舆情分析视角",
        "title": "舆情分析视角",
        "emphasis": primary,
        "body": body,
        "items": items,
    }


def _event_lens(
    text: str,
    classification: Dict[str, Any],
    attribution: Dict[str, Any],
    scenario: str,
    excerpt: str,
    reason: str,
) -> Dict[str, Any]:
    primary = scenario == "event_propagation"
    victim_present = bool(attribution.get("victim_present"))
    hop = "已经出现可核对的接收者应答，传播至少有了第一跳。" if victim_present else "目前只看到源头节点，第二跳还没有发生。"
    body = (
        f"从事件传播的角度看，我会问：谁先说、经过哪些节点、有没有被放大。"
        f"{'当前材料更强调扩散、源头或跨平台流动，所以这一段是主视角。' if primary else '就这一段原文，传播链还很短。'}"
        f"{hop} 星图里会把「未发言的接收者」画成空位，而不是补一条假装已经发生的对话边。摘录：「{excerpt}」。"
    )
    items = [
        reason if primary else "完整路径、放大点和干预窗口，进事件传播分析后再分条核对。",
        *(list(attribution.get("caveats") or [])[:1]),
        "星图用来一次看清节点关系，而不是在对话气泡里塞一张冷冰冰的窄图。",
    ]
    return {
        "heading": "事件传播视角",
        "title": "事件传播视角",
        "emphasis": primary,
        "body": body,
        "items": [item for item in items if item],
    }


def _out_of_scope_reply(text: str, classification: Dict[str, Any]) -> Dict[str, Any]:
    excerpt = _excerpt(text)
    return {
        "style": "out_of_scope",
        "lead": "这份材料我读过了，但它不是认知安全三个任务场景里的真实事件。",
        "paragraphs": [
            classification.get("extracted_summary") or "它更像项目规划、案例集或工程文档。",
            f"摘录：「{excerpt}」。我不会把它跳进舆情分析或诈骗分析，也不会拿默认话题「某品牌虚假宣传争议」去跑一遍公式化报告。",
        ],
        "sections": [
            {
                "heading": "系统实际做了什么",
                "body": classification.get("reason") or "已排除与诈骗/舆情/传播现场无关的规划文档。",
                "items": [
                    "输入解析和文档切分已经完成。",
                    "场景判定器拒绝把它标成三个任务场景之一。",
                    "如果要分析其中某一段真实对话或舆情样本，把那一段单独贴过来即可。",
                ],
            }
        ],
        "closing": "如果你要分析的是这份文档里的某一段真实对话或舆情样本，把那一段单独贴过来。有什么我可以帮你的吗？",
        "show_feature_cards": False,
        "suggested_followups": ["介绍一下你自己", "我另外贴一段对话"],
        "primary_scene": "",
    }


def _unavailable_reply(classification: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "style": "unavailable",
        "lead": "材料已经收到，但场景识别服务现在还不能给出可靠判断。",
        "paragraphs": [
            classification.get("extracted_summary") or "本地只完成了输入解析，没有把未完成的识别伪装成结论。",
        ],
        "sections": [],
        "closing": "配置识别 API 后可以再试一次。有其他材料也可以先贴过来。",
        "show_feature_cards": False,
        "suggested_followups": ["先介绍一下你自己", "我稍后再贴材料"],
        "primary_scene": "",
    }


def _followups(scenario: str, _victim_present: bool) -> List[str]:
    questions = ["为什么这样切分发言？", "接下来我该怎么办？", "先看推演星图"]
    if scenario == "public_opinion":
        questions[1] = "这段更像情绪还是谣言？"
    if scenario == "event_propagation":
        questions[1] = "传播链现在走到哪一跳了？"
    return questions


def _excerpt(text: str, limit: int = 72) -> str:
    compact = " ".join((text or "").split())
    if not compact:
        return "（空输入）"
    return compact if len(compact) <= limit else compact[:limit] + "…"


def _is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False
