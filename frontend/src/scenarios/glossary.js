/**
 * 场景分析结果的"人类可读化"字典与风险分级。
 *
 * 目的：让不熟悉后端的用户（评委）也能看懂每个指标的含义，
 * 并能一眼看出核心结论。所有专业术语、英文枚举值、异常标记都
 * 在这里集中翻译/解释，组件层只负责取用。
 *
 * —— 标注【待确认】的字段是我按语义补译/自拟的，详见交付清单。
 */

import { humanizeVisibleText } from '../lib/humanizeSim'

// ---------------------------------------------------------------------------
// 一、风险分级（核心结论的视觉锚点）
// 阈值与文案为自拟【待确认】
// ---------------------------------------------------------------------------
export function getRiskBand(score) {
  if (score == null || Number.isNaN(score)) return null
  if (score >= 75) {
    return {
      level: 'critical',
      label: '危急',
      box: 'border-rose-300 bg-rose-50',
      badge: 'bg-rose-200 text-rose-800',
      valueText: 'text-rose-700',
      bar: '#be123c',
      conclusion: '已进入危急区间，应立即截断当前操作并走官方核验。',
    }
  }
  if (score >= 50) {
    return {
      level: 'high',
      label: '高风险',
      box: 'border-rose-200 bg-rose-50',
      badge: 'bg-rose-100 text-rose-700',
      valueText: 'text-rose-600',
      bar: '#e11d48',
      conclusion: '该对象当前极易被话术操纵，建议立即干预。',
    }
  }
  if (score >= 25) {
    return {
      level: 'medium',
      label: '中风险',
      box: 'border-amber-200 bg-amber-50',
      badge: 'bg-amber-100 text-amber-700',
      valueText: 'text-amber-600',
      bar: '#d97706',
      conclusion: '存在一定被操纵风险，建议关注关键薄弱点并适时干预。',
    }
  }
  return {
    level: 'low',
    label: '低风险',
    box: 'border-leaf-100 bg-leaf-50',
    badge: 'bg-leaf-100 text-leaf-600',
    valueText: 'text-leaf-600',
    bar: '#52a882',
    conclusion: '当前被操纵风险较低，保持常规防范即可。',
  }
}

// ---------------------------------------------------------------------------
// 二、专业术语解释（供 InfoHint 悬浮显示）
// ---------------------------------------------------------------------------
export const GLOSSARY = {
  vulnerability_score:
    '衡量当前对象容易被操纵、上当的程度，0–100 分，越高越危险。',
  protection_score:
    '反映用户自身防范意识和风险抵抗能力的综合评分，数值越高说明防范能力越强。',
  t0_latency:
    '系统在检测到高危信号后，发出即时预警所用的响应时间，越短说明预警越及时（目标短于 500 毫秒）。',
  end_to_end:
    '从提交分析请求到返回完整结果的总用时（目标短于 30 秒，超时会降级运行）。',
  cognitive_mode:
    '借鉴心理学双系统理论：直觉反应快、容易被情绪和话术带动；审慎核验慢、会停下来核实再决定。',
  counterfactual:
    '模拟两种走向对比。继续走＝按原话术/对方引导继续；及时止损＝核验、澄清或处置。对比的是后验风险 R(t)，不是已经发生的事。',
  trajectory_gap:
    'ΔR(t)＝同一时刻「继续走」和「及时止损」的风险差。数字越大说明对照差得越远；峰值标的是不可逆前的最后窗口，不是建议拖到这一步才动手。',
  intervention_window:
    '优先在影响面还小的阶段介入（诈骗：核验被切断前；舆情/事件：第一跳）。具体做什么看「干预处方」，不是存档提示。ΔR 峰值只提醒再不拦就晚了。',
  asset_exposure:
    '资产/信息暴露程度。个体反事实曲线使用后验风险 R(t)，不再用该量冒充传播覆盖率。',
  risk_type:
    '本次判定的风险类型：诈骗诱导，或虚假信息（舆情/事件传播）。',
  retrieval_backend:
    '知识检索实际走的后端：向量库、关键词回退，或场景模板。',
  protection_factor:
    '构成保护因子的若干防范习惯维度（如核实习惯、安全设置等）的均值。',
}

// ---------------------------------------------------------------------------
// 三、枚举值翻译（把后端英文枚举显示成中文短语）
// 译法为按语义补译【待确认】
// ---------------------------------------------------------------------------

// 认知模式
export const COGNITIVE_MODE = {
  SYSTEM_1: { label: '直觉反应', desc: '快速直觉反应，易被情绪与话术带动' },
  SYSTEM_2: { label: '审慎核验', desc: '理性分析反应，会主动核实、审慎判断' },
}

// 异常信号标记（主展示中文，英文原名放进 hover 小字）
export const ANOMALY_LABELS = {
  pii_leak_detected: '检测到隐私信息泄露',
  hallucination_rollback: '模型幻觉已回滚',
  score_jump_audit: '风险评分骤变需复核',
  timeout_degraded: '推理超时已降级',
  audit_required: '需要人工复核',
}

// 西奥迪尼说服原理（话术策略标签）
export const CIALDINI_LABELS = {
  authority: '权威服从',
  scarcity: '稀缺诱导',
  social_proof: '从众证明',
  liking: '好感利用',
  reciprocity: '互惠诱导',
  commitment: '承诺一致',
  unity: '认同绑定',
}

// scenario_type 枚举 → 中文场景名（与 scenarios/config 的 name 对齐）
export const SCENARIO_TYPE_LABELS = {
  fraud_im: '诈骗即时通讯',
  public_opinion: '舆情分析',
  event_propagation: '事件传播分析',
}

export const RISK_TYPE_LABELS = {
  诈骗诱导: '诈骗诱导',
  虚假信息: '虚假信息',
  认知风险: '认知风险',
}

/**
 * 取异常标记的中文短语；未知名回退为原值（仍可展示，且前端不会崩）。
 * 返回 { label, original } 供 tag 渲染（original 放进 hover 小字）。
 */
export function describeAnomaly(raw) {
  const original = String(raw)
  const label = ANOMALY_LABELS[original]
  return { label: label || original, original, known: Boolean(label) }
}

/** 取说服原理中文译名，未匹配回退原值。 */
export function describeCialdini(raw) {
  if (!raw) return '—'
  return CIALDINI_LABELS[String(raw)] || String(raw)
}

/** 取场景中文名，未匹配回退原值。 */
export function describeScenarioType(raw) {
  if (!raw) return '—'
  return SCENARIO_TYPE_LABELS[String(raw)] || String(raw)
}

export function describeRiskType(raw) {
  if (!raw) return ''
  return RISK_TYPE_LABELS[String(raw)] || String(raw)
}

/** 取认知模式展示信息，未匹配回退为中文解释。 */
export function describeCognitiveMode(raw) {
  if (!raw) return { label: '—', desc: '' }
  const known = COGNITIVE_MODE[String(raw)]
  if (known) return known
  return { label: humanizeVisibleText(raw) || '当前判断方式', desc: '' }
}
