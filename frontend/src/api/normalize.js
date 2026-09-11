/**
 * Stable view model for the current CogSec response contract.
 *
 * The result pages keep their frontend_update presentation and consume this
 * adapter output.  It selects and formats backend fields only; risk,
 * intervention, scenario, and metric decisions remain backend-owned.
 */

function firstNumber(...values) {
  for (const value of values) {
    const numeric = Number(value)
    if (Number.isFinite(numeric)) return numeric
  }
  return null
}

function meanOf(values) {
  const nums = values.map(Number).filter((value) => Number.isFinite(value))
  if (!nums.length) return null
  return nums.reduce((sum, value) => sum + value, 0) / nums.length
}

function adaptT0(raw) {
  const t0 = asObject(raw)
  const hits = asArray(t0.hits)
  const patterns = asArray(t0.matched_patterns).length
    ? asArray(t0.matched_patterns)
    : hits.map((item) => item?.rule_id).filter(Boolean)
  const keywords = asArray(t0.matched_keywords).length
    ? asArray(t0.matched_keywords)
    : hits.flatMap((item) => [...asArray(item?.tags), item?.matched_text]).filter(Boolean)
  return {
    ...t0,
    matched: Boolean(t0.matched || t0.alert || hits.length),
    matched_patterns: patterns,
    matched_keywords: keywords,
  }
}

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function hasGraph(value) {
  const graph = asObject(value)
  return asArray(graph.nodes).length > 0 || asArray(graph.edges).length > 0 || asArray(graph.links).length > 0
}

function firstObject(...values) {
  return values.map(asObject).find((value) => Object.keys(value).length > 0) || {}
}

function firstText(...values) {
  return values.find((value) => typeof value === 'string' && value.trim()) || ''
}

function normalizeGrounding(...values) {
  const grounding = firstObject(...values)
  return {
    ...grounding,
    level: grounding.level || grounding.grounding_level || 'G0',
    observedActorCount: grounding.observedActorCount ?? grounding.observed_actor_count ?? 0,
    inferredActorCount: grounding.inferredActorCount ?? grounding.inferred_actor_count ?? 0,
    syntheticActorCount: grounding.syntheticActorCount ?? grounding.synthetic_actor_count ?? 0,
  }
}

function metricSourceLabel(metricSource, oasisVerification) {
  const oasis = asObject(oasisVerification)
  const oasisEffective = oasis.selection_source === 'oasis' || oasis.oasis_effective === true
  if (oasisEffective) return 'OASIS 验证 · 正收益采纳'
  if (oasis.oasis_verified || oasis.provenance === 'proxy_and_oasis_verified') {
    return '轻量代理推演'
  }
  if (metricSource === 'oasis' || metricSource === 'oasis_runtime') return 'OASIS 验证'
  if (metricSource === 'proxy' || metricSource === 'lightweight' || metricSource === 'heuristic') {
    return '轻量代理推演'
  }
  if (metricSource === 'direct_llm') return '直接模型基线'
  if (metricSource === 'none') return '未产生运行指标'
  return metricSource ? String(metricSource) : '运行时指标'
}

function retrievalBackendLabel(backend) {
  if (backend === 'chroma') return '向量检索'
  if (backend === 'keyword_fallback') return '关键词回退'
  if (backend === 'scenario_template') return '场景模板'
  return backend ? String(backend) : ''
}

