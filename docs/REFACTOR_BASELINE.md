# REFACTOR BASELINE — CogSec Backend Mainline

> **生成日期**: 2026-05-23  
> **范围**: `backend/app/modules/` + `backend/app/api/cogsec.py` + `backend/app/services/cogsec_service.py` + `backend/run_cogsec_demo.py` + `data/`  
> **不涉及**: graph fork 模块 (`api/graph.py`, `api/simulation.py`, `api/report.py` 及其 services)、前端页面

---

## 1. 现有调用链路

### 1.1 `POST /api/cogsec/analyze` 完整数据流

```
[入口] api/cogsec.py:14 analyze_cogsec()
  │  输入: Flask request JSON {scenario, questionnaire?, scenario_type?}
  │  输出: Flask jsonify {success, data: CogSecAnalysisResult.to_dict()}
  ↓
[1] CogSecService.__init__()  — services/cogsec_service.py:57
  │  创建 LLMClient / LocalGemmaClient / None (heuristic fallback)
  │  创建 CognitiveProfileExtractor, ThreatKnowledgeRAG, MiroFishRuntime,
  │      CounterfactualReporter, T0FastResponder, PrivacySanitizer
  ↓
[2] CogSecService.analyze_text()  — services/cogsec_service.py:67
  │  输入: scenario_text: str, questionnaire: dict|None, scenario_type: str|None
  │  输出: CogSecAnalysisResult
  │
  ├── [2a] T0FastResponder.scan(scenario_text) -> {alert, hits, latency_ms}
  ├── [2b] PrivacySanitizer.sanitize_with_retry(scenario_text) -> SanitizationResult
  │        (PII leak -> raise RuntimeError)
  ├── [2c] CognitiveProfileExtractor.extract(sanitized_text, questionnaire, scenario_type)
  │        -> CognitiveProfile (18-dim)
  │        └── 内部: LLM extract -> heuristic fallback -> LIWC cross-validation
  ├── [2d] profile.to_persona_state_vector() -> PersonaStateVector
  ├── [2e] ThreatKnowledgeRAG.build_risk_graph_bundle(scenario_text, scenario_type, profile, psv)
  │        -> RiskGraphBundle (nodes, edges, strategies, evidence, fork_points)
  │        └── 内部: Chroma retrieve -> rank strategies -> verify consistency -> build graph
  ├── [2f] MiroFishRuntime.run(psv, risk_graph_bundle, current_input)
  │        -> RuntimeResult {initial_world_state, fork_comparison}
  │        └── 内部: init WorldState -> select fork -> simulate Branch A (6 steps) + Branch B (6 steps) -> compare
  ├── [2g] RiskScorer(profile).evaluate_counterfactual(branch_a, branch_b, ...)
  │        -> CounterfactualRiskBreakdown
  ├── [2h] CounterfactualReporter.generate_report(branch_a_log, branch_b_log, ..., fork_comparison, risk_breakdown)
  │        -> CFReport (via _generate_mainline_report path)
  ├── [2i] _collect_anomalies(...) -> List[str]
  └── [2j] return CogSecAnalysisResult (aggregates everything above)
```

### 1.2 `GET /api/cogsec/report/<report_id>` 数据流

```
[入口] api/cogsec.py:50 analyze_cogsec_by_report()
  │  从 ProjectManager -> SimulationManager -> ReportManager 逐级获取
  │  拼接 project.simulation_requirement + analysis_summary + report outline + markdown
  │  作为 scenario_text 传入 CogSecService.analyze_text()
  │  → 与 1.1 主链相同
```

### 1.3 `run_cogsec_demo.py` 最小 Demo 链路

```
[入口] run_cogsec_demo.py:78 analyze()
  → run_minimal_cogsec_analysis() in cogsec_minimal_runtime.py:262
  简化链: T0 -> Sanitize -> Extract Profile -> RAG (no Chroma) -> Build branch A/B manually -> Score -> Report
  **不使用** MiroFishRuntime / PersonaStateVector / RiskGraphBundle / fork_comparison
```

---

