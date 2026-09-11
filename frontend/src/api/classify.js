import client from './client'
import { normalizeClassifyResponse } from './normalize'

/**
 * 智能场景识别
 * 后端：POST /api/classify  body: { text }
 * 返回：{ scenario_type: 'fraud_im' | 'public_opinion' | 'event_propagation',
 *        confidence: 0-1, reason: string, extracted_summary: string, model: string }
 *
 * 开发期由 Vite 把 /api 代理到 http://localhost:5001，生产期由后端同源提供。
 */

// 后端对信息不足的输入会主动把 confidence 压到 < 0.5（见 LLM prompt）。
export const LOW_CONFIDENCE_THRESHOLD = 0.5

const AUDIO_EXTENSIONS = new Set(['webm', 'wav', 'mp3', 'm4a', 'mp4', 'mpeg', 'mpga', 'ogg', 'oga'])

function isAudioFile(file) {
  const extension = String(file?.name || '').split('.').pop()?.toLowerCase()
  return String(file?.type || '').startsWith('audio/') || AUDIO_EXTENSIONS.has(extension)
}

export async function classifyScenario(text, { attachments = [], signal } = {}) {
  let body = { text }
  let config = signal ? { signal } : undefined
  if (attachments.length) {
    const form = new FormData()
    form.append('text', text || '')
    attachments.forEach((file) => {
      form.append(isAudioFile(file) ? 'audio' : 'files', file, file.name)
    })
    body = form
    // Let Axios/browser set the multipart boundary. Explicitly setting the
    // header would omit the boundary in some browsers.
    config = { headers: { 'Content-Type': undefined }, signal }
  }
  // Chat UI stays at 20s. OASIS itself times out at 10s and falls back inside the request.
  const resp = await client.post('/api/classify', body, { timeout: 20000, ...config })

  // 后端约定的失败结构：{ success: false, error: '...' }
  if (resp?.data?.success === false) {
    throw new Error(resp.data.message || resp.data.error || '识别失败')
  }

  // 成功结构：{ success: true, data: { ... } }
  const data = resp?.data?.data ?? resp?.data
  if (!data || data.scenario_type == null) {
    throw new Error('识别结果格式异常，请稍后重试')
  }
  return normalizeClassifyResponse(data)
}
