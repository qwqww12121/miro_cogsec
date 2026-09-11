import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { SCENARIOS } from '../../scenarios/config'
import ScenarioLayout from '../../components/ScenarioLayout'
import Section from '../../components/Section'
import { FormField, TextInput, Select } from '../../components/FormField'
import Icon from '../../components/Icon'
import Spinner from '../../components/Spinner'
import { runEventPropagationAnalysis } from '../../api/scenarios'
import { fetchOasisRuntimeStatus, oasisLoadingCopy } from '../../api/cogsec'
import EventPropagationResult from '../../components/results/EventPropagationResult'
import PlainViewWrapper from '../../components/results/PlainViewWrapper'
import AnalysisAnswer from '../../components/results/AnalysisAnswer'
import MultimodalComposer from '../../components/MultimodalComposer'
import AnalysisJumpCards from '../../components/AnalysisJumpCards'
import { loadWorkspace, saveWorkspace } from '../../lib/scenarioWorkspace'
import { composeEventPropagationText } from '../../lib/platformContext'

const EP_CHANNELS = ['微博', '抖音', '小红书', '知乎', '跨平台']

// Backend classify response has no structured extracted_fields today, so
// channel is matched against the pasted text + summary as a fallback.
// event_name / origin are free-form short text with no reliable keyword
// heuristic — left on extractedFields only, ready for when the backend
// adds structured extraction, but not guessed client-side to avoid
// showing something wrong/misleading on stage.
function matchChannel(text) {
  if (!text) return ''
  const hits = EP_CHANNELS.filter((channel) => channel !== '跨平台' && text.includes(channel))
  if (hits.length > 1) return '跨平台'
  if (hits.length === 1) return hits[0]
  if (text.includes('、') || text.includes(',') || text.includes('，')) return '跨平台'
  return ''
}

const initialForm = {
  eventName: '',
  origin: '',
  timeWindow: '24h',
  channel: '微博',
  nodes: '',
  attachments: [],
}

const SAMPLE = `节点A: @学生论坛账号 - 转发原始爆料
节点B: @行业大V - 二次解读引发话题升级
节点C: @教育媒体官方账号 - 跟进报道
节点D: 跨平台扩散至抖音 / 知乎`

export default function EventPropagationPage() {
  const location = useLocation()
  const sessionId = location.state?.sessionId || 'local'
  const cached = useMemo(() => loadWorkspace('event_propagation', sessionId), [sessionId])
  const prefillText = location.state?.prefillText ?? ''
  const extractedFields = location.state?.extractedFields || {}
  const extractedSummary = location.state?.extractedSummary || ''
  const matchSource = `${prefillText}\n${extractedSummary}`
  const prefillChanged = Boolean(prefillText && cached?.form?.nodes && prefillText.trim() !== String(cached.form.nodes || '').trim())

  const [form, setForm] = useState(() => {
    const base = { ...initialForm, ...(cached?.form || {}), attachments: [] }
    if (prefillText) base.nodes = prefillText
    if (extractedFields.event_name) base.eventName = extractedFields.event_name
    else if (prefillText) {
      const heading = prefillText.match(/^#+\s*(.+)$/m)
      if (heading) base.eventName = heading[1].slice(0, 40)
      else if (!base.eventName) base.eventName = prefillText.replace(/\s+/g, ' ').slice(0, 24)
    }
    if (extractedFields.origin) base.origin = extractedFields.origin
    else if (prefillText && !base.origin) base.origin = '材料未标明起点'
    const channel = matchChannel(extractedFields.channels) || matchChannel(matchSource)
    if (channel) base.channel = channel
    return base
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(() => (prefillChanged ? null : (cached?.data || null)))
  const [oasisStatus, setOasisStatus] = useState(null)
  const autoStarted = useRef(false)
  const analysisText = useMemo(() => composeEventPropagationText(form), [form])

  const onChange = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))
  const onFilesChange = (attachments) => setForm((s) => ({ ...s, attachments }))
  const onRemoveFile = (index) => setForm((s) => ({ ...s, attachments: s.attachments.filter((_, i) => i !== index) }))

  const analyze = async (payload) => {
    setError(null)
    if (!payload.eventName.trim() || !payload.origin.trim()) {
      setError('请填写事件名称与起点账号')
      return
    }
    setLoading(true)
    setData(null)
    try {
      const result = await runEventPropagationAnalysis(payload)
      setData(result)
      saveWorkspace('event_propagation', sessionId, { form: payload, data: result })
    } catch (err) {
      setError(err.message || '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const onSubmit = (e) => {
    e.preventDefault()
    analyze(form)
  }

  useEffect(() => {
    saveWorkspace('event_propagation', sessionId, { form, data })
  }, [form, data, sessionId])

  useEffect(() => {
    fetchOasisRuntimeStatus().then(setOasisStatus).catch(() => setOasisStatus({ ready: false }))
  }, [])

  useEffect(() => {
    if (autoStarted.current) return
    if (data) return
    if (!prefillText) return
    autoStarted.current = true
    analyze(form)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

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
              <MultimodalComposer
                value={form.nodes}
                onChange={onChange('nodes')}
                files={form.attachments}
                onFilesChange={onFilesChange}
                onRemoveFile={onRemoveFile}
                loading={loading}
                rows={7}
                accent="sand"
                placeholder={SAMPLE}
              />
            </FormField>
            <button type="submit" className="btn-primary w-full bg-sand hover:bg-sand-600" disabled={loading}>
              {loading ? <Spinner className="w-4 h-4 mr-1.5" /> : <Icon name="spark" className="w-4 h-4 mr-1.5" />}
              {loading ? '推演中…' : '开始分析'}
            </button>
            {loading && (
              <div className="rounded-lg bg-sand-50 border border-sand-100 px-3 py-2.5 mt-2 flex items-start gap-2">
                <Spinner className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span className="text-xs text-sand-600 leading-relaxed">
                  {oasisLoadingCopy(oasisStatus, { agents: 60 })}
                </span>
              </div>
            )}
            <div className="text-[11px] text-ink-500 leading-relaxed pt-1">
              结果包含对照路径、传播关系与干预处方。
            </div>
          </form>
        </Section>
      }
      result={
        <div className="space-y-4">
          <AnalysisAnswer data={data} inputText={analysisText} scenarioType="event_propagation" />
          <PlainViewWrapper data={data} scenarioType="event_propagation">
            <EventPropagationResult data={data} loading={loading} error={error} channel={form.channel} timeWindow={form.timeWindow} inputText={analysisText} />
          </PlainViewWrapper>
          <AnalysisJumpCards scenarioType="event_propagation" data={data} inputText={analysisText} sessionId={sessionId} />
        </div>
      }
    />
  )
}
