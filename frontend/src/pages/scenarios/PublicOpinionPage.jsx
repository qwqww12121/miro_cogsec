import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { SCENARIOS } from '../../scenarios/config'
import ScenarioLayout from '../../components/ScenarioLayout'
import Section from '../../components/Section'
import { FormField, TextInput, TextArea, Select } from '../../components/FormField'
import Icon from '../../components/Icon'
import { runPublicOpinionAnalysis } from '../../api/scenarios'
import PublicOpinionResult from '../../components/results/PublicOpinionResult'

const initialForm = {
  platform: '微博',
  topic: '某品牌虚假宣传争议',
  timeWindow: '24h',
  samples: '',
}

const SAMPLE = `1. 看了这次官方回应，根本没回应核心问题
2. 这种营销方式真的太恶心了，必须维权
3. 我已经在准备投诉材料了
4. 哥几个去黑猫投诉啊
5. 我之前买了，体验确实很差`

export default function PublicOpinionPage() {
  const location = useLocation()
  const prefillText = location.state?.prefillText
  const [form, setForm] = useState(
    prefillText ? { ...initialForm, samples: prefillText } : initialForm
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)

  const onChange = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!form.topic.trim() || !form.samples.trim()) {
      setError('请填写话题与样本内容')
      return
    }
    setLoading(true)
    setData(null)
    try {
      const result = await runPublicOpinionAnalysis(form)
      setData(result)
    } catch (err) {
      setError(err.message || '请求失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <ScenarioLayout
      scenario={SCENARIOS.public_opinion}
      input={
        <Section
          title="输入参数"
          action={
            <button type="button" className="btn-ghost text-xs" onClick={() => setForm((s) => ({ ...s, samples: SAMPLE }))}>
              填入示例
            </button>
          }
        >
          <form className="space-y-3" onSubmit={onSubmit}>
            <FormField label="平台">
              <Select value={form.platform} onChange={onChange('platform')}>
                <option>微博</option>
                <option>抖音</option>
                <option>小红书</option>
                <option>知乎</option>
                <option>多平台聚合</option>
              </Select>
            </FormField>
            <FormField label="话题 / 关键词 *">
              <TextInput value={form.topic} onChange={onChange('topic')} placeholder="如：某品牌虚假宣传争议" />
            </FormField>
            <FormField label="时间窗口">
              <Select value={form.timeWindow} onChange={onChange('timeWindow')}>
                <option value="6h">最近 6 小时</option>
                <option value="24h">最近 24 小时</option>
                <option value="7d">最近 7 天</option>
              </Select>
            </FormField>
            <FormField label="样本文本 *" hint="每行一条评论 / 帖文">
              <TextArea value={form.samples} onChange={onChange('samples')} rows={9} placeholder={SAMPLE} />
            </FormField>
            <button type="submit" className="btn-primary w-full bg-leaf hover:bg-leaf-600" disabled={loading}>
              <Icon name="spark" className="w-4 h-4 mr-1.5" />
              {loading ? '分析中…' : '开始分析'}
            </button>
            <div className="text-[11px] text-ink-500 leading-relaxed pt-1">
              将调用 <code className="text-ink-900">POST /api/cogsec/analyze</code>（scenario_type=public_opinion）；结果直接读取真实 CogSec 引擎输出。
            </div>
          </form>
        </Section>
      }
      result={<PublicOpinionResult data={data} loading={loading} error={error} />}
    />
  )
}