## 2. 核心数据结构清单

### 2.1 `PersonaStateVector` — `runtime_schema.py:16`

| 字段 | 类型 | 说明 |
|---|---|---|
| `authority_compliance` | `float` | 权威服从度 |
| `time_pressure_sensitivity` | `float` | 时间压力敏感度 |
| `financial_stress` | `float` | 财务压力 |
| `loss_aversion` | `float` | 损失厌恶 |
| `fomo_susceptibility` | `float` | 错失恐惧 |
| `verification_habit` | `float` | 核验习惯 |
| `help_seeking_tendency` | `float` | 求助倾向 |
| `analytic_control` | `float` | 分析控制力 |
| `emotional_volatility` | `float` | 情绪波动性 |
| `digital_trust_boundary` | `float` | 数字信任边界 |
| `asset_sensitivity` | `float` | 资产敏感度 |
| `risk_recovery_awareness` | `float` | 风险恢复意识 |
| `confidence_level` | `float` | 置信度 |
| `system1_bias` | `float` | System-1 偏差 |
| `system2_control` | `float` | System-2 控制 |
| `cognitive_mode` | `str` | 认知模式 (SYSTEM_1 / SYSTEM_2) |
| `switch_policy` | `Dict[str, Any]` | 模式切换策略 |
| `storage_policy` | `Dict[str, Any]` | 存储策略 |
| `source_profile` | `Dict[str, Any]` | 源画像引用 |

### 2.2 `RiskGraphBundle` — `runtime_schema.py:96`

| 字段 | 类型 |
|---|---|
| `schema_version` | `str` |
| `threat_template_nodes` | `List[Dict[str, Any]]` |
| `evidence_items` | `List[Dict[str, Any]]` |
| `persuasion_principles` | `List[str]` |
| `persona_weakness_hits` | `List[Dict[str, Any]]` |
| `asset_targets` | `List[Dict[str, Any]]` |
| `environment_context` | `Dict[str, Any]` |
| `fork_points` | `List[Dict[str, Any]]` |
| `nodes` | `List[RiskGraphNode]` |
| `edges` | `List[RiskGraphEdge]` |
| `attack_strategy_chain` | `List[Dict[str, Any]]` |
| `consistency_score` | `float` |
| `hallucination_rollback` | `bool` |
| `warnings` | `List[str]` |

### 2.3 `WorldStateSnapshot` — `runtime_schema.py:142`

| 字段 | 类型 |
|---|---|
| `step` | `int` |
| `stage` | `str` |
| `action` | `str` |
| `trust_score` | `float` |
| `cognitive_mode` | `str` |
| `asset_exposure` | `float` |
| `intervention_window` | `float` |
| `posterior_risk` | `float` |
| `reversibility` | `float` |
| `evidence_hits` | `List[str]` |
| `persona_hits` | `List[str]` |
| `notes` | `List[str]` |

### 2.4 `BranchTraceStep` — `runtime_schema.py:176`

| 字段 | 类型 |
|---|---|
| `branch` | `str` |
| `step` | `int` |
| `action` | `str` |
| `action_type` | `str` |
| `fork_point_type` | `str` |
| `world_state` | `WorldStateSnapshot` |
| `posterior_updates` | `Dict[str, Any]` |
| `evidence_refs` | `List[str]` |
| `persona_hit_chain` | `List[str]` |
| `irreversible` | `bool` |
| `audit_flag` | `bool` |

### 2.5 `ForkComparisonResult` — `runtime_schema.py:238`

| 字段 | 类型 |
|---|---|
| `fork_point_type` | `str` |
| `fork_node_id` | `str` |
| `branch_a_state_trace` | `List[BranchTraceStep]` |
| `branch_b_state_trace` | `List[BranchTraceStep]` |
| `posterior_updates` | `List[Dict[str, Any]]` |
| `reversibility_curve` | `List[Dict[str, Any]]` |
| `persona_hit_chain` | `List[str]` |
| `evidence_graph_consistency` | `float` |
| `trajectory_gap` | `float` |
| `irreversibility_loss` | `float` |
| `low_discriminability` | `bool` |
| `anomaly_flags` | `List[str]` |
| `best_intervention_window` | `Dict[str, Any]` |

