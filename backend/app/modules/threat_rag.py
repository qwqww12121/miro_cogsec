"""诈骗知识约束检索模块。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from .runtime_schema import RiskGraphBundle, RiskGraphEdge, RiskGraphNode

try:
    import chromadb
    from chromadb.utils import embedding_functions
except Exception:  # pragma: no cover
    chromadb = None
    embedding_functions = None


# Hardcoded strategy templates for non-fraud scenarios (no case store entries exist for these)
_PROPAGATION_STRATEGY_TEMPLATES: Dict[str, List[Dict[str, Any]]] = {
    "event_propagation": [
        {
            "id": "rumor_cascade",
            "cialdini_principle": "social_proof",
            "tactic_name": "谣言裂变式传播",
            "description": "利用信息不对称，借助关键节点账号放大未经核实的信息，形成滚雪球效应。",
            "typical_dialogue": "这条消息已经好几个大V转发了，应该是真的，快扩散。",
            "escalation_condition": "传播覆盖率超过 30% 且头部节点介入时升级。",
            "intensity_level": 3,
        },
        {
            "id": "emotional_amplification",
            "cialdini_principle": "liking",
            "tactic_name": "情绪化渲染放大",
            "description": "通过极端化表述激发群体愤怒或恐惧，使受众跳过理性判断直接转发。",
            "typical_dialogue": "太可怕了！这件事不能就这么算了，大家一起扩散！",
            "escalation_condition": "情绪值超过阈值时触发二次传播高峰。",
            "intensity_level": 2,
        },
        {
            "id": "authority_hijack",
            "cialdini_principle": "authority",
            "tactic_name": "权威账号借势传播",
            "description": "借助高粉丝量账号或疑似官方账号转发，为不实信息提供可信度背书。",
            "typical_dialogue": "某知名媒体账号已转发此消息，来源应该可靠。",
            "escalation_condition": "官方账号或媒体账号介入后传播速度激增。",
            "intensity_level": 2,
        },
    ],
    "public_opinion": [
        {
            "id": "echo_chamber_polarization",
            "cialdini_principle": "social_proof",
            "tactic_name": "信息茧房极化",
            "description": "在特定圈层内反复强化单一观点，使群体认知逐步偏移，排斥异见。",
            "typical_dialogue": "这个圈子里的人都这么认为，反对的人才是异类。",
            "escalation_condition": "回声室效应形成闭环后触发群体极化。",
            "intensity_level": 3,
        },
        {
            "id": "emotional_resonance_trigger",
            "cialdini_principle": "liking",
            "tactic_name": "情感共鸣激活",
            "description": "挖掘受众情绪触发点，以高情绪价值内容引发共鸣与自发转发。",
            "typical_dialogue": "这件事戳到我了，必须让更多人知道。",
            "escalation_condition": "情绪共鸣超过传播临界值时形成自发传播链。",
            "intensity_level": 2,
        },
        {
            "id": "trending_topic_hijack",
            "cialdini_principle": "authority",
            "tactic_name": "热点借势操控",
            "description": "借助热点事件嫁接议题，快速渗透已有流量的讨论圈层，扩大影响力。",
            "typical_dialogue": "趁着这个热点，把我们的观点夹带进去推一推。",
            "escalation_condition": "热点话题热度超过阈值时启动借势操控。",
            "intensity_level": 2,
        },
    ],
}


def _tokenize(text: str) -> List[str]:
    return [token for token in re.split(r"[^\w\u4e00-\u9fff]+", (text or "").lower()) if token]


def _cosine_similarity(left: str, right: str) -> float:
    left_tokens = _tokenize(left)
    right_tokens = _tokenize(right)
    if not left_tokens or not right_tokens:
        return 0.0

    left_count: Dict[str, int] = {}
    right_count: Dict[str, int] = {}
    for token in left_tokens:
        left_count[token] = left_count.get(token, 0) + 1
    for token in right_tokens:
        right_count[token] = right_count.get(token, 0) + 1

    common = set(left_count.keys()) & set(right_count.keys())
    numerator = sum(left_count[key] * right_count[key] for key in common)
    left_norm = math.sqrt(sum(value * value for value in left_count.values()))
    right_norm = math.sqrt(sum(value * value for value in right_count.values()))
    return float(numerator / max(1e-6, left_norm * right_norm))


@dataclass
class AttackStrategy:
    """单条攻击策略。"""

    id: str
    cialdini_principle: str
    tactic_name: str
    description: str
    typical_dialogue: str
    escalation_condition: str
    intensity_level: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AttackStrategy":
        return cls(
            id=str(payload.get("id", "")),
            cialdini_principle=str(payload.get("cialdini_principle", "authority")),
            tactic_name=str(payload.get("tactic_name", "")),
            description=str(payload.get("description", "")),
            typical_dialogue=str(payload.get("typical_dialogue", "")),
            escalation_condition=str(payload.get("escalation_condition", "")),
            intensity_level=int(payload.get("intensity_level", 1)),
        )


@dataclass
class FraudCase:
    """诈骗案例知识单元。"""

    id: str
    category: str
    attack_role: str
    target_info: List[str]
    attack_strategies: List[AttackStrategy]
    dialogue_examples: List[Dict[str, str]]
    risk_keywords: List[str]
    red_flags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["attack_strategies"] = [strategy.to_dict() for strategy in self.attack_strategies]
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FraudCase":
        strategies = [AttackStrategy.from_dict(item) for item in payload.get("attack_strategies", [])]
        return cls(
            id=str(payload.get("id", "")),
            category=str(payload.get("category", "unknown")),
            attack_role=str(payload.get("attack_role", "adversary")),
            target_info=[str(item) for item in payload.get("target_info", [])],
            attack_strategies=strategies,
            dialogue_examples=[dict(item) for item in payload.get("dialogue_examples", [])],
            risk_keywords=[str(item) for item in payload.get("risk_keywords", [])],
            red_flags=[str(item) for item in payload.get("red_flags", [])],
        )


class ThreatKnowledgeRAG:
    """用于约束攻击者行为的诈骗知识检索器。"""

    COLLECTION_NAME = "fraud_cases_cn"
    MIN_VERIFICATION_SIMILARITY = 0.3
    MIN_GRAPH_CONSISTENCY = 0.35

    def __init__(
        self,
        chroma_path: str,
        client: Any = None,
        enable_chroma: bool = True,
        embedding_function: Any = None,
    ):
        self.chroma_path = chroma_path
        self.client = None
        self.collection = None
        self.case_store: Dict[str, FraudCase] = {}
        self.known_operations: set[str] = set()

        if enable_chroma and (client is not None or chromadb is not None):
            self.client = client or chromadb.PersistentClient(path=chroma_path)
            self.embedding_function = embedding_function
            if self.embedding_function is None and embedding_functions is not None:
                self.embedding_function = embedding_functions.DefaultEmbeddingFunction()

            kwargs = {"name": self.COLLECTION_NAME}
            if self.embedding_function is not None:
                kwargs["embedding_function"] = self.embedding_function
            self.collection = self.client.get_or_create_collection(**kwargs)

    def ingest_cases(self, cases: List[FraudCase]) -> None:
        """写入案例库并建立索引。"""
        if not cases:
            return

        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []

        for case in cases:
            self.case_store[case.id] = case
            for strategy in case.attack_strategies:
                self.known_operations.add(strategy.tactic_name.strip().lower())
            documents.append(self._case_to_document(case))
            metadatas.append({"category": case.category, "case_id": case.id, "attack_role": case.attack_role})
            ids.append(case.id)

        if self.collection is not None:
            self.collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

    def load_cases_from_file(self, file_path: str) -> List[FraudCase]:
        """从 JSON 文件加载案例并写入索引。"""
        if not os.path.exists(file_path):
            return []

        with open(file_path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)

        raw_cases = payload.get("cases", payload) if isinstance(payload, dict) else payload
        cases = [FraudCase.from_dict(item) for item in raw_cases]
        self.ingest_cases(cases)
        return cases

    def retrieve_attack_strategies(
        self,
        scenario_type: str,
        cognitive_profile: Any,
        n_results: int = 3,
    ) -> List[AttackStrategy]:
        """按场景与受害者画像检索最相关的攻击策略。"""
        # Non-fraud scenarios have no entries in the case store; use hardcoded templates
        # to avoid returning semantically similar but wrong-category fraud strategies.
        if scenario_type in _PROPAGATION_STRATEGY_TEMPLATES:
            templates = _PROPAGATION_STRATEGY_TEMPLATES[scenario_type]
            return [AttackStrategy.from_dict(t) for t in templates[:n_results]]

        if not self.case_store:
            return []

        query = self._build_query(scenario_type, cognitive_profile)
        candidate_case_ids = self._retrieve_case_ids(query, scenario_type, n_results=max(n_results, 3))
        candidate_cases = [self.case_store[case_id] for case_id in candidate_case_ids if case_id in self.case_store]
        strategies = self._rank_strategies(candidate_cases, cognitive_profile)

        verified: List[AttackStrategy] = []
        for strategy in strategies:
            if self.verify_generated_action(strategy.typical_dialogue, strategy):
                verified.append(strategy)
            if len(verified) >= n_results:
                break

        if not verified:
            verified = strategies[:n_results]

        return verified[:n_results]

    def build_risk_graph_bundle(
        self,
        scenario_text: str,
        scenario_type: str,
        cognitive_profile: Any,
        persona_state_vector: Any,
        n_results: int = 3,
    ) -> RiskGraphBundle:
        """Construct the mainline threat-persona-context graph bundle."""
        strategies = self.retrieve_attack_strategies(scenario_type, cognitive_profile, n_results=n_results)
        weakness_hits = self._derive_persona_weakness_hits(persona_state_vector)
        evidence_items = self._collect_evidence_items(scenario_text, strategies)
        asset_targets = self._derive_asset_targets(scenario_text, strategies)
        environment_context = self._derive_environment_context(scenario_text, scenario_type)
        fork_points = self._derive_fork_points(scenario_text, strategies, asset_targets, scenario_type)

        consistency_scores = []
        for strategy in strategies:
            _, score = self.verify_strategy_legitimacy(strategy)
            consistency_scores.append(score)
        evidence_score = min(1.0, 0.2 + len(evidence_items) * 0.15)
        consistency_score = round((sum(consistency_scores) + evidence_score) / max(1, len(consistency_scores) + 1), 3)

        hallucination_rollback = consistency_score < self.MIN_GRAPH_CONSISTENCY
        warnings: List[str] = []
        if hallucination_rollback:
            warnings.append("llm hallucination -> rollback to verified threat templates")
            strategies = self._fallback_verified_strategies(scenario_type, strategies)

        nodes, edges = self._build_graph_objects(
            strategies=strategies,
            weakness_hits=weakness_hits,
            evidence_items=evidence_items,
            asset_targets=asset_targets,
            fork_points=fork_points,
            environment_context=environment_context,
        )

        return RiskGraphBundle(
            schema_version="cogsec.mainline.v1",
            threat_template_nodes=[
                {
                    "id": f"threat:{strategy.id}",
                    "label": strategy.tactic_name,
                    "principle": strategy.cialdini_principle,
                    "description": strategy.description,
                    "intensity": strategy.intensity_level,
                }
                for strategy in strategies
            ],
            evidence_items=evidence_items,
            persuasion_principles=[strategy.cialdini_principle for strategy in strategies],
            persona_weakness_hits=weakness_hits,
            asset_targets=asset_targets,
            environment_context=environment_context,
            fork_points=fork_points,
            nodes=nodes,
            edges=edges,
            attack_strategy_chain=[strategy.to_dict() for strategy in strategies],
            consistency_score=consistency_score,
            hallucination_rollback=hallucination_rollback,
            warnings=warnings,
        )

    def verify_strategy_legitimacy(self, strategy: AttackStrategy) -> Tuple[bool, float]:
        """验证策略是否存在于知识库中。"""
        best_similarity = 0.0
        for case in self.case_store.values():
            for known_strategy in case.attack_strategies:
                similarity = self._strategy_similarity(strategy, known_strategy)
                best_similarity = max(best_similarity, similarity)

        return best_similarity >= self.MIN_VERIFICATION_SIMILARITY, round(best_similarity, 3)

    def _fallback_verified_strategies(
        self,
        scenario_type: str,
        current: List[AttackStrategy],
    ) -> List[AttackStrategy]:
        if current:
            return current
        for case in self.case_store.values():
            if case.category == scenario_type and case.attack_strategies:
                return case.attack_strategies[:3]
        for case in self.case_store.values():
            if case.attack_strategies:
                return case.attack_strategies[:3]
        return []

    def assert_operation_allowed(self, action_text: str) -> bool:
        """断言动作是否在已知操作白名单中。"""
        if not action_text:
            return False

        lowered = action_text.lower()
        for operation in self.known_operations:
            if operation and operation in lowered:
                return True

        action_tokens = set(_tokenize(lowered))
        for operation in self.known_operations:
            if not operation:
                continue
            if action_tokens & set(_tokenize(operation)):
                return True
        return False

    def verify_generated_action(self, action_text: str, strategy: Optional[AttackStrategy] = None) -> bool:
        """验证动作是否与检索知识有足够相似度。"""
        if not action_text:
            return False

        if not self.assert_operation_allowed(action_text):
            return False

        candidates: List[str] = []
        if strategy is not None:
            candidates.extend([strategy.tactic_name, strategy.description, strategy.typical_dialogue])

        for case in self.case_store.values():
            for known in case.attack_strategies:
                candidates.extend([known.tactic_name, known.description, known.typical_dialogue])

        best = 0.0
        for text in candidates:
            best = max(best, _cosine_similarity(action_text, text))

        return best >= self.MIN_VERIFICATION_SIMILARITY

    def constrain_action(self, action_text: str, fallback_strategy: AttackStrategy) -> str:
        """对生成动作执行断言与回退。"""
        if self.verify_generated_action(action_text, fallback_strategy):
            return action_text
        return fallback_strategy.typical_dialogue or fallback_strategy.description

    def _retrieve_case_ids(self, query: str, scenario_type: str, n_results: int) -> List[str]:
        if self.collection is not None:
            # Fetch extra results so we can post-filter by category
            fetch_n = min(max(n_results * 2, 6), max(1, len(self.case_store)))
            result = self.collection.query(query_texts=[query], n_results=fetch_n)
            metadatas = result.get("metadatas", [[]])
            case_ids = [item.get("case_id") for item in metadatas[0] if item.get("case_id")]
            if case_ids:
                # Prefer cases whose category matches the requested scenario type
                matched = [
                    cid for cid in case_ids
                    if cid in self.case_store
                    and self._category_score(self.case_store[cid].category, scenario_type) >= 0.8
                ]
                return (matched if matched else case_ids)[:n_results]

        ranked = sorted(
            self.case_store.values(),
            key=lambda case: self._case_relevance(case, query, scenario_type),
            reverse=True,
        )
        return [case.id for case in ranked[:n_results]]

    def _category_score(self, case_category: str, scenario_type: str) -> float:
        """Return match score [0,1] between a case's category and the requested scenario_type."""
        if not scenario_type:
            return 1.0
        if case_category == scenario_type:
            return 1.0
        # Canonical fraud_im maps to all fraud sub-types except romance
        _FRAUD_IM_CATEGORIES: frozenset = frozenset([
            "虚假征信类", "刷单返利类", "虚假网络投资理财类",
            "冒充电商物流客服类", "冒充公检法及政府机关类",
            "冒充领导熟人类", "虚假贷款代办信用卡类",
            "机票退改签类", "网络游戏产品虚假交易类",
        ])
        if scenario_type == "fraud_im" and case_category in _FRAUD_IM_CATEGORIES:
            return 0.85
        return SequenceMatcher(None, scenario_type, case_category).ratio()

    def _build_query(self, scenario_type: str, cognitive_profile: Any) -> str:
        query_parts = [f"Fraud type: {scenario_type or 'unknown'}"]

        if getattr(cognitive_profile, "authority_compliance", 0) > 6:
            query_parts.append("victim is responsive to authority claims")
        if getattr(cognitive_profile, "scarcity_sensitivity", 0) > 6:
            query_parts.append("victim is responsive to urgency and scarcity")
        if getattr(cognitive_profile, "social_proof_sensitivity", 0) > 6:
            query_parts.append("victim follows crowd signals")
        if getattr(cognitive_profile, "financial_pressure", 0) > 6:
            query_parts.append("victim has strong financial motivation")
        if getattr(cognitive_profile, "trust_threshold", 0) > 6:
            query_parts.append("victim tends to trust strangers")

        return ", ".join(query_parts)

    def _derive_persona_weakness_hits(self, persona_state_vector: Any) -> List[Dict[str, Any]]:
        candidates = [
            ("authority_compliance", getattr(persona_state_vector, "authority_compliance", 0.0), "authority-pressure susceptibility"),
            ("time_pressure_sensitivity", getattr(persona_state_vector, "time_pressure_sensitivity", 0.0), "time pressure switch risk"),
            ("financial_stress", getattr(persona_state_vector, "financial_stress", 0.0), "financial urgency leverage"),
            ("loss_aversion", getattr(persona_state_vector, "loss_aversion", 0.0), "loss-aversion escalation"),
            ("fomo_susceptibility", getattr(persona_state_vector, "fomo_susceptibility", 0.0), "scarcity and crowd pull"),
            ("emotional_volatility", getattr(persona_state_vector, "emotional_volatility", 0.0), "emotion-driven system switch"),
        ]
        protective = [
            ("verification_habit", 10.0 - getattr(persona_state_vector, "verification_habit", 0.0), "verification gap"),
            ("help_seeking_tendency", 10.0 - getattr(persona_state_vector, "help_seeking_tendency", 0.0), "help-seeking gap"),
            ("analytic_control", 10.0 - getattr(persona_state_vector, "analytic_control", 0.0), "analytic-control gap"),
            ("digital_trust_boundary", 10.0 - getattr(persona_state_vector, "digital_trust_boundary", 0.0), "trust-boundary erosion"),
        ]
        hits = [
            {"dimension": name, "score": round(score, 2), "label": label}
            for name, score, label in candidates + protective
            if score >= 5.5
        ]
        hits.sort(key=lambda item: item["score"], reverse=True)
        return hits[:6]

    def _collect_evidence_items(
        self,
        scenario_text: str,
        strategies: List[AttackStrategy],
    ) -> List[Dict[str, Any]]:
        lowered = (scenario_text or "").lower()
        evidence_items: List[Dict[str, Any]] = []
        for strategy in strategies:
            keywords = _tokenize(" ".join([strategy.tactic_name, strategy.description, strategy.typical_dialogue]))
            hit_tokens = [token for token in keywords if token and token in lowered][:4]
            evidence_items.append(
                {
                    "id": f"evidence:{strategy.id}",
                    "label": strategy.tactic_name,
                    "source": "threat_rag",
                    "matched_terms": hit_tokens,
                    "score": round(min(1.0, 0.35 + len(hit_tokens) * 0.15), 3),
                    "detail": strategy.typical_dialogue or strategy.description,
                }
            )
        return evidence_items

    def _derive_asset_targets(
        self,
        scenario_text: str,
        strategies: List[AttackStrategy],
    ) -> List[Dict[str, Any]]:
        lowered = (scenario_text or "").lower()
        candidates = [
            ("asset:funds", "资金账户", 0.95, ["转账", "汇款", "退款", "safe account"]),
            ("asset:credential", "身份凭证", 0.92, ["验证码", "动态码", "短信", "密码"]),
            ("asset:device", "设备控制权", 0.86, ["共享屏幕", "远程", "下载", "app"]),
            ("asset:social", "社会支持系统", 0.72, ["不要告诉别人", "单独联系", "保密"]),
        ]
        assets = []
        for asset_id, label, severity, keywords in candidates:
            if any(keyword.lower() in lowered for keyword in keywords):
                assets.append({"id": asset_id, "label": label, "severity": severity})
        if not assets and strategies:
            assets.append({"id": "asset:funds", "label": "资金账户", "severity": 0.8})
        return assets

    def _derive_environment_context(self, scenario_text: str, scenario_type: str) -> Dict[str, Any]:
        lowered = (scenario_text or "").lower()
        channel = "text"
        if any(token in lowered for token in ["电话", "来电", "客服热线"]):
            channel = "voice"
        if any(token in lowered for token in ["链接", "网址", "二维码"]):
            channel = "mixed"
        return {
            "scenario_type": scenario_type or "unknown",
            "channel": channel,
            "time_pressure": any(token in lowered for token in ["马上", "立即", "今天内", "过期"]),
            "social_isolation": any(token in lowered for token in ["不要告诉别人", "单独联系", "保密"]),
            "official_masking": any(token in lowered for token in ["官方", "客服", "警方", "监管"]),
        }

    def _derive_fork_points(
        self,
        scenario_text: str,
        strategies: List[AttackStrategy],
        asset_targets: List[Dict[str, Any]],
        scenario_type: str = "fraud_im",
    ) -> List[Dict[str, Any]]:
        # 传播场景无需 fraud 专属 fork 节点
        if scenario_type in ("event_propagation", "public_opinion"):
            return []

        lowered = (scenario_text or "").lower()
        fork_specs = [
            ("transfer_money", ["转账", "汇款", "打款", "safe account"], 0.96),
            ("screen_share", ["共享屏幕", "远程控制", "screen share"], 0.88),
            ("verification_code", ["验证码", "动态码"], 0.92),
            ("unknown_app_download", ["下载", "安装", "app"], 0.83),
            ("social_isolation", ["不要告诉别人", "不要联系家人", "单独联系"], 0.74),
            ("fake_official_verification", ["官方核验", "监管流程", "安全核验"], 0.8),
        ]
        forks = []
        for fork_type, keywords, severity in fork_specs:
            if any(keyword.lower() in lowered for keyword in keywords):
                forks.append(
                    {
                        "id": f"fork:{fork_type}",
                        "type": fork_type,
                        "severity": severity,
                        "asset": asset_targets[0]["label"] if asset_targets else "核心资产",
                        "from_strategy": strategies[0].id if strategies else None,
                    }
                )
        if not forks and strategies:
            forks.append(
                {
                    "id": "fork:transfer_money",
                    "type": "transfer_money",
                    "severity": 0.78,
                    "asset": asset_targets[0]["label"] if asset_targets else "资金账户",
                    "from_strategy": strategies[0].id,
                }
            )
        return forks

    def _build_graph_objects(
        self,
        strategies: List[AttackStrategy],
        weakness_hits: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        asset_targets: List[Dict[str, Any]],
        fork_points: List[Dict[str, Any]],
        environment_context: Dict[str, Any],
    ) -> Tuple[List[RiskGraphNode], List[RiskGraphEdge]]:
        nodes: List[RiskGraphNode] = [
            RiskGraphNode(id="agent:primary", name="Primary Agent", category="agent", value=7.0, risk=4.5, symbol_size=58, description="User digital twin"),
            RiskGraphNode(id="agent:adversary", name="Adversary Agent", category="agent", value=8.5, risk=8.8, symbol_size=56, description="Threat actor"),
            RiskGraphNode(id="agent:context", name="Context Agent", category="agent", value=5.0, risk=5.0, symbol_size=46, description="Scene and platform context"),
            RiskGraphNode(id="agent:audit", name="Audit Agent", category="agent", value=4.0, risk=2.5, symbol_size=44, description="Safety audit and anomaly handler"),
            RiskGraphNode(id="state:world", name="WorldState", category="world_state", value=6.0, risk=6.0, symbol_size=60, description="Counterfactual runtime state"),
        ]
        edges: List[RiskGraphEdge] = [
            RiskGraphEdge(source="agent:primary", target="agent:adversary", relation="TRUST_IN", value=0.62),
            RiskGraphEdge(source="agent:context", target="agent:adversary", relation="PRESSURED_BY", value=0.74, metadata=environment_context),
        ]

        for strategy in strategies:
            node_id = f"threat:{strategy.id}"
            nodes.append(
                RiskGraphNode(
                    id=node_id,
                    name=strategy.tactic_name,
                    category="threat_template",
                    value=6.0 + strategy.intensity_level,
                    risk=6.4 + strategy.intensity_level,
                    symbol_size=42 + strategy.intensity_level * 3,
                    description=strategy.description,
                    metadata={"principle": strategy.cialdini_principle},
                )
            )
            edges.append(RiskGraphEdge(source="agent:adversary", target=node_id, relation="ESCALATES_TO", value=0.62))

        for item in weakness_hits:
            node_id = f"weakness:{item['dimension']}"
            nodes.append(
                RiskGraphNode(
                    id=node_id,
                    name=item["dimension"],
                    category="weakness",
                    value=item["score"],
                    risk=item["score"],
                    symbol_size=30 + item["score"] * 2,
                    description=item["label"],
                )
            )
            edges.append(RiskGraphEdge(source="agent:primary", target=node_id, relation="MATCHES_WEAKNESS", value=item["score"] / 10))
            edges.append(RiskGraphEdge(source=node_id, target="agent:audit", relation="MITIGATED_BY", value=0.72))

        for item in evidence_items:
            node_id = item["id"]
            nodes.append(
                RiskGraphNode(
                    id=node_id,
                    name=item["label"],
                    category="evidence",
                    value=item["score"] * 10,
                    risk=item["score"] * 10,
                    symbol_size=34 + item["score"] * 12,
                    description=item["detail"],
                )
            )
            edges.append(RiskGraphEdge(source=node_id, target="state:world", relation="ESCALATES_TO", value=item["score"]))

        for item in asset_targets:
            node_id = item["id"]
            nodes.append(
                RiskGraphNode(
                    id=node_id,
                    name=item["label"],
                    category="asset",
                    value=item["severity"] * 10,
                    risk=item["severity"] * 10,
                    symbol_size=36 + item["severity"] * 12,
                    description="Protected asset target",
                )
            )

        for item in fork_points:
            node_id = item["id"]
            nodes.append(
                RiskGraphNode(
                    id=node_id,
                    name=item["type"],
                    category="decision",
                    value=item["severity"] * 10,
                    risk=item["severity"] * 10,
                    symbol_size=38 + item["severity"] * 8,
                    description=f"Fork node for {item['type']}",
                )
            )
            edges.append(RiskGraphEdge(source="state:world", target=node_id, relation="FORK_AT", value=item["severity"]))

        for strategy in strategies:
            threat_id = f"threat:{strategy.id}"
            for weakness in weakness_hits[:2]:
                edges.append(
                    RiskGraphEdge(
                        source=threat_id,
                        target=f"weakness:{weakness['dimension']}",
                        relation="MATCHES_WEAKNESS",
                        value=weakness["score"] / 10,
                    )
                )
            for asset in asset_targets:
                edges.append(
                    RiskGraphEdge(
                        source=threat_id,
                        target=asset["id"],
                        relation="THREATENS_ASSET",
                        value=asset["severity"],
                    )
                )
            for fork in fork_points:
                edges.append(
                    RiskGraphEdge(
                        source=threat_id,
                        target=fork["id"],
                        relation="ESCALATES_TO",
                        value=fork["severity"],
                    )
                )

        return nodes, edges

    def _rank_strategies(self, cases: List[FraudCase], profile: Any) -> List[AttackStrategy]:
        scored: List[Tuple[float, AttackStrategy]] = []

        for case in cases:
            for strategy in case.attack_strategies:
                principle = strategy.cialdini_principle.lower()
                alignment = self._principle_alignment(profile, principle)
                intensity_bonus = 0.15 * strategy.intensity_level
                case_bonus = 0.6 if case.category == getattr(profile, "scenario_type", "") else 0.0
                score = alignment + intensity_bonus + case_bonus
                scored.append((score, strategy))

        scored.sort(key=lambda item: item[0], reverse=True)

        unique: List[AttackStrategy] = []
        seen: set[str] = set()
        for _, strategy in scored:
            if strategy.id in seen:
                continue
            unique.append(strategy)
            seen.add(strategy.id)
        return unique

    def _case_to_document(self, case: FraudCase) -> str:
        strategies = ", ".join(strategy.tactic_name for strategy in case.attack_strategies)
        keywords = ", ".join(case.risk_keywords)
        red_flags = ", ".join(case.red_flags)
        return (
            f"Category: {case.category}\n"
            f"Attack Role: {case.attack_role}\n"
            f"Target Info: {', '.join(case.target_info)}\n"
            f"Keywords: {keywords}\n"
            f"Strategies: {strategies}\n"
            f"Red Flags: {red_flags}"
        )

    def _case_relevance(self, case: FraudCase, query: str, scenario_type: str) -> float:
        doc = self._case_to_document(case)
        query_tokens = set(_tokenize(query))
        doc_tokens = set(_tokenize(doc))
        overlap = len(query_tokens & doc_tokens) / max(1, len(query_tokens))
        similarity = SequenceMatcher(None, scenario_type or "", case.category).ratio()
        return overlap + similarity

    def _principle_alignment(self, profile: Any, principle: str) -> float:
        mapping = {
            "authority": getattr(profile, "authority_compliance", 5.0),
            "scarcity": getattr(profile, "scarcity_sensitivity", 5.0),
            "social_proof": getattr(profile, "social_proof_sensitivity", 5.0),
            "reciprocity": getattr(profile, "trust_threshold", 5.0),
            "liking": getattr(profile, "trust_threshold", 5.0),
            "commitment": getattr(profile, "loss_aversion_threshold", 5.0),
            "unity": getattr(profile, "social_proof_sensitivity", 5.0),
        }
        return float(mapping.get(principle, 5.0)) / 10.0

    def _strategy_similarity(self, left: AttackStrategy, right: AttackStrategy) -> float:
        principle_bonus = 0.2 if left.cialdini_principle == right.cialdini_principle else 0.0
        name_similarity = SequenceMatcher(None, left.tactic_name, right.tactic_name).ratio()
        desc_similarity = SequenceMatcher(None, left.description, right.description).ratio()
        dialogue_similarity = SequenceMatcher(None, left.typical_dialogue, right.typical_dialogue).ratio()
        cosine_similarity = _cosine_similarity(left.description + " " + left.typical_dialogue, right.description + " " + right.typical_dialogue)
        score = 0.3 * name_similarity + 0.3 * desc_similarity + 0.2 * dialogue_similarity + 0.2 * cosine_similarity + principle_bonus
        return min(1.0, score)
