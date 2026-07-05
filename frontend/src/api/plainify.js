import client from './client'

/**
 * 将专业分析结果转换为面向普通用户的大白话解释。
 * 后端：POST /api/plainify  body: { ...analysis_fields }
 * 返回：{ plain_summary: string, action_advice: string }
 */
export async function plainifyResult(analysisData) {
  const resp = await client.post('/api/plainify', analysisData)
  if (resp?.data?.success === false) {
    throw new Error(resp.data.error || '通俗解读生成失败')
  }
  const data = resp?.data?.data ?? resp?.data
  if (!data?.plain_summary) {
    throw new Error('后端返回数据格式异常')
  }
  return data
}

/**
 * 从 /api/cogsec/analyze 的返回中挑选关键字段，作为 plainify 的入参。
 * 按 scenario_type 提取对应场景的核心指标，确保 LLM 有足够的场景上下文。
 */
export function extractPlainifyInput(data, scenarioTypeOverride) {
  if (!data) return {}
  const profile = data.profile || {}
  const scenarioType = scenarioTypeOverride || profile.scenario_type || ''

  const detected_tactics = (data.strategies || [])
    .slice(0, 3)
    .map((s) => s.tactic_name || s.id)
    .filter(Boolean)

  const intervention_suggestions = (data.intervention_prescriptions || [])
    .slice(0, 3)
    .map((p) => p.action || p.title)
    .filter(Boolean)

  const base = {
    scenario_type: scenarioType,
    vulnerability_score: profile.overall_vulnerability_score,
    summary: profile.summary,
    detected_tactics,
    intervention_suggestions,
    anomalies: (data.anomalies || []).slice(0, 5),
  }

  if (scenarioType === 'public_opinion') {
    // 舆情场景：补充情绪维度和高危关键词
    const t0 = data.t0_fast_response || {}
    const keywords = [...(t0.matched_patterns || []), ...(t0.matched_keywords || [])]
      .slice(0, 5)
      .map((k) => (typeof k === 'string' ? k : k.pattern || k.keyword || ''))
      .filter(Boolean)
    base.emotional_volatility = profile.emotional_volatility
    base.social_proof_sensitivity = profile.social_proof_sensitivity
    base.high_risk_keywords = keywords
  } else if (scenarioType === 'event_propagation') {
    // 传播场景：补充传播路径关键指标
    const fork = data.fork_comparison || {}
    const counter = data.counterfactual_report || {}
    const win = fork.best_intervention_window || counter.best_intervention_window || {}
    base.trajectory_gap = fork.trajectory_gap
    base.total_spread_steps = Math.max(
      (data.branch_a_log || []).length,
      (data.branch_b_log || []).length,
    )
    base.best_intervention_step = win.open_step
  } else {
    // fraud_im：补充 T0 即时告警结果
    base.t0_alert_matched = data.t0_fast_response?.matched ?? false
  }

  return base
}