### 2.6 `RiskScores` — `risk_scorer.py:32`

| 字段 | 类型 | 说明 |
|---|---|---|
| `CHS` | `float` | 认知健康分数 (Cognitive Health Score), 默认 100 |
| `ASS` | `float` | 资产安全分数 (Asset Safety Score), 默认 100 |
| `SSS` | `float` | 社会支持分数 (Social Support Score), 默认 50 |
| `EES` | `float` | 情绪升级分数 (Emotion Escalation Score), 默认 0 |
| `risk_score` | `float` | 综合风险分, 默认 20 |
| `cognitive_mode` | `str` | SYSTEM_1 / SYSTEM_2 |
| `reversibility` | `float` | 可逆性, 默认 1.0 |
| `prior_probability` | `float` | 先验概率, 默认 0.2 |
| `posterior_probability` | `float` | 后验概率, 默认 0.2 |

### 2.7 `CounterfactualRiskBreakdown` — `risk_scorer.py:11`

| 字段 | 类型 |
|---|---|
| `final_risk` | `float` |
| `risk_level` | `str` |
| `persona_prior` | `float` |
| `attack_match` | `float` |
| `trajectory_gap` | `float` |
| `irreversibility_loss` | `float` |
| `evidence_consistency` | `float` |
| `fork_point_type` | `str` |
| `low_discriminability` | `bool` |
| `anomaly_flags` | `List[str]` |
| `audit_required` | `bool` |
| `metrics` | `Dict[str, Any]` |

### 2.8 `SanitizationResult` — `privacy_sanitizer.py:28`

| 字段 | 类型 |
|---|---|
| `sanitized_text` | `str` |
| `entities` | `List[SanitizedEntity]` |
| `used_presidio` | `bool` |
| `storage_policy` | `str` |
| `minimal_necessary` | `bool` |
| `retry_count` | `int` |
| `pii_leak_detected` | `bool` |

### 2.9 `CFReport` — `cf_reporter.py:26`

| 字段 | 类型 |
|---|---|
| `summary_branch_a` | `str` |
| `summary_branch_b` | `str` |
| `risk_level` | `str` |
| `critical_bifurcation_step` | `int` |
| `critical_bifurcation_reason` | `str` |
| `trigger_points` | `List[TriggerPoint]` |
| `recommendations` | `List[Dict[str, Any]]` |
| `score_comparison` | `Dict[str, Any]` |
| `related_case_summary` | `Optional[str]` |
| `structured_report` | `Optional[Dict[str, Any]]` |
| `digital_twin_summary` | `Optional[Dict[str, Any]]` |
| `cognitive_weakness_chain` | `Optional[List[Dict[str, Any]]]` |
| `attack_strategy_chain` | `Optional[List[Dict[str, Any]]]` |
| `fork_nodes` | `Optional[List[Dict[str, Any]]]` |
| `branch_contrast` | `Optional[Dict[str, Any]]` |
| `irreversible_nodes` | `Optional[List[Dict[str, Any]]]` |
| `best_intervention_window` | `Optional[Dict[str, Any]]` |
| `intervention_prescriptions` | `Optional[List[Dict[str, Any]]]` |
| `implementation_status` | `Optional[Dict[str, Any]]` |

### 2.10 `InterventionPrescription` — `runtime_schema.py:218`

| 字段 | 类型 |
|---|---|
| `title` | `str` |
| `priority` | `int` |
| `target_failure_node` | `str` |
| `trigger_step` | `int` |
| `window_open_step` | `int` |
| `window_close_step` | `int` |
| `rationale` | `str` |
| `recommended_actions` | `List[str]` |
| `channel` | `str` |
| `expected_effect` | `str` |
| `fallback` | `str` |

### 2.11 `CognitiveProfile` — `cognitive_profiler.py:141`

