import { analyzeCogSec } from './cogsec'
import {
  composeEventPropagationText,
  composeFraudText,
  composePublicOpinionText,
} from '../lib/platformContext'

/**
 * 三个场景统一调用 POST /api/cogsec/analyze（后端 backend/app/api/cogsec.py）。
 *
 * 用户在下拉框里选的平台 / 渠道 / 时间窗口会写进 scenario 文本（[平台][渠道][时间窗口]），
 * 主分析和人话步骤都按这个选择切换。问卷字段仍传给认知画像，作置信度校正。
 */

function optionalFragments(form) {
  if (Array.isArray(form.fragments)) return { fragments: form.fragments }
  if (Array.isArray(form.inputs)) return { fragments: form.inputs }
  return {}
}

export async function runFraudImAnalysis(form) {
  return analyzeCogSec({
    scenario: composeFraudText(form),
    scenario_type: form.scenarioCategory || undefined,
    questionnaire: {
      platform: form.platform || undefined,
      attacker_role: form.attackerRole || undefined,
      victim_context: form.victimContext || undefined,
      scenario_category: form.scenarioCategory || undefined,
    },
    ...optionalFragments(form),
  }, { attachments: form.attachments || [] })
}

export async function runPublicOpinionAnalysis(form) {
  return analyzeCogSec({
    scenario: composePublicOpinionText(form),
    scenario_type: 'public_opinion',
    questionnaire: {
      platform: form.platform || undefined,
      time_window: form.timeWindow || undefined,
    },
    ...optionalFragments(form),
  }, { attachments: form.attachments || [] })
}

export async function runEventPropagationAnalysis(form) {
  return analyzeCogSec({
    scenario: composeEventPropagationText(form),
    scenario_type: 'event_propagation',
    questionnaire: {
      channel: form.channel || undefined,
      time_window: form.timeWindow || undefined,
    },
    ...optionalFragments(form),
  }, { attachments: form.attachments || [] })
}
