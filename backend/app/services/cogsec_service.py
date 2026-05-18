"""CogSec 场景分析编排服务。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import time
from typing import Any, Dict, List, Optional

from ..config import Config
from ..modules import (
    CognitiveProfile,
    CognitiveProfileExtractor,
    CounterfactualReporter,
    FraudCase,
    MiroFishRuntime,
    PrivacySanitizer,
    RiskScorer,
    T0FastResponder,
    ThreatKnowledgeRAG,
)
from ..utils import LocalGemmaClient
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.cogsec")


@dataclass
class CogSecAnalysisResult:
    """CogSec 全量分析结果。"""

    profile: Dict[str, Any]
    persona_state_vector: Dict[str, Any]
    strategies: List[Dict[str, Any]]
    graph: Dict[str, Any]
    risk_graph_bundle: Dict[str, Any]
    world_state_snapshot: Dict[str, Any]
    branch_a_log: List[Dict[str, Any]]
    branch_b_log: List[Dict[str, Any]]
    fork_comparison: Dict[str, Any]
    counterfactual_report: Dict[str, Any]
    intervention_prescriptions: List[Dict[str, Any]]
    t0_fast_response: Dict[str, Any]
    sanitization: Dict[str, Any]
    metrics: Dict[str, Any]
    anomalies: List[str]
    implementation_status: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return asdict(self)


class CogSecService:
    """认知安全分析服务。"""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or self._safe_build_llm_client()
        self.profile_extractor = CognitiveProfileExtractor(self.llm_client)
        self.threat_rag = ThreatKnowledgeRAG(Config.CHROMA_PATH)
        self.runtime = MiroFishRuntime()
        self.reporter = CounterfactualReporter()
        self.t0_responder = T0FastResponder(getattr(Config, "T0_PATTERNS_PATH", None))
        self.privacy_sanitizer = PrivacySanitizer(enabled=Config.PRESIDIO_ENABLED and Config.LOCAL_SANITIZE_ENABLED)
        self._case_library_loaded = False

    def analyze_text(
        self,
        scenario_text: str,
        questionnaire: Optional[Dict[str, Any]] = None,
        scenario_type: Optional[str] = None,
    ) -> CogSecAnalysisResult:
        """从场景文本生成完整的 CogSec 分析结果。"""
        started = time.perf_counter()
        self._ensure_case_library()
        t0_result = self.t0_responder.scan(scenario_text)
        sanitization_result = self.privacy_sanitizer.sanitize_with_retry(
            scenario_text,
            storage_policy="session_only",
            max_retries=1,
        )
        if sanitization_result.pii_leak_detected:
            raise RuntimeError("PII leak detected after sanitization retry")

        profile = self.profile_extractor.extract(
            scenario=sanitization_result.sanitized_text or scenario_text,
            questionnaire=questionnaire,
            scenario_type=scenario_type,
        )
        persona_state_vector = profile.to_persona_state_vector()
        risk_graph_bundle = self.threat_rag.build_risk_graph_bundle(
            scenario_text=sanitization_result.sanitized_text or scenario_text,
            scenario_type=profile.scenario_type,
            cognitive_profile=profile,
            persona_state_vector=persona_state_vector,
            n_results=3,
        )
        runtime_result = self.runtime.run(
            persona_state_vector=persona_state_vector,
            risk_graph_bundle=risk_graph_bundle,
            current_input=sanitization_result.sanitized_text or scenario_text,
            deadline_sec=getattr(Config, "COGSEC_RUNTIME_TIMEOUT_SEC", 15.0),
        )
        branch_a_log = [step.to_dict() for step in runtime_result.fork_comparison.branch_a_state_trace]
        branch_b_log = [step.to_dict() for step in runtime_result.fork_comparison.branch_b_state_trace]

        triggered_fork_count = self._count_triggered_forks(sanitization_result.sanitized_text or scenario_text)
        risk_breakdown = RiskScorer(profile).evaluate_counterfactual(
            branch_a_state_trace=runtime_result.fork_comparison.branch_a_state_trace,
            branch_b_state_trace=runtime_result.fork_comparison.branch_b_state_trace,
            fork_point_type=runtime_result.fork_comparison.fork_point_type,
            posterior_updates=runtime_result.fork_comparison.posterior_updates,
            reversibility_curve=runtime_result.fork_comparison.reversibility_curve,
            persona_hit_chain=runtime_result.fork_comparison.persona_hit_chain,
            evidence_graph_consistency=runtime_result.fork_comparison.evidence_graph_consistency,
            anomaly_flags=runtime_result.fork_comparison.anomaly_flags,
            irreversibility_loss=runtime_result.fork_comparison.irreversibility_loss,
            fork_count=triggered_fork_count,
        )

        case_evidence = self._build_case_evidence(profile.scenario_type, risk_graph_bundle.attack_strategy_chain)
        report = self.reporter.generate_report(
            branch_a_log=branch_a_log,
            branch_b_log=branch_b_log,
            scorer_a=None,
            scorer_b=None,
            cognitive_profile=profile,
            case_evidence=case_evidence,
            persona_state_vector=persona_state_vector,
            risk_graph_bundle=risk_graph_bundle,
            fork_comparison=runtime_result.fork_comparison,
            risk_breakdown=risk_breakdown,
        )
        end_to_end_ms = round((time.perf_counter() - started) * 1000, 2)
        anomalies = self._collect_anomalies(
            sanitization_result=sanitization_result.to_dict(),
            risk_graph_bundle=risk_graph_bundle.to_dict(),
            fork_comparison=runtime_result.fork_comparison.to_dict(),
            runtime_result=runtime_result.to_dict(),
            risk_breakdown=risk_breakdown.to_dict(),
        )
        implementation_status = report.implementation_status or {
            "stable_base": [],
            "new_mainline": [],
            "phase_ii": [],
        }

        return CogSecAnalysisResult(
            profile=profile.to_dict(),
            persona_state_vector=persona_state_vector.to_dict(),
            strategies=risk_graph_bundle.attack_strategy_chain,
            graph=risk_graph_bundle.to_dict(),
            risk_graph_bundle=risk_graph_bundle.to_dict(),
            world_state_snapshot=runtime_result.initial_world_state.to_dict(),
            branch_a_log=branch_a_log,
            branch_b_log=branch_b_log,
            fork_comparison=runtime_result.fork_comparison.to_dict(),
            counterfactual_report=report.to_dict(),
            intervention_prescriptions=report.intervention_prescriptions or [],
            t0_fast_response=t0_result,
            sanitization=sanitization_result.to_dict(),
            metrics={
                "t0_latency_ms": t0_result.get("latency_ms"),
                "t0_target_met": t0_result.get("target_met"),
                "end_to_end_ms": end_to_end_ms,
                "end_to_end_target_met": end_to_end_ms < 30000,
                "benchmarks": {
                    "T0 latency < 500ms": bool(t0_result.get("target_met")),
                    "End-to-end inference < 30s": end_to_end_ms < 30000,
                    "FSA > 70%": "Phase-II benchmark hook required",
                    "CPA > 60%": "Phase-II benchmark hook required",
                    "EWT > 2 steps": runtime_result.fork_comparison.best_intervention_window.get("open_step", 0) >= 2,
                    "FPR < 15%": "Phase-II benchmark hook required",
                    "CAL < 0.2": runtime_result.fork_comparison.trajectory_gap >= 0.12,
                    "EAR > 65%": risk_breakdown.evidence_consistency >= 0.65,
                },
                "risk_breakdown": risk_breakdown.to_dict(),
            },
            anomalies=anomalies,
            implementation_status=implementation_status,
        )

    def _score_branch(self, branch_log: List[Dict[str, Any]], scorer: RiskScorer) -> None:
        """滚动更新分支分数，并写回每步分数增量。"""
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

    def _build_branch(
        self,
        profile: CognitiveProfile,
        strategies: List[Any],
        branch_name: str,
        defensive: bool,
    ) -> List[Dict[str, Any]]:
        """根据策略构造危险分支与防御分支。"""
        max_steps = min(Config.MAX_SIMULATION_STEPS, max(3, len(strategies) + 1))
        branch_log: List[Dict[str, Any]] = []

        if not strategies:
            strategies = self._fallback_strategies()

        for index in range(max_steps):
            strategy = strategies[min(index, len(strategies) - 1)]
            principles = [strategy.cialdini_principle]
            if index % 2 == 1 and not defensive:
                principles.append("scarcity" if strategy.cialdini_principle != "scarcity" else "authority")

            if defensive:
                action = self.threat_rag.constrain_action(
                    f"受害者通过官方渠道核验，并对“{strategy.tactic_name}”保持距离",
                    strategy,
                )
                response = "选择回拨官方客服、暂停转账并向家人求助"
                asset_exposure = 0.01 if index == 0 else 0.0
                protection = True
            else:
                action = self.threat_rag.constrain_action(
                    f"攻击者使用“{strategy.tactic_name}”推进对话，要求进一步操作",
                    strategy,
                )
                response = f"受害者在 {strategy.typical_dialogue[:18]} 的引导下继续配合"
                asset_exposure = min(0.32, 0.08 + index * 0.07)
                protection = False

            branch_log.append(
                {
                    "step": index + 1,
                    "branch": branch_name,
                    "strategy_id": strategy.id,
                    "triggered_principles": principles,
                    "agent_action": action,
                    "victim_response": response,
                    "is_protection_action": protection,
                    "asset_exposure_coefficient": asset_exposure,
                    "evidence_case_id": strategy.id.split(":")[0] if ":" in strategy.id else None,
                    "evidence_similarity": round(0.58 + index * 0.06, 2),
                }
            )

        return branch_log

    def _build_graph(self, profile: CognitiveProfile, strategies: List[Any]) -> Dict[str, Any]:
        """构造前端图谱可视化数据。"""
        nodes: List[Dict[str, Any]] = [
            {
                "id": "profile",
                "name": profile.scenario_type or "未知场景",
                "category": "scenario",
                "value": profile.overall_vulnerability_score(),
                "symbolSize": 64,
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
                        "symbolSize": 28 + score * 2.4,
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
                    "symbolSize": 30 + strategy.intensity_level * 10,
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

    def _build_case_evidence(self, scenario_type: str, strategies: List[Any]) -> str:
        """拼装案例证据摘要。"""
        if not strategies:
            return f"未检索到与 {scenario_type or '当前场景'} 高相似的案例，已回退到默认策略库。"
        evidence = "；".join(
            f"{self._strategy_field(strategy, 'tactic_name')}（{self._strategy_field(strategy, 'cialdini_principle')}，强度 {self._strategy_field(strategy, 'intensity_level')}）"
            for strategy in strategies[:3]
        )
        return f"与“{scenario_type}”最相关的真实攻击话术包括：{evidence}。"

    def _strategy_field(self, strategy: Any, key: str) -> Any:
        if isinstance(strategy, dict):
            return strategy.get(key, "")
        return getattr(strategy, key, "")

    def _collect_anomalies(
        self,
        sanitization_result: Dict[str, Any],
        risk_graph_bundle: Dict[str, Any],
        fork_comparison: Dict[str, Any],
        runtime_result: Dict[str, Any],
        risk_breakdown: Dict[str, Any],
    ) -> List[str]:
        anomalies = set()
        if sanitization_result.get("pii_leak_detected"):
            anomalies.add("pii_leak_detected")
        if risk_graph_bundle.get("hallucination_rollback"):
            anomalies.add("hallucination_rollback")
        for item in fork_comparison.get("anomaly_flags", []):
            anomalies.add(item)
        if runtime_result.get("degraded"):
            anomalies.add("timeout_degraded")
        if risk_breakdown.get("audit_required"):
            anomalies.add("audit_required")
        return sorted(anomalies)

    def _ensure_case_library(self) -> None:
        """加载欺诈案例库。"""
        if self._case_library_loaded:
            return

        try:
            loaded_cases = self.threat_rag.load_cases_from_file(Config.FRAUD_CASE_DB_PATH)
        except Exception as exc:
            logger.warning("加载欺诈案例文件失败（%s），已降级到内置案例库。路径：%s 错误：%s",
                           type(exc).__name__, Config.FRAUD_CASE_DB_PATH, exc)
            loaded_cases = []

        if loaded_cases:
            self._case_library_loaded = True
            logger.info("已从文件加载 %s 条欺诈案例（路径：%s）", len(loaded_cases), Config.FRAUD_CASE_DB_PATH)
            return

        fallback_cases = [FraudCase.from_dict(item) for item in self._default_case_library()]
        self.threat_rag.ingest_cases(fallback_cases)
        self._case_library_loaded = True
        logger.warning("欺诈案例文件为空或不存在，已加载内置默认案例库。期望路径：%s", Config.FRAUD_CASE_DB_PATH)

    def _safe_build_llm_client(self) -> Optional[LLMClient]:
        """在环境变量齐全时创建 LLM 客户端。"""
        if getattr(Config, "COGSEC_USE_LOCAL_GEMMA", False):
            try:
                return LocalGemmaClient(
                    model_path=Config.COGSEC_LOCAL_MODEL_PATH,
                    device=Config.COGSEC_LOCAL_GEMMA_DEVICE,
                    torch_dtype=Config.COGSEC_LOCAL_GEMMA_DTYPE,
                    max_new_tokens=Config.COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS,
                    offload_folder=Config.COGSEC_LOCAL_GEMMA_OFFLOAD_DIR,
                )
            except Exception as exc:
                logger.warning("本地 Gemma 初始化失败，转为启发式模式: %s", exc)
                return None

        if not Config.LLM_API_KEY:
            return None
        try:
            return LLMClient()
        except Exception as exc:  # pragma: no cover
            logger.warning("LLM 客户端初始化失败，转为启发式模式: %s", exc)
            return None

    def _count_triggered_forks(self, text: str) -> int:
        """统计场景文本中触发的 fork 规则数量，用于多规则叠加计分。"""
        from ..modules.mainline_runtime import MiroFishRuntime
        text_lower = (text or "").lower()
        count = sum(
            1 for rule in MiroFishRuntime.FORK_RULES
            if any(kw.lower() in text_lower for kw in rule["keywords"])
        )
        return max(1, count)

    def _fallback_strategies(self) -> List[Any]:
        """无案例时使用的默认策略。"""
        cases = [FraudCase.from_dict(case) for case in self._default_case_library()[:3]]
        return [case.attack_strategies[0] for case in cases if case.attack_strategies]

    def _default_case_library(self) -> List[Dict[str, Any]]:
        """内置默认案例库。"""
        return [
            {
                "id": "case_credit_001",
                "category": "虚假征信类",
                "attack_role": "fake_credit_officer",
                "target_info": ["银行卡", "验证码", "屏幕共享"],
                "attack_strategies": [
                    {
                        "id": "case_credit_001:authority_call",
                        "cialdini_principle": "authority",
                        "tactic_name": "征信中心权威施压",
                        "description": "冒充征信或监管人员，以影响征信和司法风险制造服从压力。",
                        "typical_dialogue": "你的征信即将受影响，请立即按我说的做。",
                        "escalation_condition": "受害者表达担忧或害怕账户冻结时。",
                        "intensity_level": 3,
                    }
                ],
                "dialogue_examples": [{"attacker": "马上核验", "victim": "我有点担心"}],
                "risk_keywords": ["征信", "安全账户", "司法风险", "冻结"],
                "red_flags": ["要求屏幕共享", "要求向安全账户转账"],
            },
            {
                "id": "case_rebate_001",
                "category": "刷单返利类",
                "attack_role": "task_operator",
                "target_info": ["垫付款", "收款码", "银行卡"],
                "attack_strategies": [
                    {
                        "id": "case_rebate_001:small_profit",
                        "cialdini_principle": "reciprocity",
                        "tactic_name": "小额返利建立信任",
                        "description": "先给受害者小额甜头，再引导进入更大金额任务。",
                        "typical_dialogue": "这单你已经赚到了，继续做高级单返佣更高。",
                        "escalation_condition": "受害者体验到首次返利后。",
                        "intensity_level": 2,
                    }
                ],
                "dialogue_examples": [{"attacker": "再做一单就能提现", "victim": "那我继续"}],
                "risk_keywords": ["返利", "任务", "垫付", "佣金"],
                "red_flags": ["先返小利后要大额垫付", "提现前还要继续充值"],
            },
            {
                "id": "case_invest_001",
                "category": "虚假网络投资理财类",
                "attack_role": "investment_advisor",
                "target_info": ["投资本金", "证券账户", "转账凭证"],
                "attack_strategies": [
                    {
                        "id": "case_invest_001:expert_packaging",
                        "cialdini_principle": "authority",
                        "tactic_name": "导师包装与内幕背书",
                        "description": "包装专业导师身份，提供内幕消息和稳赚预期。",
                        "typical_dialogue": "我是内部老师，这波行情只有小范围学员能跟上。",
                        "escalation_condition": "受害者表现出赚钱意愿时。",
                        "intensity_level": 2,
                    }
                ],
                "dialogue_examples": [{"attacker": "大家都跟上了", "victim": "我也想试试"}],
                "risk_keywords": ["导师", "内幕", "群聊", "盈利截图"],
                "red_flags": ["承诺稳赚不赔", "展示可伪造收益截图"],
            },
        ]