| 字段 | 类型 | 说明 |
|---|---|---|
| `time_pressure` | `float` | 时间压力 (0-10) |
| `financial_pressure` | `float` | 财务压力 |
| `info_asymmetry` | `float` | 信息不对称 |
| `emotional_volatility` | `float` | 情绪波动 |
| `cognitive_load` | `float` | 认知负荷 |
| `authority_intensity` | `float` | 权威强度 |
| `authority_compliance` | `float` | 权威服从 |
| `social_proof_sensitivity` | `float` | 社会认同敏感 |
| `scarcity_sensitivity` | `float` | 稀缺敏感 |
| `loss_aversion_threshold` | `float` | 损失厌恶阈值 |
| `gambler_fallacy` | `float` | 赌徒谬误 |
| `trust_threshold` | `float` | 信任阈值 |
| `decision_delay` | `float` | 决策延迟 (保护因子) |
| `verification_habit` | `float` | 核验习惯 (保护因子) |
| `help_seeking` | `float` | 求助行为 (保护因子) |
| `link_check_ability` | `float` | 链接甄别能力 (保护因子) |
| `transaction_review` | `float` | 交易复核 (保护因子) |
| `prior_experience` | `float` | 既往经验 (保护因子) |
| `scenario_type` | `str` | 场景类别 |
| `confidence_scores` | `Dict[str, float]` | 各维度置信度 |
| `reasoning` | `Dict[str, str]` | 各维度推理依据 |

### 2.12 Pydantic/Flask Models

当前项目**未使用 Pydantic**。API 层为 Flask Blueprint，数据验证完全靠 `request.get_json() or {}` 手动取字段。所有 dataclass 都有 `to_dict()` 方法但没有 schema validation。

---

## 3. LLM 调用点清单

| # | 文件:行号 | 函数 | 模型 | Prompt 摘要 |
|---|---|---|---|---|
| 1 | `cognitive_profiler.py:468` | `CognitiveProfileExtractor._llm_extract()` | `LLM_MODEL_NAME` (默认 gpt-4o-mini) 或 local_gemma | `EXTRACTION_PROMPT`: "你是一名认知安全分析师。请阅读场景，输出严格 JSON。" — 抽取 18 维特征 + scenario_type + confidence + reasoning |
| 2 | `llm_client.py:64` | `LLMClient.chat()` | 同上 | 通用 OpenAI-compatible chat，供所有 LLM 调用复用 |
| 3 | `llm_client.py:87` | `LLMClient.chat_json()` | 同上 | 与 chat() 相同但强制 `response_format={"type": "json_object"}` |
| 4 | `local_gemma_client.py:49` | `LocalGemmaClient.chat()` | google/gemma-4-E2B-it (本地) | 与 LLMClient 接口一致，走 transformers |
| 5 | `local_gemma_client.py:75` | `LocalGemmaClient.chat_json()` | 同上 | 同上 + JSON 解析 |
| 6 | `ontology_generator.py` | `OntologyGenerator.generate()` | `LLM_MODEL_NAME` | ONTOLOGY_SYSTEM_PROMPT — 设计实体类型/关系类型，面向社交媒体舆论模拟 |
| 7 | `simulation_config_generator.py` | `SimulationConfigGenerator` | `LLM_MODEL_NAME` | 生成 OASIS 模拟配置（agent_configs, time_config, event_config） |
| 8 | `oasis_profile_generator.py` | `OasisProfileGenerator` | `LLM_MODEL_NAME` | 为每个 Zep 实体生成 Agent Profile（人设） |
| 9 | `report_agent.py` | `ReportAgent.generate_report()` | `LLM_MODEL_NAME` | ReACT 模式多轮报告生成（outline + 逐章节 + reflection） |
| 10 | `report_agent.py` | `ReportAgent.chat()` | `LLM_MODEL_NAME` | 对话式问答，Agent 可调用 Zep 检索工具 |

**Note**: #6-#10 属于 graph fork 模块，不在本次改造范围。

---

## 4. 场景假设硬编码点

