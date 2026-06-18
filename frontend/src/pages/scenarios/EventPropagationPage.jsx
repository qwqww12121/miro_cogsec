import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { SCENARIOS } from '../../scenarios/config'
import ScenarioLayout from '../../components/ScenarioLayout'
import Section from '../../components/Section'
import { FormField, TextInput, TextArea, Select } from '../../components/FormField'
import Icon from '../../components/Icon'
import { runEventPropagationAnalysis } from '../../api/scenarios'
import EventPropagationResult from '../../components/results/EventPropagationResult'

const initialForm = {
  eventName: '某高校学术不端事件',
  origin: '@匿名爆料账号',
  timeWindow: '24h',
  channel: '微博',
  nodes: '',
}

const SAMPLE = `节点A: @学生论坛账号 - 转发原始爆料
节点B: @行业大V - 二次解读引发话题升级
节点C: @教育媒体官方账号 - 跟进报道
节点D: 跨平台扩散至抖音 / 知乎`

export default function EventPropagationPage() {
  const location = useLocation()
  const prefillText = location.state?.prefillText
  const [form, setForm] = useState(
    prefillText ? { ...initialForm, nodes: prefillText } : initialForm
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)

  const onChange = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!form.eventName.trim() || !form.origin.trim()) {
      setError('请填写事件名称与起点账号')
      return
    }
    setLoading(true)
    setData(null)
    try {
      const result = await runEventPropagationAnalysis(form)
      setData(result)
    } catch (err) {
      setError(err.message || '请求失败')
    } finally {
      setLoading(false)
    }
  }

  return (
    <ScenarioLayout
      scenario={SCENARIOS.event_propagation}
      input={
        <Section
          title="输入参数"
          action={
            <button type="button" className="btn-ghost text-xs" onClick={() => setForm((s) => ({ ...s, nodes: SAMPLE }))}>
              填入示例
            </button>
          }
        >
          <form className="space-y-3" onSubmit={onSubmit}>
            <FormField label="事件名称 *">
              <TextInput value={form.eventName} onChange={onChange('eventName')} placeholder="如：某行业丑闻事件" />
            </FormField>
            <FormField label="起点账号 / 节点 *">
              <TextInput value={form.origin} onChange={onChange('origin')} />
            </FormField>
            <FormField label="主要发酵渠道">
              <Select value={form.channel} onChange={onChange('channel')}>
                <option>微博</option>
                <option>抖音</option>
                <option>小红书</option>
                <option>知乎</option>
                <option>跨平台</option>
              </Select>
            </FormField>
            <FormField label="时间窗口">
              <Select value={form.timeWindow} onChange={onChange('timeWindow')}>
                <option value="6h">6 小时</option>
                <option value="24h">24 小时</option>
                <option value="7d">7 天</option>
              </Select>
            </FormField>
            <FormField label="已知传播节点（可选）" hint="每行描述一个节点">
              <TextArea value={form.nodes} onChange={onChange('nodes')} rows={7} placeholder={SAMPLE} />
            </FormField>
            <button type="submit" className="btn-primary w-full bg-sand hover:bg-sand-600" disabled={loading}>
              <Icon name="spark" className="w-4 h-4 mr-1.5" />
              {loading ? '推演中…' : '开始分析'}
            </button>
            <div className="text-[11px] text-ink-500 leading-relaxed pt-1">
              将调用 <code className="text-ink-900">POST /api/cogsec/analyze</code>（scenario_type=event_propagation）；时间线优先读取 scenario_extension.propagation。
            </div>
          </form>
        </Section>
      }
      result={<EventPropagationResult data={data} loading={loading} error={error} />}
    />
  )
}
