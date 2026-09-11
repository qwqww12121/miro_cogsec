"""Grounded final-answer policy for the CogSec runtime.

The simulation and analysis layers produce facts and candidate actions.  This
module owns only the last mile: turning the canonical ``ReportState`` into a
helpful answer.  It deliberately has no access to benchmark gold, benchmark
predictions, or scorer output.

An LLM-backed reporter is preferred when a configured client is available.
It returns a dual-view answer in one call: ``assistant_message`` (the
professional answer, unchanged contract) plus ``plain_view`` (a full LLM
*translation* of the same content into everyday language for non-expert
users -- same coverage, not a shorter summary) and ``most_important_action``
(one fixed-field key action).  When the plain view is missing or fails
validation it degrades to None and the frontend falls back to local
assembly; the professional answer is never retried for the plain view's
sake alone.  The existing deterministic renderer remains the offline/error
fallback.  A fine-tuned local model can implement the same client contract,
so changing the reporter does not create a second public API.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Any, Callable, Dict, Mapping, Optional

from .opinion_shaping import looks_like_opinion_shaping, shaping_plain_answer
from .platform_context import detect_platform
from ..utils.logger import get_logger

logger = get_logger("mirofish.reporter_policy")


REPORTER_PROMPT_VERSION = "grounded_natural_reporter_v3_dualview"
REPORTER_SCHEMA_VERSION = "reporter_policy.v2"
REPORTER_MODES = {
    "auto", "deterministic", "main_llm", "remote_model", "dedicated_llm",
    "local_model", "trained_policy",
}


@dataclass(frozen=True)
class ReporterPreferenceWeights:
    """Priorities shared by prompt-only and future learned reporters.

    These are transparent defaults, not learned parameters and not a reward
    model.  They make the intended multi-objective boundary explicit.
    """

    grounding: float = 1.0
    actionability: float = 0.95
    specificity: float = 0.90
    mechanism_clarity: float = 0.80
    naturalness: float = 0.80
    concision: float = 0.55

    def to_dict(self) -> Dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class ReporterPolicyResult:
    assistant_message: str
    provenance: Dict[str, Any]
    # Dual-view output: plain_view is a full LLM *translation* of the
    # professional answer for non-expert users (same coverage, everyday
    # language) -- deliberately NOT a shorter summary.  None means the LLM
    # path did not run or the plain view failed validation; the frontend then
    # falls back to its local assembly.
    plain_view: Optional[str] = None
    most_important_action: Optional[str] = None


def normalize_reporter_mode(value: Any) -> str:
    mode = str(value or "auto").strip().lower()
    return mode if mode in REPORTER_MODES else "auto"


def generate_reporter_answer(
    *,
    report_state: Mapping[str, Any],
    response_plan: Mapping[str, Any],
    user_message: str,
    tone: str,
    deterministic_fallback: Callable[[], str],
    mode: str = "auto",
    client: Any = None,
    checkpoint_path: Optional[str] = None,
    preference_weights: Optional[ReporterPreferenceWeights] = None,
    max_tokens: int = 1400,
) -> ReporterPolicyResult:
    """Generate one canonical user answer and expose honest provenance."""
    selected_mode = normalize_reporter_mode(mode)
    weights = preference_weights or ReporterPreferenceWeights()
    constraints = _reporter_constraints(report_state, user_message)
    effective_fallback = deterministic_fallback
    if constraints["low_risk_fraud"]:
        effective_fallback = lambda: _low_risk_fraud_answer(report_state, user_message)
    elif constraints["proxy_only"] and str(report_state.get("scenario") or "") == "event_propagation":
        effective_fallback = lambda: _proxy_event_answer(report_state, user_message)
    base = {
        "policy_mode": selected_mode,
        "backend": "deterministic",
        "model": None,
        "prompt_version": REPORTER_PROMPT_VERSION,
        "schema_version": REPORTER_SCHEMA_VERSION,
        "llm_attempted": False,
        "retry_count": 0,
        "fallback_used": False,
        "fallback_reason": None,
        "guardrail_applied": False,
        "guardrail_reason": None,
        "trained_policy_used": False,
        "checkpoint_path": checkpoint_path,
        "preference_weights": weights.to_dict(),
        "preference_weights_source": "fixed_untrained",
        "plain_view_generated": False,
        "plain_view_source": None,
    }

    direct = report_state.get("direct_llm") if isinstance(report_state, Mapping) else None
    direct_answer = direct.get("assistant_message") if isinstance(direct, Mapping) else None
    if report_state.get("is_direct_llm_baseline") and _valid_text(direct_answer):
        return ReporterPolicyResult(
            assistant_message=str(direct_answer).strip(),
            provenance={
                **base,
                "policy_mode": "direct_llm_passthrough",
                "backend": "main_llm",
                "model": _model_name(client),
                "llm_attempted": True,
            },
        )

    if constraints["low_risk_fraud"]:
        guardrail_text = _low_risk_fraud_answer(report_state, user_message)
        return ReporterPolicyResult(
            assistant_message=guardrail_text,
            plain_view=guardrail_text,
            provenance={
                **base,
                "policy_mode": "risk_guardrail",
                "backend": "deterministic_guardrail",
                "guardrail_applied": True,
                "guardrail_reason": "low_risk_without_observed_attack_transition",
                "plain_view_generated": True,
                "plain_view_source": "guardrail",
            },
        )

    if constraints["explicit_no_distortion"] and str(report_state.get("scenario") or "") == "event_propagation":
        guardrail_text = _no_distortion_event_answer(report_state, user_message)
        return ReporterPolicyResult(
            assistant_message=guardrail_text,
            plain_view=guardrail_text,
            provenance={
                **base,
                "policy_mode": "evidence_guardrail",
                "backend": "deterministic_guardrail",
                "guardrail_applied": True,
                "guardrail_reason": "explicit_observation_overrides_proxy_simulation",
                "plain_view_generated": True,
                "plain_view_source": "guardrail",
            },
        )

    if constraints["explicit_stable_public"]:
        guardrail_text = _stable_public_answer(report_state, user_message)
        return ReporterPolicyResult(
            assistant_message=guardrail_text,
            plain_view=guardrail_text,
            provenance={
                **base,
                "policy_mode": "evidence_guardrail",
                "backend": "deterministic_guardrail",
                "guardrail_applied": True,
                "guardrail_reason": "explicit_stability_evidence_overrides_proxy_signal",
                "plain_view_generated": True,
                "plain_view_source": "guardrail",
            },
        )

    if constraints["opinion_shaping"]:
        guardrail_text = shaping_plain_answer(detect_platform(user_message or ""))
        return ReporterPolicyResult(
            assistant_message=guardrail_text,
            plain_view=guardrail_text,
            provenance={
                **base,
                "policy_mode": "evidence_guardrail",
                "backend": "deterministic_guardrail",
                "guardrail_applied": True,
                "guardrail_reason": "opinion_shaping_playbook",
                "plain_view_generated": True,
                "plain_view_source": "guardrail",
            },
        )

    if selected_mode == "deterministic":
        return ReporterPolicyResult(
            assistant_message=effective_fallback(),
            provenance=base,
        )

    if selected_mode == "trained_policy" and not checkpoint_path:
        return _fallback(
            effective_fallback,
            base,
            "trained_reporter_checkpoint_missing",
        )

    if client is None:
        return _fallback(
            effective_fallback,
            base,
            "reporter_client_unavailable",
        )

    payload = _bounded_payload(
        report_state=report_state,
        response_plan=response_plan,
        user_message=user_message,
        tone=tone,
        preference_weights=weights,
    )
    messages = _messages(payload)
    provenance = {
        **base,
        "backend": _backend_name(selected_mode, client),
        "model": _model_name(client),
        "llm_attempted": True,
        "trained_policy_used": selected_mode == "trained_policy",
    }

    last_reason = "unknown_reporter_error"
    for attempt in range(2):
        try:
            attempt_max_tokens = max(256, int(max_tokens)) + (400 * attempt)
            parsed = _structured_answer(
                client,
                messages,
                temperature=0.35 if attempt == 0 else 0.15,
                max_tokens=attempt_max_tokens,
                json_mode=(attempt > 0),
            )
            cleaned = _clean_text(parsed.get("professional_message"))
            plain_text = _clean_text(parsed.get("plain_view"))
            key_action = _clean_text(parsed.get("most_important_action"))
            response_meta = _response_metadata(client)
            provenance["finish_reason"] = response_meta.get("finish_reason")
            provenance["completion_tokens"] = response_meta.get("completion_tokens")
            provenance["response_model"] = response_meta.get("model")
            valid, reason = validate_reporter_text(
                cleaned,
                finish_reason=response_meta.get("finish_reason"),
                report_state=report_state,
                user_message=user_message,
            )
            if valid:
                provenance["retry_count"] = attempt
                # Dual-view degradation contract (agreed): the professional
                # message is the primary output.  A missing/invalid plain view
                # never triggers a retry -- it degrades to None and the
                # frontend falls back to its local assembly.
                plain_ok, plain_reason = validate_plain_view(
                    plain_text,
                    finish_reason=response_meta.get("finish_reason"),
                    report_state=report_state,
                    user_message=user_message,
                )
                if not plain_ok:
                    plain_text = None
                    provenance["plain_view_reason"] = plain_reason
                if not (8 <= len(key_action) <= 200):
                    key_action = None
                provenance["plain_view_generated"] = plain_text is not None
                provenance["plain_view_source"] = "llm" if plain_text is not None else None
                return ReporterPolicyResult(
                    cleaned,
                    provenance,
                    plain_view=plain_text,
                    most_important_action=key_action,
                )
            last_reason = reason or "reporter_output_invalid"
            retry_direction = (
                "必须明确当前证据不足以判定诈骗，不得出现诈骗、骗局、转账、账号资料或验证码等原文没有的情节。"
                if last_reason in {"low_risk_overclaim", "ungrounded_downstream_risk"}
                else ""
            )
            messages = [
                *messages,
                {"role": "assistant", "content": json.dumps(parsed, ensure_ascii=False)},
                {
                    "role": "user",
                    "content": (
                        "上一个回答的 professional_message 未通过最终文本检查（原因："
                        f"{last_reason}）。请重新输出完整的 JSON 对象（包含 "
                        "professional_message、plain_view、most_important_action 三个字段）；"
                        f"professional_message 中不要输出 JSON、代码块、内部字段名或重复段落。{retry_direction}"
                    ),
                },
            ]
        except Exception as exc:  # the deterministic path must remain available
            last_reason = f"reporter_call_failed:{type(exc).__name__}"

    provenance["retry_count"] = 1
    return _fallback(effective_fallback, provenance, last_reason)


def validate_reporter_text(
    value: Any,
    *,
    finish_reason: Optional[str] = None,
    report_state: Optional[Mapping[str, Any]] = None,
    user_message: str = "",
    min_chars: int = 12,
) -> tuple[bool, Optional[str]]:
    """Reject transport/format failures without pretending to fact-check an LLM."""
    if not _valid_text(value, min_chars=min_chars):
        return False, "empty_or_too_short"
    text = str(value).strip()
    if str(finish_reason or "").lower() in {"length", "max_tokens"}:
        return False, "answer_truncated"
    if len(text) > 5000:
        return False, "answer_too_long"
    if "```" in text or _looks_like_json(text):
        return False, "machine_format_leaked"
    forbidden = (
        "benchmark_prediction",
        "benchmark gold",
        "report_state",
        "source_contract",
        "candidate_id",
        "metric_source",
        "score_lineage",
    )
    lowered = text.lower()
    if any(token in lowered for token in forbidden):
        return False, "internal_field_leaked"
    internal_action_tokens = (
        "identity_asset_exchange", "private_contact_lure", "transfer_money",
        "request_verification_code", "apply_urgency", "bind_correction",
    )
    if any(token in lowered for token in internal_action_tokens):
        return False, "internal_action_token_leaked"
    unsupported_promises = ("我们将持续关注", "我们会持续关注", "我们将继续跟进", "我们会继续跟进")
    if any(token in text for token in unsupported_promises):
        return False, "unsupported_followup_promise"
    constraints = _reporter_constraints(report_state or {}, user_message)
    if constraints["low_risk_fraud"]:
        if any(token in text for token in ("诈骗", "骗局", "欺诈")):
            return False, "low_risk_overclaim"
        grounding = constraints["grounding_text"]
        downstream = ("转账", "付款", "交付资金", "账号资料", "验证码", "安全账户")
        if any(token in text and token not in grounding for token in downstream):
            return False, "ungrounded_downstream_risk"
    if constraints["proxy_only"]:
        if re.search(r"\b(?:SYNTH|INFERRED|ACTOR|CLAIM)_\d+\b", text, re.IGNORECASE):
            return False, "synthetic_identifier_leaked"
        if re.search(r"(?:保真度|完整性|确信度|失真率)[^。；\n]{0,20}\d+\.\d+", text):
            return False, "proxy_metric_presented_as_observation"
    if constraints["explicit_no_distortion"] and any(
        token in text for token in ("严重失真", "显著失真", "内容完整性正在显著下降", "保真度急剧下降")
    ):
        return False, "contradicts_observed_evidence"
    lines = [re.sub(r"\s+", "", item) for item in text.splitlines() if item.strip()]
    if len(lines) != len(set(lines)):
        return False, "repeated_lines"
    return True, None


def validate_plain_view(
    value: Any,
    *,
    finish_reason: Optional[str] = None,
    report_state: Optional[Mapping[str, Any]] = None,
    user_message: str = "",
) -> tuple[bool, Optional[str]]:
    """Validate the plain-view translation.

    Applies the same grounding/safety guardrails as the professional answer
    (a simpler wording must never become a loophole for overclaiming or
    leaking internal fields), plus a stricter minimum length: a real
    *translation* keeps the professional answer's coverage, so a very short
    plain view is treated as a degraded summary rather than a translation.
    """
    return validate_reporter_text(
        value,
        finish_reason=finish_reason,
        report_state=report_state,
        user_message=user_message,
        min_chars=100,
    )


def _structured_answer(
    client: Any,
    messages: list[Dict[str, str]],
    *,
    temperature: float,
    max_tokens: int,
    json_mode: bool = False,
) -> Dict[str, Any]:
    """Call the client once and return the parsed dual-view JSON object.

    Default mode is plain ``chat`` + tolerant parsing: on DeepSeek-style
    providers, ``json_object`` constrained decoding combined with larger
    propagation payloads sent the model into a reasoning loop that consumed
    the whole token budget and returned empty content at
    ``finish_reason=length``.  ``json_mode`` (used for the second attempt)
    switches to ``chat_json`` when available: the two modes have
    complementary failure modes on reasoning-style providers, so alternating
    them makes the 2-attempt loop more robust.  The system prompt already
    demands a bare JSON object (and contains the word "JSON", which some
    providers require before accepting ``response_format``).
    """
    if json_mode and hasattr(client, "chat_json"):
        result = client.chat_json(messages, temperature=temperature, max_tokens=max_tokens)
        if not isinstance(result, dict) or not result:
            logger.warning(
                "reporter chat_json returned no usable object; meta=%s",
                dict(getattr(client, "last_response_metadata", {}) or {}),
            )
        return result if isinstance(result, dict) and result else _parse_json_object(str(result or ""))
    content = _clean_text(client.chat(messages, temperature=temperature, max_tokens=max_tokens))
    if not content:
        logger.warning(
            "reporter chat returned empty content; meta=%s",
            dict(getattr(client, "last_response_metadata", {}) or {}),
        )
    return _parse_json_object(content)


def _parse_json_object(text: str) -> Dict[str, Any]:
    """Tolerantly parse a JSON object out of an LLM answer, or raise ValueError."""
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", str(text or "").strip(), flags=re.IGNORECASE).strip()
    try:
        parsed = json.loads(cleaned)
    except (TypeError, ValueError, json.JSONDecodeError):
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end <= start:
            logger.warning(
                "reporter answer is not JSON (len=%d): %.300r", len(cleaned), cleaned
            )
            raise ValueError("reporter_answer_not_json")
        try:
            parsed = json.loads(cleaned[start : end + 1])
        except (TypeError, ValueError, json.JSONDecodeError):
            # Truncated JSON (finish_reason=length) or prose-wrapped output.
            logger.warning(
                "reporter JSON unparseable after brace-slice (len=%d): %.300r",
                len(cleaned), cleaned,
            )
            raise ValueError("reporter_answer_not_json")
    if not isinstance(parsed, dict):
        logger.warning("reporter answer parsed to non-dict: %s", type(parsed).__name__)
        raise ValueError("reporter_answer_not_json_object")
    return parsed


def _messages(payload: Dict[str, Any]) -> list[Dict[str, str]]:
    system_prompt = """你是 Miro-CogSec 的最终回答者。上游多智能体、风险图和反事实模块已经完成分析；你的职责是把给定状态写成对当前用户真正有用的中文回答，不重新猜测事实。

