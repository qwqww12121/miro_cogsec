import service, { requestWithRetry } from './index'

/**
 * 直接提交场景文本执行 CogSec 分析
 * @param {Object} data - { scenario, questionnaire?, scenario_type? }
 */
export const analyzeCogSec = (data) => {
  return requestWithRetry(() => service.post('/api/cogsec/analyze', data), 2, 800)
}

/**
 * 根据现有 reportId 获取 CogSec 分析结果
 * @param {string} reportId
 * @param {Object} params - 可选查询参数
 */
export const getCogSecByReport = (reportId, params = {}) => {
  return requestWithRetry(() => service.get(`/api/cogsec/report/${reportId}`, { params }), 2, 800)
}
