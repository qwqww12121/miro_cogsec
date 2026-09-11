/**
 * 通俗视图（plain view）数据源。
 *
 * 优先使用同一次主链请求中生成的 plain_view /
 * most_important_action 字段：它们是专业版回答的"完整转译"（覆盖面一致，
 * 日常语言，不是删减摘要），由 reporter_policy 在一次 LLM 调用中一并产出。
 *
 * 当 plain_view 不可用或字段为空时，退回结构化字段拼接，避免通俗视图空白。
 */

// 术语转译提示用于保证结构化摘要也保持用户可读。
const FALLBACK_LABELS = {
  vulnerability_score: '风险评分',
  summary: '核心结论',
}

export async function plainifyResult(input) {
  const {
    plain_view,
    most_important_action,
    vulnerability_score,
    summary,
    detected_tactics = [],
    intervention_suggestions = [],
    action_advice,
    assistant_message,
  } = input || {}

  // 首选：同一次分析生成的完整转译版。
  if (plain_view && plain_view.trim().length > 0) {
    const keyAction =
      most_important_action && most_important_action.trim().length > 0
        ? most_important_action
        : action_advice || intervention_suggestions[0] || ''
    return {
      plain_summary: plain_view,
      action_advice: keyAction || '暂无可展示的行动建议',
    }
  }

  // 结构化字段拼接，保证通俗视图始终有内容。
  const lines = []

  if (vulnerability_score != null && !Number.isNaN(Number(vulnerability_score))) {
    lines.push(`${FALLBACK_LABELS.vulnerability_score}：${Number(vulnerability_score).toFixed(1)}`)
  }
  if (summary) {
    lines.push(`${FALLBACK_LABELS.summary}：${truncate(summary, 80)}`)
  }
  if (detected_tactics.length > 0) {
    lines.push(`识别到的手法：${detected_tactics.join('、')}`)
  }
  if (intervention_suggestions.length > 0) {
    lines.push(`可选干预方向：${intervention_suggestions.join('；')}`)
  }

  // Only fall back to the raw assistant message when there is truly no
  // structured data to work with (e.g. an unusual scenario type).
  if (lines.length === 0 && assistant_message) {
    lines.push(truncate(assistant_message, 120))
  }

  if (lines.length === 0) {
    throw new Error('当前没有可展示的通俗解读')
  }

  return {
    plain_summary: lines.join('\n'),
    action_advice:
      most_important_action
      || action_advice
      || intervention_suggestions[0]
      || '暂无可展示的行动建议',
  }
}

function truncate(text, maxLen) {
  if (!text) return ''
  return text.length > maxLen ? `${text.slice(0, maxLen)}…` : text
}

export function extractPlainifyInput(data, scenarioTypeOverride) {
  if (!data) return {}
  const profile = data.profile || {}
  const scenarioType = scenarioTypeOverride || data.scenario || profile.scenario_type || ''
  const effective = data.effectiveIntervention || {}
  const responsePlan = data.responsePlan || data.response_plan || {}
  const raw = data.raw || data
  const strategies = Array.isArray(data.strategies) ? data.strategies : []
  const prescriptions = Array.isArray(data.intervention_prescriptions)
    ? data.intervention_prescriptions
    : []

  // response_plan.recommendations is the real field (array of strings or
  // {action|title} objects). recommended_action / recommended_intervention
  // recommended_action / recommended_intervention are not part of this schema.
  const recommendations = Array.isArray(responsePlan.recommendations)
    ? responsePlan.recommendations
    : []
  const firstRecommendation = recommendations[0]
  const firstRecommendationText = typeof firstRecommendation === 'string'
    ? firstRecommendation
    : (firstRecommendation?.action || firstRecommendation?.title || '')

  return {
    scenario_type: scenarioType,
    // 同一次分析生成的通俗解读（normalize 层已映射为 plainView）。
    plain_view: data.plainView || data.plain_view || raw.plain_view || '',
    most_important_action:
      data.mostImportantAction || data.most_important_action || raw.most_important_action || '',
    assistant_message: data.assistantMessage || data.assistant_message || '',
    action_advice: effective.best_intervention_action
      || effective.message
      || firstRecommendationText
      || prescriptions[0]?.action
      || '',
    vulnerability_score: profile.overall_vulnerability_score,
    summary: profile.summary,
    detected_tactics: strategies.slice(0, 3).map((item) => item.tactic_name || item.id).filter(Boolean),
    intervention_suggestions: prescriptions.slice(0, 3).map((item) => item.action || item.title).filter(Boolean),
    raw,
  }
}