| # | 文件:行号 | 硬编码内容 | 类型 | 影响 |
|---|---|---|---|---|
| 1 | `config.py:41-43` | `FRAUD_CASE_DB_PATH` 默认指向 `data/fraud_cases.json` | 数据路径 | 只加载诈骗案例 |
| 2 | `config.py:50` | `LIWC_DICT_PATH` 默认指向 `data/liwc_chinese.json` | 数据路径 | LIWC 词典只有 anxiety/fear/urgency/money/authority 5类 |
| 3 | `config.py:52` | `T0_PATTERNS_PATH` 默认指向 `data/t0_regex_patterns.json` | 数据路径 | T0 规则只有反诈关键词 |
| 4 | `config.py:47` | `RISK_THRESHOLD_CRITICAL` 默认 `20` | 阈值 | 反诈场景调参 |
| 5 | `config.py:54` | `RISK_SCORE_THRESHOLD_CRITICAL` 默认 `0.85` | 阈值 | 反诈场景调参 |
| 6 | `config.py:55` | `REVERSIBILITY_WARN_THRESHOLD` 默认 `0.3` | 阈值 | 反诈场景调参 |
| 7 | `config.py:56` | `COGSEC_RUNTIME_TIMEOUT_SEC` 默认 `15s` | 阈值 | 反事实推演超时 |
| 8 | `cognitive_profiler.py:42-53` | `SCENARIO_KEYWORDS` — 10 类诈骗场景关键词 | 词典 | 场景识别硬绑定诈骗分类 |
| 9 | `cognitive_profiler.py:55-74` | `HEURISTIC_FEATURE_RULES` — 中文诈骗话术关键词 | 词典 | 启发式回退只匹配诈骗话术 |
| 10 | `cognitive_profiler.py:320-381` | `EXTRACTION_PROMPT` — "你是一名认知安全分析师" | Prompt | 角色限定为反诈分析 |
| 11 | `cognitive_profiler.py:655-727` | `_load_scenario_defaults()` — 10 类诈骗默认画像 | 默认值 | 无诈骗类别时不可用 |
| 12 | `t0_fast_responder.py:33-48` | `DEFAULT_PATTERNS` — 3 条红旗规则: screen_share_bank_card / safe_account_transfer / police_secrecy_isolation | 规则 | 只匹配电信诈骗行为 |
| 13 | `t0_regex_patterns.json` | 同上 3 条规则的外部文件版 | 数据 | 与代码默认值相同 |
| 14 | `mainline_runtime.py:47-84` | `FORK_RULES` — 6 种 fork 类型: transfer_money / screen_share / verification_code / unknown_app_download / social_isolation / fake_official_verification | 规则 | 分叉检测只适用电信诈骗 |
| 15 | `mainline_runtime.py:554-620` | `_fork_specific_labels()` — 每种 fork 的中文话术模板 | 模板 | Branch A/B 推演步骤写死为诈骗对话 |
| 16 | `threat_rag.py:416-428` | `_derive_asset_targets()` — 4 类资产目标: funds / credential / device / social | 枚举 | 资产分类贴合电信诈骗 |
| 17 | `threat_rag.py:430-443` | `_derive_environment_context()` — channel: text/voice/mixed | 枚举 | 通信渠道限定为诈骗场景 |
| 18 | `threat_rag.py:452-458` | `_derive_fork_points()` — 关键词匹配与 mainline_runtime 中 FORK_RULES 重复 | 规则 | 分叉点识别双重硬编码 |
| 19 | `fraud_cases.json` | 10 条诈骗案例，全部是电信诈骗/网络诈骗 | 数据 | 检索增强只返回诈骗话术 |
| 20 | `liwc_chinese.json` | 5 个维度 (anxiety/fear/urgency/money/authority)，共 ~25 词 | 数据 | 词典尺寸小，维度偏反诈 |
| 21 | `risk_scorer.py:70-78` | `CIALDINI_WEIGHTS` — 7 种说服原则权重 | 参数 | 权重为反诈场景调优 |
| 22 | `cf_reporter.py:200-211` | `implementation_status` — "stable_base" / "new_mainline" / "phase_ii" | 元数据 | 硬编码版本阶段说明 |
| 23 | `cf_reporter.py:364-413` | `_generate_recommendations()` — 中文反诈建议模板 | 模板 | 建议文本面向反诈场景 |
| 24 | `cf_reporter.py:439-501` | `_generate_mainline_prescriptions()` — "切换到官方 APP / 官方回拨" 等 | 模板 | 干预处方面向反诈场景 |
| 25 | `run_cogsec_demo.py:24-28` | `DEFAULT_SCENARIO` — "我接到自称电商平台客服的电话..." | 示例 | Demo 默认文本是诈骗 |