你需要在一次输出中同时给出两个版本的同一条回答：专业版（professional_message）和通俗版（plain_view），外加一条最关键行动建议（most_important_action）。输出为一个 JSON 对象，恰好包含这三个字段。

两个版本共用的事实与安全规则（规则 1-11）：
1. 只使用输入状态中的事实、证据、机制和动作，不补充未提供的人名、号码、机构结论或统计值。
2. 先直接回答风险/传播问题，再解释最关键的原文证据与机制，最后给出可执行动作。动作尽量包含行动人、对象、时机和做法。
3. 区分原文事实、模型推断和代理仿真；provenance 为 proxy/heuristic 时，不把效果写成真实观测或确定结论。不要在回答里提及 OASIS、FORK 等内部模块名，也勿解释某模块“未调用/未接入”。
4. 信息不足时明确说缺什么。不要为了显得完整而编造。
5. 使用自然、具体、面向人的表达。不要泄露字段名、内部 Agent 名、benchmark、分数优化、JSON 或代码块。
6. 不强制固定标题。可按内容使用短段落或少量项目符号；避免每个案例都输出同一套句式，避免重复证据和抽象术语堆叠。
7. 不模仿任何参考答案，不追求关键词重合。优先保证证据可信、建议可执行、表述清楚。
8. 不要把"接下来可能怎样"写成已发生事实；若状态没有给出，不推测对方会索要哪些额外信息。
9. 不承诺"持续关注、继续跟进或提供后续支持"，除非输入状态明确提供了该服务能力。
10. evidence_priority 中的原文陈述高于代理仿真。若原文明确说"未出现误传/失真"，不得用代理仿真反驳它；只能说明仍可监测哪些变化。
11. 当 safety_constraints.low_risk_fraud=true 时，不得直接定性为诈骗，也不得虚构后续转账、账号、验证码等情节；应明确当前证据不足，并给出与风险相称的核验建议。

