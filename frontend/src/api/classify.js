import client from './client'

/**
 * 智能场景识别
 * 后端：POST /api/classify  body: { text }
 * 返回：{ scenario_type: 'fraud_im' | 'public_opinion' | 'event_propagation',
 *        confidence: 0-1, reason: string }
 *
 * TODO: 后端接口就绪后取消下方 mock，恢复 client.post 调用。
 */
export async function classifyScenario(text) {
  // --- MOCK START ---
  await new Promise((r) => setTimeout(r, 600))
  return mockClassify(text)
  // --- MOCK END ---

  // 真实调用（接口就绪后启用）：
  // const resp = await client.post('/api/classify', { text })
  // if (resp?.data?.success === false) {
  //   throw new Error(resp.data.error || '识别失败')
  // }
  // return resp.data?.data ?? resp.data
}

function mockClassify(text) {
  const lower = (text || '').toLowerCase()
  const fraudKeywords = ['转账', '验证码', '安全账户', '银行卡', '客服', '征信', '冻结', '屏幕共享']
  const opinionKeywords = ['热搜', '话题', '舆论', '维权', '投诉', '回应', '官方声明', '评论']
  const propagationKeywords = ['传播', '扩散', '转发', '裂变', '事件', '节点', '社群', '路径']

  const score = (keywords) =>
    keywords.reduce((acc, k) => acc + (lower.includes(k.toLowerCase()) ? 1 : 0), 0)

  const scores = {
    fraud_im: score(fraudKeywords),
    public_opinion: score(opinionKeywords),
    event_propagation: score(propagationKeywords),
  }
  const winner = Object.entries(scores).sort((a, b) => b[1] - a[1])[0]

  // 默认（无任何关键词命中）走 fraud_im + 题目示意的固定 mock
  if (!text || winner[1] === 0) {
    return {
      scenario_type: 'fraud_im',
      confidence: 0.92,
      reason: '包含转账诱导和验证码索取行为',
    }
  }

  const reasons = {
    fraud_im: '包含转账诱导和验证码索取行为',
    public_opinion: '出现话题讨论、维权与官方回应等舆情特征',
    event_propagation: '出现传播节点、扩散与转发等事件特征',
  }
  return {
    scenario_type: winner[0],
    confidence: Math.min(0.96, 0.7 + winner[1] * 0.06),
    reason: reasons[winner[0]],
  }
}