---

## 5. 可复用 vs 必须改造

### 5.1 modules/

| 模块 | 判定 | 原因 |
|---|---|---|
| `privacy_sanitizer.py` | ✅ 可复用 | PII 脱敏与场景无关，直接复用 |
| `t0_fast_responder.py` | ⚠️ 需扩展 | 正则引擎框架可复用，但 `DEFAULT_PATTERNS` 需按场景扩展（舆情谣言/事件传播的 T0 规则） |
| `cognitive_profiler.py` | ⚠️ 需扩展 | 18 维画像 + LLM 提取 + LIWC 交叉验证架构可复用，但 `SCENARIO_KEYWORDS`、`HEURISTIC_FEATURE_RULES`、`EXTRACTION_PROMPT`、`_load_scenario_defaults` 全部绑定诈骗 |
| `runtime_schema.py` | ⚠️ 需扩展 | 数据结构可复用，但 `PersonaStateVector` 的反诈特有字段（authority_compliance/loss_aversion）需补充舆情/传播维度；`fork_point_type` 需扩展枚举 |
| `threat_rag.py` | ❌ 需重写 | 整个模块绑定诈骗案例库 + Cialdini 说服原则 + 电信诈骗资产分类，对舆情/事件传播需要全新的知识检索架构 |
| `mainline_runtime.py` | ❌ 需重写 | `FORK_RULES`、fork 话术模板、Branch A/B 推演逻辑完全绑定电信诈骗对话场景。舆情传播推演需要不同的状态机模型（如 SIR/级联传播/叙事演化） |
| `risk_scorer.py` | ⚠️ 需扩展 | 四维评分 CHS/ASS/SSS/EES + 贝叶斯更新框架可复用，但评分维度对舆情传播需要重新设计（如叙事强度/传播速度/情绪极化等） |
| `cf_reporter.py` | ⚠️ 需扩展 | 报告结构 + 干预处方框架可复用，但建议文本、处方模板、implementation_status 绑定诈骗 |

### 5.2 services/

| 模块 | 判定 | 原因 |
|---|---|---|
| `cogsec_service.py` | ⚠️ 需扩展 | 编排主链框架可复用，但需要在 `analyze_text` 之外新增 `analyze_session`（多轮）、`analyze_file`（文件输入）；需要注入场景类型路由（fraud/public_opinion/event_propagation） |
| `report_agent.py` | — | 不在本次范围（属于 graph fork 模块） |
| `simulation_manager.py` | — | 不在本次范围 |
| `simulation_runner.py` | — | 不在本次范围 |
| `ontology_generator.py` | — | 不在本次范围 |
| `graph_builder.py` | — | 不在本次范围 |

### 5.3 utils/

| 模块 | 判定 | 原因 |
|---|---|---|
| `llm_client.py` | ✅ 可复用 | 通用 OpenAI-compatible 封装 |
| `local_gemma_client.py` | ✅ 可复用 | 本地模型推理 |
| `file_parser.py` | ✅ 可复用 | PDF/MD/TXT 解析，直接用于文件输入场景 |
| `logger.py` | ✅ 可复用 | 通用日志 |
| `retry.py` | ✅ 可复用 | 通用重试 |
| `zep_paging.py` | — | 不在本次范围 |

### 5.4 data/

