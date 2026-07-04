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
 */
export function extractPlainifyInput(data) {
  if (!data) return {}
  const profile = data.profile || {}
  const strategies = (data.strategies || [])
    .slice(0, 3)
    .map((s) => s.tactic_name || s.id)
    .filter(Boolean)
  const interventions = (data.intervention_prescriptions || [])
    .slice(0, 3)
    .map((p) => p.action || p.title)
    .filter(Boolean)

  return {
    scenario_type: profile.scenario_type,
    vulnerability_score: profile.overall_vulnerability_score,
    summary: profile.summary,
    rhetoric_features: strategies,
    intervention_suggestions: interventions,
    t0_matched: data.t0_fast_response?.matched ?? false,
    anomalies: (data.anomalies || []).slice(0, 5),
  }
}
