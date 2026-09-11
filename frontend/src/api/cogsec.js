import client from './client'
import { normalizeCogSecResponse } from './normalize'

/**
 * 调用后端 CogSec 分析接口
 * 后端：POST /api/cogsec/analyze
 * body: { scenario, scenario_type?, tone?, fragments?, variant_id?, include_benchmark?, user_role? }
 * 返回：保留 raw，同时提供稳定的前端视图模型。
 */
function isAudioFile(file) {
  if (!file) return false
  if (String(file.type || '').startsWith('audio/')) return true
  return /\.(webm|wav|mp3|m4a|mp4|mpeg|mpga|ogg|oga)$/i.test(file.name || '')
}

function buildMultipartPayload(payload, attachments = []) {
  const body = new FormData()
  body.append('scenario', payload.scenario || '')
  if (payload.scenario_type) body.append('scenario_type', payload.scenario_type)
  if (payload.user_role) body.append('user_role', payload.user_role)
  if (payload.tone) body.append('tone', payload.tone)
  if (payload.variant_id) body.append('variant_id', payload.variant_id)
  if (payload.include_benchmark !== undefined) body.append('include_benchmark', String(payload.include_benchmark))
  if (payload.questionnaire) body.append('questionnaire', JSON.stringify(payload.questionnaire))
  if (Array.isArray(payload.fragments)) body.append('fragments', JSON.stringify(payload.fragments))
  attachments.forEach((file) => body.append(isAudioFile(file) ? 'audio' : 'files', file, file.name))
  return body
}

export async function analyzeCogSec(payload, { attachments = [] } = {}) {
  const body = attachments.length ? buildMultipartPayload(payload, attachments) : payload
  const resp = await client.post('/api/cogsec/analyze', body, attachments.length
    ? { headers: { 'Content-Type': undefined } }
    : undefined)
  if (resp?.data?.success === false) {
    throw new Error(resp.data.message || resp.data.error || '分析失败')
  }
  return normalizeCogSecResponse(resp.data?.data ?? resp.data)
}

export async function transcribeCogSec(file, language = 'zh') {
  const body = new FormData()
  body.append('audio', file, file.name || 'recording.webm')
  body.append('language', language)
  const resp = await client.post('/api/cogsec/transcribe', body, {
    headers: { 'Content-Type': undefined },
  })
  if (resp?.data?.success === false) {
    throw new Error(resp.data.message || resp.data.error || '语音识别失败')
  }
  return resp.data?.data ?? resp.data
}

export async function answerCogSecFollowup({ state, message, tone }) {
  const resp = await client.post('/api/cogsec/followup', { state, message, tone })
  if (resp?.data?.success === false) {
    throw new Error(resp.data.message || resp.data.error || '追问失败')
  }
  return resp.data?.data ?? resp.data
}

export async function summarizeSimulationStory(payload) {
  const resp = await client.post('/api/cogsec/story-summary', payload)
  if (resp?.data?.success === false) {
    throw new Error(resp.data.message || resp.data.error || '事件说明失败')
  }
  return resp.data?.data ?? resp.data
}

export async function explainForkSteps(payload) {
  const resp = await client.post('/api/cogsec/step-explain', payload, { timeout: 25000 })
  if (resp?.data?.success === false) {
    throw new Error(resp.data.message || resp.data.error || '步骤说明失败')
  }
  return resp.data?.data ?? resp.data
}

export async function fetchOasisRuntimeStatus() {
  const resp = await client.get('/api/cogsec/runtime-status')
  return resp.data?.data ?? resp.data ?? {}
}

export function oasisLoadingCopy(_status, { agents = 50 } = {}) {
  return `正在运行个体对照与传播仿真（约 ${agents} 个代理节点）。期间可浏览本页说明，请勿关闭或刷新页面。`
}
