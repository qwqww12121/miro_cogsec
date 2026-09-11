import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { SCENARIOS } from '../../scenarios/config'
import ScenarioLayout from '../../components/ScenarioLayout'
import Section from '../../components/Section'
import { FormField, TextInput, Select } from '../../components/FormField'
import Icon from '../../components/Icon'
import Spinner from '../../components/Spinner'
import { runPublicOpinionAnalysis } from '../../api/scenarios'
import { fetchOasisRuntimeStatus, oasisLoadingCopy } from '../../api/cogsec'
import PublicOpinionResult from '../../components/results/PublicOpinionResult'
import PlainViewWrapper from '../../components/results/PlainViewWrapper'
import AnalysisAnswer from '../../components/results/AnalysisAnswer'
import MultimodalComposer from '../../components/MultimodalComposer'
import AnalysisJumpCards from '../../components/AnalysisJumpCards'
import { loadWorkspace, saveWorkspace } from '../../lib/scenarioWorkspace'
import { composePublicOpinionText } from '../../lib/platformContext'

const PO_PLATFORMS = ['微博', '抖音', '小红书', '知乎', '多平台聚合']

// Backend classify response has no structured extracted_fields today, so
// platform is matched against the pasted text + summary as a fallback.
// topic is free-form and has no reliable keyword heuristic — left on
// extractedFields only, ready for when the backend adds structured
// extraction, but not guessed client-side to avoid showing something
// wrong/misleading on stage.
function matchPlatform(text) {
  if (!text) return ''
  const hits = PO_PLATFORMS.filter((platform) => platform !== '多平台聚合' && text.includes(platform))
  if (hits.length > 1) return '多平台聚合'
  if (hits.length === 1) return hits[0]
  return ''
}

const initialForm = {
  platform: '微博',
  topic: '',
  timeWindow: '24h',
  samples: '',
  attachments: [],
}

const SAMPLE = `1. 看了这次官方回应，根本没回应核心问题
2. 这种营销方式真的太恶心了，必须维权
3. 我已经在准备投诉材料了
4. 哥几个去黑猫投诉啊
5. 我之前买了，体验确实很差`

export default function PublicOpinionPage() {
  const location = useLocation()
  const sessionId = location.state?.sessionId || 'local'
  const cached = useMemo(() => loadWorkspace('public_opinion', sessionId), [sessionId])
  const prefillText = location.state?.prefillText ?? ''
  const extractedFields = location.state?.extractedFields || {}
  const extractedSummary = location.state?.extractedSummary || ''
  const matchSource = `${prefillText}\n${extractedSummary}`
  const prefillChanged = Boolean(prefillText && cached?.form?.samples && prefillText.trim() !== String(cached.form.samples || '').trim())

  const [form, setForm] = useState(() => {
    const base = { ...initialForm, ...(cached?.form || {}), attachments: [] }
    if (prefillText) base.samples = prefillText
    const platform = matchPlatform(extractedFields.platform) || matchPlatform(matchSource)
    if (platform) base.platform = platform
    if (extractedFields.topic) base.topic = extractedFields.topic
    else if (prefillText) {
      const heading = prefillText.match(/^#+\s*(.+)$/m)
      if (heading) base.topic = heading[1].slice(0, 40)
      else if (/食堂/.test(prefillText) && /涨价/.test(prefillText)) base.topic = '食堂涨价'
      else if (!base.topic) base.topic = prefillText.replace(/\s+/g, ' ').slice(0, 24)
    }
    return base
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(() => (prefillChanged ? null : (cached?.data || null)))
  const [oasisStatus, setOasisStatus] = useState(null)
  const autoStarted = useRef(false)
  const analysisText = useMemo(() => composePublicOpinionText(form), [form])

  const onChange = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))
  const onFilesChange = (attachments) => setForm((s) => ({ ...s, attachments }))
  const onRemoveFile = (index) => setForm((s) => ({ ...s, attachments: s.attachments.filter((_, i) => i !== index) }))

  const analyze = async (payload) => {
    setError(null)
    if (!payload.topic.trim() || (!payload.samples.trim() && !payload.attachments.length)) {
      setError('请填写话题，并输入样本内容或添加文件/语音')
      return
    }
    setLoading(true)
    setData(null)
    try {
      const result = await runPublicOpinionAnalysis(payload)
      setData(result)
      saveWorkspace('public_opinion', sessionId, { form: payload, data: result })
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
    saveWorkspace('public_opinion', sessionId, { form, data })
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
              <TextInput value={form.topic} onChange={onChange('topic')} placeholder="从材料里概括，不要沿用示例话题" />
            </FormField>
            <FormField label="时间窗口">
              <Select value={form.timeWindow} onChange={onChange('timeWindow')}>
                <option value="6h">最近 6 小时</option>
                <option value="24h">最近 24 小时</option>
                <option value="7d">最近 7 天</option>
              </Select>
            </FormField>
            <FormField label="样本文本 *" hint="每行一条评论 / 帖文">
              <MultimodalComposer
                value={form.samples}
                onChange={onChange('samples')}
                files={form.attachments}
                onFilesChange={onFilesChange}
                onRemoveFile={onRemoveFile}
                loading={loading}
                rows={9}
                accent="leaf"
                placeholder={SAMPLE}
              />
            </FormField>
            <button type="submit" className="btn-primary w-full bg-leaf hover:bg-leaf-600" disabled={loading}>
              {loading ? <Spinner className="w-4 h-4 mr-1.5" /> : <Icon name="spark" className="w-4 h-4 mr-1.5" />}
              {loading ? '分析中…' : '开始分析'}
            </button>
            {loading && (
              <div className="rounded-lg bg-leaf-50 border border-leaf-100 px-3 py-2.5 mt-2 flex items-start gap-2">
                <Spinner className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                <span className="text-xs text-leaf-600 leading-relaxed">
                  {oasisLoadingCopy(oasisStatus, { agents: 50 })}
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
          <AnalysisAnswer data={data} inputText={analysisText} scenarioType="public_opinion" />
          <PlainViewWrapper data={data} scenarioType="public_opinion">
            <PublicOpinionResult data={data} loading={loading} error={error} platform={form.platform} timeWindow={form.timeWindow} inputText={analysisText} />
          </PlainViewWrapper>
          <AnalysisJumpCards scenarioType="public_opinion" data={data} inputText={analysisText} sessionId={sessionId} />
        </div>
      }
    />
  )
}