【professional_message 字段】面向安全分析与运营人员。遵循规则 1-11，控制在 180 至 600 个汉字内，以完整句子结束。

【plain_view 字段】面向完全没有安全和技术背景的普通用户（例如接到可疑电话的长辈）。它和 professional_message 是同一内容的两种说法，遵循规则 1-11 的全部事实与安全约束，但表达方式完全不同。最重要的要求--它是"转译"，不是"摘要"：

A. 覆盖面必须与 professional_message 一致，四块内容一样都不能少：
   ① 现在的风险是什么、有多紧急；
   ② 为什么危险--对方在用什么手法、在利用人的什么心理（对应专业版中的攻击策略与认知弱点分析）；
   ③ 如果继续下去会发生什么、现在停下来能避免什么（对应反事实推演结论）；
   ④ 具体该怎么办（对应全部干预建议，不只是第一条）。
   篇幅不设"越短越好"的目标：专业版需要多少字讲清楚，通俗版就用多少字讲清楚，不许通过删减内容来缩短篇幅。

B. 唯一允许改变的是"怎么说"。凡专业版使用的术语和机制名词--如"认知画像""风险图谱""反事实推演/双路径推演""Cialdini 影响力原则""权威服从""损失厌恶""资产暴露""可逆性""传播仿真""干预窗口"等--不得原样出现在 plain_view 中，必须换成日常语言的解释。示例：
   - "认知画像显示权威服从维度偏高" → "对方冒充的'官方身份'对这类话术特别管用，因为人面对'警察''客服主管'时倾向于照办"
   - "反事实推演显示两条路径风险差距扩大" → "我们对比了'继续按他说的做'和'现在就停下来'这两种走向：继续下去钱大概率追不回来，现在停下几乎没有损失"
   - "干预窗口在第2-3步" → "现在停下来最来得及，再拖一两步就晚了"

