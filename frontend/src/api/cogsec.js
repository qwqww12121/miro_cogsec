import client from './client'

/**
 * 调用后端 CogSec 分析接口
 * 后端：POST /api/cogsec/analyze
 * body: { scenario: string, questionnaire?: object, scenario_type?: string }
 * 返回：CogSecAnalysisResult（profile / strategies / graph / counterfactual_report / metrics ...）
 */
export async function analyzeCogSec(payload) {
  const resp = await client.post('/api/cogsec/analyze', payload, { timeout: 180000 })
  if (resp?.data?.success === false) {
    throw new Error(resp.data.error || '分析失败')
  }
  return resp.data?.data ?? resp.data
}