| 文件 | 判定 | 原因 |
|---|---|---|
| `fraud_cases.json` | ❌ 需替换 | 需新增 `public_opinion_cases.json` / `event_propagation_cases.json` |
| `liwc_chinese.json` | ⚠️ 需扩展 | 5 个维度不足，需补充情绪/道德/群体/叙事等维度 |
| `t0_regex_patterns.json` | ⚠️ 需扩展 | 需新增舆情/事件传播的 T0 规则 |

---

## 6. 风险与未知

**[Q1]** `SimulationRunner` (`simulation_runner.py:10`) 同时 import `asyncio` 和 `threading`，OASIS 仿真运行是同步子进程调用还是异步？如果是异步，CogSec mainline 的 `analyze_text()` 是否需要在 async context 中调用？

**[Q2]** Zep 知识图谱是否是 CogSec 主链的必需依赖？代码中 `api/cogsec.py:53` 在 `by_report` 路由中有 Zep 强依赖（需从 Project/Simulation/Report 三级取数），但 `analyze` 路由只用文本输入不依赖 Zep。Minimal demo 完全不加载 Zep。如果后续要支持多轮 session，Zep 是否作为 session memory 的候选方案？

**[Q3]** `Config` 类 (`config.py:21`) 是模块级单例但使用了类属性而非实例属性——多线程 Flask (`threaded=True` in `run.py:45`) 下是否有竞态条件？`LLM_API_KEY`、`LLM_MODEL_NAME` 等在请求过程中被修改的可能？

**[Q4]** `CogSecService.__init__()` (`cogsec_service.py:57`) 每次请求都 new 一个实例（`api/cogsec.py:28` 中 `service = CogSecService()`），导致 LLMClient 和 ThreatKnowledgeRAG（含 Chroma client）每次都重新创建。Chroma PersistentClient 是否支持短生命周期频繁创建？是否应该改为模块级单例或依赖注入？

**[Q5]** `ThreatKnowledgeRAG` (`threat_rag.py:108`) 的 `chromadb` 导入有 try/except 保护，允许 `chromadb = None` 时降级为纯内存检索。当前生产环境是否依赖 Chroma？如果不依赖，重构时是否可以完全移除 Chroma 依赖？

**[Q6]** `MiroFishRuntime.FORK_RULES` (`mainline_runtime.py:47`) 和 `ThreatKnowledgeRAG._derive_fork_points()` (`threat_rag.py:452`) 中的 fork 关键词规则有大量重复——它们是独立维护的还是应该合并为单一规则源？

**[Q7]** `run_cogsec_demo.py` 中的 minimal runtime 和完整 `CogSecService` 的主链在统计算法上有显著差异（minimal 不用 PersonaStateVector/RiskGraphBundle/MiroFishRuntime/fork_comparison），重构时需要把哪套作为 baseline？还是两套都要保留？

**[Q8]** 舆情传播推演和事件传播推演的数学模型是否有已确定的方向？当前 `mainline_runtime.py` 的分支推演是规则驱动的状态转移（delta-based），舆情传播可能需要图扩散模型、SIR 级联模型、或 LLM-agent 自由推演——需要明确。

**[Q9]** `allowed_extensions` 在 `config.py:72` 中设为 `{'pdf', 'md', 'txt', 'markdown'}`。文件上传是否需要支持更多格式（如 Word/HTML/聊天记录导出/CSV）？

**[Q10]** 当前 `cognitive_profiler.py:165-212` 中 `overall_vulnerability_score()` 计算公式为 `(vuln*0.45 + state*0.35) / protection * 50`，这个权重是为电信诈骗受害者脆弱性设计的。对舆情传播场景（如信息接受度/转发意愿）和事件传播场景（如谣言采信度），需要不同的计算公式——是否已经有方向？

**[Q11]** T0 fast responder 的目标是 `<500ms`，这限制了它只能使用正则而无法调用 LLM。舆情/事件传播场景下的 T0 规则是否需要更复杂的 NLP（如情感分析/立场检测）？如果是，500ms 约束是否需要放宽或改为异步触发？

---

> **下一轮待确认**: 请逐一回答 [Q1]–[Q11]，然后进入第二轮的实施方案设计。