C. 禁止把 plain_view 做成 professional_message 的删减版、缩句版或挑重点版。如果 plain_view 的信息量明显少于 professional_message（只保留了结论和建议、丢掉了"为什么危险"和"如果继续会怎样"的解释），即为不合格输出。

D. "通俗"不等于可以夸大或吓唬用户：不得使用"必然""肯定倾家荡产"等超出输入状态的表述。

【most_important_action 字段】一句话、一条最关键的具体行动建议，包含行动和渠道（例如"先挂断电话，联系家人或拨打110核实"）。它是 plain_view 中最重要的一条建议，不是新的建议。

输出格式：只输出一个 JSON 对象，形如
{"professional_message": "...", "plain_view": "...", "most_important_action": "..."}
不要输出 JSON 之外的任何文字、代码块标记或解释。"""
    return [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "请根据以下受限状态回答。\n" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        },
    ]


def _bounded_payload(
    *,
    report_state: Mapping[str, Any],
    response_plan: Mapping[str, Any],
    user_message: str,
    tone: str,
    preference_weights: ReporterPreferenceWeights,
) -> Dict[str, Any]:
    scenario = str(report_state.get("scenario") or "unknown")
    branch_key = {
        "fraud_im": "fraud",
        "public_opinion": "public_opinion",
        "event_propagation": "event_propagation",
    }.get(scenario)
    branch = report_state.get(branch_key, {}) if branch_key else {}
    branch = dict(branch) if isinstance(branch, Mapping) else {}
    branch.pop("provenance", None)
    provenance = report_state.get("provenance")
    provenance = dict(provenance) if isinstance(provenance, Mapping) else {}
    trusted_counterfactual = bool(provenance.get("has_oasis_counterfactual_branches"))
    constraints = _reporter_constraints(report_state, user_message)
    reported_scenario = "general_content_review" if constraints["low_risk_fraud"] else scenario
    answer_plan = {
        "conclusion": response_plan.get("conclusion"),
        "evidence": list(response_plan.get("evidence") or [])[:5],
        "mechanism": list(response_plan.get("mechanism") or [])[:5],
        "recommendations": list(response_plan.get("recommendations") or [])[:4],
    }
    if constraints["low_risk_fraud"]:
        answer_plan = {
            "conclusion": "当前材料未显示足以定性为诈骗的高风险请求。",
            "evidence": _as_list(response_plan.get("evidence") or report_state.get("evidence"))[:5],
            "mechanism": [],
            "recommendations": ["核对发布来源；仅在后续出现异常请求时升级处置。"],
        }
    return {
        "user_request": str(user_message or "")[:1200],
        "tone": tone,
        "scenario": reported_scenario,
        "summary": report_state.get("summary") or {},
        "observed_evidence": list(report_state.get("evidence") or [])[:8],
        "mechanisms": list(report_state.get("mechanisms") or [])[:6],
        "scenario_state": _bounded_scenario_state(
            scenario,
            branch,
            trusted_counterfactual=trusted_counterfactual,
        ),
        "selected_actions": _bounded_actions(
            report_state.get("selected_actions"),
            trusted_counterfactual=trusted_counterfactual,
        )[:2],
        "candidate_actions": _bounded_actions(
            report_state.get("candidate_actions"),
            trusted_counterfactual=trusted_counterfactual,
        )[:4],
        "answer_plan": answer_plan,
        "runtime_limits": {
            "metric_source": provenance.get("metric_source"),
            "counterfactual_runtime_executed": bool(provenance.get("has_counterfactual_runtime")),
            "oasis_counterfactual_executed": bool(provenance.get("has_oasis_counterfactual_branches")),
        },
        "evidence_priority": {
            "original_input_over_proxy": True,
            "explicit_no_distortion": constraints["explicit_no_distortion"],
            "synthetic_identifiers_are_not_real_accounts": True,
        },
        "safety_constraints": {
            "low_risk_fraud": constraints["low_risk_fraud"],
            "do_not_invent_downstream_requests": constraints["low_risk_fraud"],
        },
        "preference_priorities": preference_weights.to_dict(),
    }


def _reporter_constraints(
    report_state: Mapping[str, Any],
    user_message: str,
) -> Dict[str, Any]:
    scenario = str(report_state.get("scenario") or "")
    summary = report_state.get("summary")
    summary = summary if isinstance(summary, Mapping) else {}
    evidence = report_state.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    grounding_text = " ".join([str(user_message or ""), *(str(item) for item in evidence)])
    risk_level = str(summary.get("risk_level") or "").strip().lower()
    provenance = report_state.get("provenance")
    provenance = provenance if isinstance(provenance, Mapping) else {}
    metric_source = str(provenance.get("metric_source") or "").strip().lower()
    has_oasis = bool(provenance.get("has_oasis_counterfactual_branches"))
    explicit_no_distortion = any(
        token in grounding_text
        for token in ("未出现明显地点误传", "未出现明显误传", "未出现失真", "没有明显失真", "未发生明显失真")
    )
    attack_markers = (
        "转账", "汇款", "付款", "先交", "交费", "缴费", "包装费", "通道费",
        "保证金", "验证码", "密码", "安全账户", "远程控制", "共享屏幕",
        "屏幕共享", "私人微信", "添加微信", "垫付", "充值", "收款码",
        "无需征信", "保证下卡",
    )
    observed_attack_transition = any(token in grounding_text for token in attack_markers)
    stable_markers = (
        "多家可靠媒体确认", "多家媒体确认", "理性分析", "理性讨论",
        "未出现未经证实", "没有未经证实", "未出现强烈", "无强烈情绪",
        "整体平稳", "平稳有序",
    )
    explicit_stable_public = scenario == "public_opinion" and sum(
        token in grounding_text for token in stable_markers
    ) >= 2
    opinion_shaping = scenario == "public_opinion" and looks_like_opinion_shaping(grounding_text)
    return {
        "low_risk_fraud": (
            scenario == "fraud_im"
            and risk_level in {"low", "none", "minimal"}
            and not observed_attack_transition
        ),
        "proxy_only": metric_source in {"proxy", "heuristic"} and not has_oasis,
        "explicit_no_distortion": explicit_no_distortion,
        "explicit_stable_public": explicit_stable_public,
        "opinion_shaping": opinion_shaping,
        "observed_attack_transition": observed_attack_transition,
        "grounding_text": grounding_text,
    }


def _bounded_scenario_state(
    scenario: str,
    branch: Mapping[str, Any],
    *,
    trusted_counterfactual: bool,
) -> Dict[str, Any]:
    """Expose only user-facing, provenance-safe fields to the final reporter."""
    if scenario == "event_propagation":
        value: Dict[str, Any] = {
            "original_claim": branch.get("original_claim"),
            "correction_status": branch.get("correction_status") or {},
            "containment_action": branch.get("containment_action"),
            "containment_timing": _human_timing(branch.get("containment_timing")),
        }
        if trusted_counterfactual:
            value["expected_effect"] = branch.get("expected_effect") or {}
        else:
            value["simulation_scope"] = (
                "仅运行轻量代理仿真；轨迹、节点和数值不是现实观测，禁止在最终回答中引用。"
            )
        return {key: item for key, item in value.items() if item not in (None, "", {}, [])}
    if scenario == "fraud_im":
        allowed = (
            "fraud_type", "risk_level", "threat_level", "attack_stage",
            "asset_targets", "critical_transitions", "expected_warning",
            "expected_safe_action", "current_stage",
        )
        return {key: branch[key] for key in allowed if key in branch and branch[key] not in (None, "", {}, [])}
    return _remove_internal_values(branch, keep_numbers=trusted_counterfactual)


def _bounded_actions(value: Any, *, trusted_counterfactual: bool) -> list[Dict[str, Any]]:
    items = value if isinstance(value, list) else ([value] if isinstance(value, Mapping) else [])
    output: list[Dict[str, Any]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        action = item.get("action") or item.get("best_intervention_action")
        bounded: Dict[str, Any] = {}
        if action:
            bounded["action"] = str(action)
        if item.get("actor"):
            bounded["actor"] = item.get("actor")
        timing = item.get("timing") or item.get("best_intervention_window")
        timing = _human_timing(timing)
        if timing:
            bounded["timing"] = timing
        if trusted_counterfactual and item.get("expected_effect"):
            bounded["expected_effect"] = _remove_internal_values(item.get("expected_effect"), keep_numbers=True)
        if bounded:
            output.append(bounded)
    return output


def _human_timing(value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    allowed = ("open_stage", "close_stage", "label")
    return {key: value[key] for key in allowed if value.get(key) not in (None, "")}


def _remove_internal_values(value: Any, *, keep_numbers: bool) -> Any:
    blocked_keys = {
        "candidate_id", "branch_id", "node_id", "target_nodes", "mutation_steps",
        "score_breakdown", "ranking_score", "final_score", "provenance",
    }
    if isinstance(value, Mapping):
        return {
            str(key): _remove_internal_values(item, keep_numbers=keep_numbers)
            for key, item in value.items()
            if str(key) not in blocked_keys
        }
    if isinstance(value, list):
        return [_remove_internal_values(item, keep_numbers=keep_numbers) for item in value[:12]]
    if isinstance(value, str):
        if re.search(r"\b(?:SYNTH|INFERRED|ACTOR|CLAIM)_\d+\b", value, re.IGNORECASE):
            return ""
        return value
    if isinstance(value, (int, float)) and not keep_numbers:
        return None
    return value


def _low_risk_fraud_answer(report_state: Mapping[str, Any], user_message: str) -> str:
    evidence = report_state.get("evidence") or []
    if isinstance(evidence, str):
        evidence = [evidence]
    fact = str(evidence[0]).strip() if evidence else str(user_message or "").strip()
    if not fact:
        fact = "现有材料"
    fact = fact[:180]
    return (
        "从目前给出的内容看，没有足够证据把它判定为诈骗。"
        f"现有信息只是：{fact}"
        "其中没有出现转账、索要验证码、远程控制或要求脱离正规渠道等明确高风险行为。"
        "建议先核对发布来源、日期和官方联系方式，正常信息无需过度处置；"
        "如果后续出现付款、提交敏感信息或安装来历不明程序的要求，再立即停止并通过独立官方渠道核验。"
    )


def _no_distortion_event_answer(report_state: Mapping[str, Any], user_message: str) -> str:
    fact = _first_grounded_fact(report_state, user_message)
    return (
        "根据现有描述，目前没有明显的地点误传、时间误传或断章取义证据，"
        "因此不宜把它直接定性为传播失真或高风险事件。"
        f"判断依据是：{fact}"
        "当前更合适的做法是保留官方原帖作为核验基准，观察后续转发是否改动发布时间、影响区域、"
        "来源归属或防护建议；只有出现这些变化时，再对具体转发内容做标注、澄清或定向更正。"
        "轻量代理仿真只能用于提出监测方向，不能替代真实平台传播数据。"
    )


def _proxy_event_answer(report_state: Mapping[str, Any], user_message: str) -> str:
    fact = _first_grounded_fact(report_state, user_message)
    return (
        f"从现有信息看，传播判断应以这段原始事实为准：{fact}"
        "目前只有轻量代理仿真，没有真实平台传播轨迹，因此不能把模拟节点、传播数值或预估效果"
        "当作已经发生的事实。建议先核实首发来源和原始时间地点，再关注高影响力转发是否加入未经"
        "证实的判断；如发现具体误传，应把更正直接同步到原帖和主要转发链，并保留出处与仍待核实的细节。"
    )


def _stable_public_answer(report_state: Mapping[str, Any], user_message: str) -> str:
    fact = _first_grounded_fact(report_state, user_message)
    return (
        "从给出的材料看，当前舆论环境整体平稳，没有足够证据支持中高风险判断。"
        f"原文依据是：{fact}"
        "现阶段无需进行压制性干预，可保留可靠媒体和官方来源链接，按正常节奏补充后续事实。"
        "只有当新内容出现未经证实的爆料、篡改时间地点、明显断章取义或跨群体情绪动员时，"
        "再升级为事实核查、来源标注和针对具体误传的澄清。代理情绪或传播指标只能作为监测线索，不能覆盖原文事实。"
    )


def _first_grounded_fact(report_state: Mapping[str, Any], user_message: str) -> str:
    evidence = _as_list(report_state.get("evidence"))
    value = str(evidence[0]).strip() if evidence else str(user_message or "").strip()
    return (value or "现有材料未提供更多可核验细节")[:220]


def _as_list(value: Any) -> list[Any]:
    if value in (None, ""):
        return []
    return value if isinstance(value, list) else [value]


def _fallback(
    deterministic_fallback: Callable[[], str],
    provenance: Dict[str, Any],
    reason: str,
) -> ReporterPolicyResult:
    return ReporterPolicyResult(
        assistant_message=deterministic_fallback(),
        provenance={
            **provenance,
            "backend": "deterministic",
            "fallback_used": True,
            "fallback_reason": reason,
            "trained_policy_used": False,
        },
    )


def _backend_name(mode: str, client: Any) -> str:
    if mode in {"local_model", "trained_policy"}:
        return mode
    if mode in {"remote_model", "dedicated_llm"}:
        return "remote_model"
    if str(getattr(client, "mode_name", "")).startswith("local"):
        return "local_model"
    if str(getattr(client, "mode_name", "")).startswith("remote"):
        return "remote_model"
    return "main_llm"


def _response_metadata(client: Any) -> Dict[str, Any]:
    value = getattr(client, "last_response_metadata", None)
    return dict(value) if isinstance(value, Mapping) else {}


def _model_name(client: Any) -> Optional[str]:
    for key in ("model", "model_path"):
        value = getattr(client, key, None)
        if value:
            return str(value)
    return None


def _clean_text(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE).strip()
    return text


def _valid_text(value: Any, min_chars: int = 12) -> bool:
    return isinstance(value, str) and len(value.strip()) >= min_chars


def _looks_like_json(text: str) -> bool:
    stripped = text.strip()
    if not (stripped.startswith("{") and stripped.endswith("}")):
        return False
    try:
        return isinstance(json.loads(stripped), dict)
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
