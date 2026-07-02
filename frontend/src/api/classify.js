import client from './client'

/**
 * 智能场景识别
 * 后端：POST /api/classify  body: { text }
 * 返回：{ scenario_type: 'fraud_im' | 'public_opinion' | 'event_propagation',
 *        confidence: 0-1, reason: string, extracted_summary: string, model: string }
 *
 * 开发期由 Vite 把 /api 代理到 http://localhost:5001，生产期由后端同源提供。
 */

// 后端对信息不足的输入会主动把 confidence 压到 < 0.5（见 LLM prompt）。
// 低于该阈值时，前端不再强行把用户导进某个具体场景。
export const LOW_CONFIDENCE_THRESHOLD = 0.5

export async function classifyScenario(text) {
  const resp = await client.post('/api/classify', { text })

  // 后端约定的失败结构：{ success: false, error: '...' }
  if (resp?.data?.success === false) {
    throw new Error(resp.data.error || '识别失败')
  }

  // 成功结构：{ success: true, data: { ... } }
  const data = resp?.data?.data ?? resp?.data
  if (!data || data.scenario_type == null) {
    throw new Error('后端返回数据格式异常，未能解析识别结果')
  }
  return data
}
