import { analyzeCogSec } from './cogsec'

/**
 * 三个场景统一调用 POST /api/cogsec/analyze（后端 backend/app/api/cogsec.py）。
 * 后端目前没有独立的 public_opinion / event_propagation 分析端点，
 * 因此三个场景共享同一个 CogSec 引擎，仅通过 scenario_type 和 scenario 文本
 * 的拼装方式来区分。前端结果面板会直接消费 CogSecAnalysisResult。
 */

function joinScenario(parts) {
  return parts.filter(Boolean).join('\n')
}

export async function runFraudImAnalysis(form) {
  const scenarioText = joinScenario([
    form.platform ? `[平台]${form.platform}` : '',
    form.attackerRole ? `[嫌疑人身份]${form.attackerRole}` : '',
    form.victimContext ? `[受害人背景]${form.victimContext}` : '',
    form.conversation ? `[对话内容]\n${form.conversation}` : '',
  ])

  return analyzeCogSec({
    scenario: scenarioText,
    scenario_type: form.scenarioCategory || undefined,
    questionnaire: form.questionnaire || undefined,
  })
}

export async function runPublicOpinionAnalysis(form) {
  const scenarioText = joinScenario([
    form.platform ? `[平台]${form.platform}` : '',
    form.topic ? `[话题]${form.topic}` : '',
    form.timeWindow ? `[时间窗口]${form.timeWindow}` : '',
    form.samples ? `[样本]\n${form.samples}` : '',
  ])

  return analyzeCogSec({
    scenario: scenarioText,
    scenario_type: form.scenarioType || '舆情分析',
  })
}

export async function runEventPropagationAnalysis(form) {
  const scenarioText = joinScenario([
    form.eventName ? `[事件]${form.eventName}` : '',
    form.origin ? `[起点]${form.origin}` : '',
    form.channel ? `[渠道]${form.channel}` : '',
    form.timeWindow ? `[时间窗口]${form.timeWindow}` : '',
    form.nodes ? `[节点描述]\n${form.nodes}` : '',
  ])

  return analyzeCogSec({
    scenario: scenarioText,
    scenario_type: form.scenarioType || '事件传播分析',
  })
}
