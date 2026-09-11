"""CogSec 最小运行时。

只依赖 CogSec 新增模块，用于：
1. 最小脚本验证
2. 独立 Flask Demo API
3. 静态演示页面的数据供给
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from .modules import (
    AttackStrategy,
    CognitiveProfile,
    CognitiveProfileExtractor,
    CounterfactualReporter,
    FraudCase,
    PrivacySanitizer,
    RiskScorer,
    T0FastResponder,
    ThreatKnowledgeRAG,
)
from .utils import LocalGemmaClient


PROJECT_BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PROJECT_BACKEND_ROOT.parent
DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "fraud_cases.json"
DEFAULT_CHROMA_PATH = PROJECT_ROOT / "data" / "chroma_db"
DEFAULT_LOCAL_GEMMA_PATH = PROJECT_ROOT / "models" / "google--gemma-4-E2B-it"
DEFAULT_LOCAL_GEMMA_OFFLOAD_PATH = PROJECT_BACKEND_ROOT / ".cache" / "gemma_offload"

logger = logging.getLogger(__name__)


def _env_flag(name: str, default: bool = False) -> bool:
    """解析布尔环境变量。"""
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def build_demo_llm_client() -> Optional[Any]:
    """按环境变量构造最小 Demo 使用的 LLM 客户端。"""
    if not _env_flag("COGSEC_USE_LOCAL_GEMMA", default=False):
        return None

    model_path = os.environ.get("COGSEC_LOCAL_MODEL_PATH", str(DEFAULT_LOCAL_GEMMA_PATH))
    device = os.environ.get("COGSEC_LOCAL_GEMMA_DEVICE", "auto")
    torch_dtype = os.environ.get("COGSEC_LOCAL_GEMMA_DTYPE", "auto")
    max_new_tokens = int(os.environ.get("COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS", "768"))
    attn_implementation = os.environ.get("COGSEC_LOCAL_GEMMA_ATTN_IMPLEMENTATION")
    offload_folder = os.environ.get(
        "COGSEC_LOCAL_GEMMA_OFFLOAD_DIR",
        str(DEFAULT_LOCAL_GEMMA_OFFLOAD_PATH),
    )

    try:
        return LocalGemmaClient(
            model_path=model_path,
            device=device,
            torch_dtype=torch_dtype,
            max_new_tokens=max_new_tokens,
            offload_folder=offload_folder,
            attn_implementation=attn_implementation,
        )
    except Exception as exc:
        logger.warning("本地 Gemma 客户端初始化失败，将回退到启发式模式: %s", exc)
        return None


def build_fallback_cases() -> List[FraudCase]:
    """当本地案例库不可用时，提供一组最小内置案例。"""
    return [
        FraudCase.from_dict(
            {
                "id": "fallback_logistics_001",
                "category": "冒充电商物流客服类",
                "attack_role": "fake_customer_service",
                "target_info": ["银行卡", "验证码", "远程控制"],
                "attack_strategies": [
                    {
                        "id": "fallback_logistics_001:refund_pressure",
                        "cialdini_principle": "authority",
                        "tactic_name": "客服退款流程施压",
                        "description": "冒充平台客服，以退款、理赔等名义获取银行卡与验证码。",
                        "typical_dialogue": "为了给你退款，需要你先配合验证银行卡。",
                        "escalation_condition": "受害者确认近期确实有电商订单或快递时。",
                        "intensity_level": 2,
                    },
                    {
                        "id": "fallback_logistics_001:screen_share",
                        "cialdini_principle": "commitment",
                        "tactic_name": "远程协助接管设备",
                        "description": "要求下载会议软件、共享屏幕或开启远程控制。",
                        "typical_dialogue": "你不会操作的话，我远程帮你点一下就行。",
                        "escalation_condition": "受害者表示不会操作退款流程时。",
                        "intensity_level": 3,
                    },
                ],
                "dialogue_examples": [{"attacker": "快递丢件赔付", "victim": "需要怎么处理"}],
                "risk_keywords": ["客服", "快递", "退款", "理赔"],
                "red_flags": ["要求验证码", "要求下载远控软件"],
            }
        )
    ]


def _build_branch(
    strategies: List[AttackStrategy],
    branch_name: str,
    defensive: bool,
    max_steps: int = 4,
) -> List[Dict[str, Any]]:
    """构造危险分支与防御分支。"""
    branch_log: List[Dict[str, Any]] = []
    for index, strategy in enumerate(strategies[:max_steps], start=1):
        principles = [strategy.cialdini_principle]
        if defensive:
            branch_log.append(
                {
                    "step": index,
                    "branch": branch_name,
                    "agent_action": f"受害者识别“{strategy.tactic_name}”并通过官方渠道核验",
                    "victim_response": "暂停操作，回拨官方客服，并向家人求助",
                    "triggered_principles": principles,
                    "is_protection_action": True,
                    "asset_exposure_coefficient": 0.0,
                    "evidence_case_id": strategy.id.split(":")[0] if ":" in strategy.id else strategy.id,
                    "evidence_similarity": round(0.72 + index * 0.04, 2),
                }
            )
        else:
            if index % 2 == 0:
                principles.append("scarcity" if strategy.cialdini_principle != "scarcity" else "authority")
            branch_log.append(
                {
                    "step": index,
                    "branch": branch_name,
                    "agent_action": f"攻击者继续使用“{strategy.tactic_name}”推进操作",
                    "victim_response": "受害者继续配合，准备填写个人信息并转账",
                    "triggered_principles": principles,
                    "is_protection_action": False,
                    "asset_exposure_coefficient": min(0.32, 0.08 + index * 0.06),
                    "evidence_case_id": strategy.id.split(":")[0] if ":" in strategy.id else strategy.id,
                    "evidence_similarity": round(0.72 + index * 0.04, 2),
                }
            )
    return branch_log


def _score_branch(branch_log: List[Dict[str, Any]], scorer: RiskScorer) -> None:
    """滚动计算分支分数，并写回每步增量。"""
    previous = scorer.scores
    for item in branch_log:
        updated = scorer.update_scores(
            agent_action=item.get("agent_action", ""),
            triggered_principles=item.get("triggered_principles", []),
            is_protection_action=item.get("is_protection_action", False),
            asset_exposure_coefficient=item.get("asset_exposure_coefficient", 0.0),
        )
        item["score_delta"] = {
            "CHS": round(updated.CHS - previous.CHS, 2),
            "ASS": round(updated.ASS - previous.ASS, 2),
            "SSS": round(updated.SSS - previous.SSS, 2),
            "EES": round(updated.EES - previous.EES, 2),
        }
        item["scores_after"] = updated.to_dict()
        previous = updated


def _build_graph(profile: CognitiveProfile, strategies: List[AttackStrategy]) -> Dict[str, Any]:
    """为前端页面构造轻量图谱数据。"""
    nodes: List[Dict[str, Any]] = [
        {
            "id": "profile",
            "name": profile.scenario_type or "未知场景",
            "category": "scenario",
            "value": profile.overall_vulnerability_score(),
            "risk": profile.overall_vulnerability_score(),
            "description": profile.summary(),
        }
    ]
    links: List[Dict[str, Any]] = []
    categories = [
        {"name": "scenario"},
        {"name": "state"},
        {"name": "vulnerability"},
        {"name": "protection"},
        {"name": "strategy"},
    ]

    feature_map = {
        "state": ["time_pressure", "financial_pressure", "info_asymmetry", "emotional_volatility"],
        "vulnerability": ["authority_compliance", "social_proof_sensitivity", "scarcity_sensitivity", "trust_threshold"],
        "protection": ["decision_delay", "verification_habit", "help_seeking", "link_check_ability"],
    }

    for group_name, feature_keys in feature_map.items():
        for feature_name in feature_keys:
            score = getattr(profile, feature_name, 5.0)
            node_id = f"feature:{feature_name}"
            nodes.append(
                {
                    "id": node_id,
                    "name": feature_name,
                    "category": group_name,
                    "value": score,
                    "risk": score if group_name != "protection" else 10 - score,
                    "description": profile.reasoning.get(feature_name, ""),
                }
            )
            links.append(
                {
                    "source": "profile",
                    "target": node_id,
                    "value": round(score, 2),
                    "label": feature_name,
                }
            )

    for strategy in strategies[:3]:
        strategy_id = f"strategy:{strategy.id}"
        nodes.append(
            {
                "id": strategy_id,
                "name": strategy.tactic_name,
                "category": "strategy",
                "value": strategy.intensity_level * 3,
                "risk": 6 + strategy.intensity_level,
                "description": strategy.description,
            }
        )
        links.append(
            {
                "source": "profile",
                "target": strategy_id,
                "value": strategy.intensity_level,
                "label": strategy.cialdini_principle,
            }
        )

    return {"nodes": nodes, "links": links, "categories": categories}


def _build_case_evidence(scenario_type: str, strategies: List[AttackStrategy]) -> str:
    """拼装案例证据摘要。"""
    if not strategies:
        return (
            f"未检索到与 {scenario_type or '当前场景'} 直接对应的具体攻击话术；"
            "案例库模板不会被当作本次输入中已经发生的事实。"
        )
    evidence = "；".join(
        f"{strategy.tactic_name}（{strategy.cialdini_principle}，强度 {strategy.intensity_level}）"
        for strategy in strategies[:3]
    )
    return f"与“{scenario_type or '未知场景'}”最接近的攻击话术包括：{evidence}。"


def run_minimal_cogsec_analysis(
    scenario_text: str,
    questionnaire: Optional[Dict[str, Any]] = None,
    scenario_type: Optional[str] = None,
    case_db_path: Optional[str] = None,
    llm_client: Optional[Any] = None,
) -> Dict[str, Any]:
    """执行最小 CogSec 分析链路，返回前端可直接消费的数据结构。"""
    t0_responder = T0FastResponder(os.environ.get("T0_PATTERNS_PATH"))
    privacy_sanitizer = PrivacySanitizer(enabled=_env_flag("PRESIDIO_ENABLED", default=False))
    t0_result = t0_responder.scan(scenario_text)
    sanitization_result = privacy_sanitizer.sanitize(scenario_text)

    active_llm_client = llm_client if llm_client is not None else build_demo_llm_client()
    extractor = CognitiveProfileExtractor(llm_client=active_llm_client)
    profile = extractor.extract(
        scenario=sanitization_result.sanitized_text or scenario_text,
        questionnaire=questionnaire,
        scenario_type=scenario_type,
    )

    rag = ThreatKnowledgeRAG(
        chroma_path=str(DEFAULT_CHROMA_PATH),
        enable_chroma=False,
    )
    data_path = Path(case_db_path) if case_db_path else DEFAULT_DATA_PATH
    loaded_cases = rag.load_cases_from_file(str(data_path)) if data_path.exists() else []

    if not loaded_cases:
        fallback_cases = build_fallback_cases()
        rag.ingest_cases(fallback_cases)
        loaded_cases = fallback_cases

    strategies = rag.retrieve_attack_strategies(profile.scenario_type, profile, n_results=3)
    if not strategies:
        strategies = list(loaded_cases[0].attack_strategies[:3]) if loaded_cases else []

    branch_a_log = _build_branch(strategies, branch_name="A", defensive=False)
    branch_b_log = _build_branch(strategies, branch_name="B", defensive=True)

    scorer_a = RiskScorer(profile)
    scorer_b = RiskScorer(profile)
    _score_branch(branch_a_log, scorer_a)
    _score_branch(branch_b_log, scorer_b)

    reporter = CounterfactualReporter()
    report = reporter.generate_report(
        branch_a_log=branch_a_log,
        branch_b_log=branch_b_log,
        scorer_a=scorer_a,
        scorer_b=scorer_b,
        cognitive_profile=profile,
        case_evidence=_build_case_evidence(profile.scenario_type, strategies),
    )

    llm_mode = "heuristic"
    llm_error = None
    llm_model_path = None
    llm_loaded_device = None
    if active_llm_client is not None:
        llm_mode = getattr(active_llm_client, "mode_name", active_llm_client.__class__.__name__)
        llm_error = getattr(active_llm_client, "last_error", None)
        llm_model_path = getattr(active_llm_client, "model_path", None)
        llm_loaded_device = getattr(active_llm_client, "loaded_device", None)

    return {
        "profile": profile.to_dict(),
        "strategies": [strategy.to_dict() for strategy in strategies],
        "graph": _build_graph(profile, strategies),
        "branch_a_log": branch_a_log,
        "branch_b_log": branch_b_log,
        "counterfactual_report": report.to_dict(),
        "t0_fast_response": t0_result,
        "sanitization": sanitization_result.to_dict(),
        "meta": {
            "mode": "minimal_demo",
            "loaded_case_count": len(loaded_cases),
            "case_db_path": str(data_path),
            "llm_mode": llm_mode,
            "llm_last_error": llm_error,
            "llm_model_path": llm_model_path,
            "llm_loaded_device": llm_loaded_device,
        },
    }