export function normalizeCogSecResponse(payload) {
  const raw = asObject(payload)
  const extension = asObject(raw.scenario_extension)
  const coreAnalysis = asObject(raw.core_analysis)
  const search = asObject(extension.propagation_intervention_search)
  const oasisVerification = asObject(search.oasis_verification)
  const propagation = firstObject(extension.propagation_normalized, extension.propagation)
  const propagationProvenance = asObject(propagation.provenance)
  const searchProvenance = asObject(search.provenance)
  const latencyProfile = asObject(raw.latency_profile)
  const caseProvenance = asObject(extension.canonical_case)
  const coreProvenance = asObject(coreAnalysis.provenance)
  const grounding = normalizeGrounding(
    caseProvenance.grounding,
    coreProvenance.grounding,
    propagationProvenance.grounding,
  )

  const metricSource = firstText(
    latencyProfile.metric_source,
    oasisVerification.metric_source,
    searchProvenance.metric_source,
    propagationProvenance.metric_source,
    coreProvenance.metric_source,
  ) || 'runtime'

  // OASIS 三态:正收益采纳 / 已验证但无正收益(保留轻量代理选择) / 未验证。
  // 对应后端 selection_source 与 oasis_effective 字段;禁止把 proxy 回退伪装成 OASIS 结果。
  const oasisEffective = oasisVerification.selection_source === 'oasis'
    || oasisVerification.oasis_effective === true
  const oasisVerified = Boolean(
    oasisVerification.oasis_verified || oasisVerification.provenance === 'proxy_and_oasis_verified'
  )
  const oasisStatus = oasisEffective ? 'effective' : (oasisVerified ? 'verified_ineffective' : 'none')

  const effectiveIntervention = firstObject(
    coreAnalysis.effective_selected_intervention,
    search.effective_selected_intervention,
    oasisVerification.selected,
  )
  const graphPayload = hasGraph(raw.graph_payload)
    ? asObject(raw.graph_payload)
    : (hasGraph(raw.risk_graph_bundle) ? asObject(raw.risk_graph_bundle) : asObject(raw.graph))

  const profile = asObject(raw.profile)
  const protectionKeys = [
    'decision_delay', 'verification_habit', 'help_seeking',
    'link_check_ability', 'transaction_review', 'prior_experience',
  ]
  if (profile.protection_score == null) {
    const nested = protectionKeys.map((key) => asObject(asObject(profile.dimension_details)[key]).value)
    const computed = firstNumber(profile.protection_score, meanOf(protectionKeys.map((key) => profile[key])), meanOf(nested))
    if (computed != null) profile.protection_score = Number(computed.toFixed(2))
  }
  const scenario = firstText(
    coreAnalysis.scenario,
    profile.scenario_type,
    asObject(raw.scenario_metadata).canonical,
    extension.requires_clarification ? 'unknown' : '',
  ) || 'unknown'

  const responsePlan = asObject(raw.response_plan)
  const assistantMessage = firstText(
    raw.assistant_message,
    responsePlan.assistant_message,
    responsePlan.summary,
  )

  // Dual-view fields: the backend LLM plain-language translation of the
  // professional answer (same coverage, everyday wording) and the single key
  // action.  Empty string means the LLM view was not produced this turn and
  // PlainViewWrapper falls back to local assembly.
  const plainView = firstText(raw.plain_view)
  const mostImportantAction = firstText(raw.most_important_action)

  return {
    ...raw,
    raw,
    profile,
    strategies: asArray(raw.strategies),
    intervention_prescriptions: asArray(raw.intervention_prescriptions),
    anomalies: asArray(raw.anomalies),
    branch_a_log: asArray(raw.branch_a_log),
    branch_b_log: asArray(raw.branch_b_log),
    metrics: asObject(raw.metrics),
    counterfactual_report: asObject(raw.counterfactual_report),
    fork_comparison: asObject(raw.fork_comparison),
    deltaRCurve: asArray(asObject(raw.fork_comparison).delta_r_curve),
    lossCriticalStep: asObject(raw.fork_comparison).loss_critical_step ?? null,
    t0_fast_response: adaptT0(raw.t0_fast_response),
    scenario,
    riskType: firstText(coreAnalysis.risk_type),
    retrievalBackend: firstText(
      coreAnalysis.retrieval_backend,
      asObject(raw.risk_graph_bundle).retrieval_backend,
    ),
    retrievalBackendLabel: retrievalBackendLabel(firstText(
      coreAnalysis.retrieval_backend,
      asObject(raw.risk_graph_bundle).retrieval_backend,
    )),
    agentCount: firstNumber(
      coreAnalysis.agent_count,
      asObject(extension.social_state_summary).actor_count,
      asObject(extension.social_state_summary).agent_count,
      asObject(extension.propagation_graph).agent_count,
    ),
    topologyType: firstText(
      coreAnalysis.topology_type,
      asObject(extension.social_state_summary).topology_type,
      asObject(extension.propagation_graph).topology_type,
    ),
    propagationGraph: hasGraph(extension.propagation_graph)
      ? asObject(extension.propagation_graph)
      : {},
    risk: {
      score: profile.overall_vulnerability_score,
      level: coreAnalysis.risk_level || coreAnalysis.propagation_risk_level || 'unknown',
    },
    assistantMessage,
    plainView,
    mostImportantAction,
    suggestedFollowups: asArray(raw.suggested_followups),
    responsePlan,
    graphPayload,
    conversationState: asObject(raw.conversation_state),
    latencyProfile,
    metricSource,
    metricSourceLabel: metricSourceLabel(metricSource, oasisVerification),
    oasisStatus,
    grounding,
    runtimeComponents: asObject(raw.runtime_components),
    propagation,
    proxySelection: firstObject(search.proxy_selected_intervention, search.selected_best_branch),
    effectiveIntervention,
    oasisVerification,
    status: raw.status || 'complete',
    legacy: {
      branchA: asArray(raw.branch_a_log),
      branchB: asArray(raw.branch_b_log),
      forkComparison: asObject(raw.fork_comparison),
      counterfactualReport: asObject(raw.counterfactual_report),
      strategies: asArray(raw.strategies),
    },
  }
}

export function normalizeClassifyResponse(payload) {
  const data = asObject(payload)
  const confidence = Number.isFinite(Number(data.confidence)) ? Number(data.confidence) : 0
  const extension = asObject(data.scenario_extension)
  const graphPayload = hasGraph(data.graph_payload)
    ? asObject(data.graph_payload)
    : asObject(data.propagation_graph)
  const propagationGraph = hasGraph(data.propagation_graph)
    ? asObject(data.propagation_graph)
    : (hasGraph(extension.propagation_graph) ? asObject(extension.propagation_graph) : graphPayload)
  const coreAnalysis = asObject(data.core_analysis)
  return {
    ...data,
    scenario_type: data.scenario_type || 'unknown',
    scenario: data.scenario_type || 'unknown',
    confidence,
    reason: data.reason || '未提供判定理由',
    extracted_summary: data.extracted_summary || '',
    extracted_fields: asObject(data.extracted_fields),
    attribution: asObject(data.attribution),
    thinking: asArray(data.thinking),
    chat_reply: asObject(data.chat_reply),
    graph_payload: graphPayload,
    graphPayload,
    propagationGraph: hasGraph(propagationGraph) ? propagationGraph : {},
    riskType: coreAnalysis.risk_type || (data.scenario_type === 'public_opinion' || data.scenario_type === 'event_propagation' ? '虚假信息' : ''),
    agentCount: firstNumber(coreAnalysis.agent_count, asObject(propagationGraph).agent_count),
    topologyType: firstText(coreAnalysis.topology_type, asObject(propagationGraph).topology_type),
    agent_trace: asArray(data.agent_trace),
    fork_status: asObject(data.fork_status),
    requires_clarification: data.requires_clarification === true || data.scenario_type === 'unknown',
  }
}
