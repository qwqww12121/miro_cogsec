import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { classifyScenario, LOW_CONFIDENCE_THRESHOLD } from '../api/classify'
import { SCENARIOS, THEME_CLASSES } from '../scenarios/config'
import Icon from './Icon'
import Spinner from './Spinner'

export default function IntelligentClassifier() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const onClassify = async () => {
    const trimmed = text.trim()
    if (!trimmed) {
      setError('请先粘贴待识别内容')
      return
    }
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const data = await classifyScenario(trimmed)
      setResult(data)
    } catch (err) {
      setError(err.message || '识别失败')
    } finally {
      setLoading(false)
    }
  }

  const onEnterScenario = () => {
    const scenario = result && SCENARIOS[result.scenario_type]
    if (!scenario) return
    navigate(scenario.path, {
      state: {
        prefillText: text,
        extractedFields: result.extracted_fields || {},
      },
    })
  }

  const scenario = result ? SCENARIOS[result.scenario_type] : null
  const theme = scenario ? THEME_CLASSES[scenario.theme] : null

  return (
    <div>
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-ink-900">智能识别</h2>
        <p className="text-xs text-ink-500 mt-1">粘贴内容，自动判断场景</p>
      </div>

      <textarea
        className="input-base resize-none leading-relaxed font-mono text-[13px]"
        rows={8}
        placeholder="粘贴对话记录、舆情文本或事件描述..."
        value={text}
        onChange={(e) => setText(e.target.value)}
      />

      <button
        type="button"
        className="btn-primary mt-3"
        onClick={onClassify}
        disabled={loading}
      >
        {loading ? <Spinner className="w-4 h-4 mr-1.5" /> : <Icon name="spark" className="w-4 h-4 mr-1.5" />}
        {loading ? '识别中…' : '开始识别'}
      </button>

      <div className="mt-4">
        {loading && <ClassifierLoading />}
        {error && !loading && <ClassifierError message={error} />}
        {result && !loading && (
          <ClassifierResult
            scenario={scenario}
            theme={theme}
            confidence={result.confidence}
            reason={result.reason}
            extractedSummary={result.extracted_summary}
            model={result.model}
            onEnter={onEnterScenario}
          />
        )}
        {!loading && !error && !result && <ClassifierPlaceholder />}
      </div>
    </div>
  )
}

function ClassifierPlaceholder() {
  return (
    <div className="card border-dashed py-6 px-4 text-center">
      <div className="text-xs text-ink-500">识别结果将显示在这里</div>
    </div>
  )
}

function ClassifierLoading() {
  return (
    <div className="card py-6 px-4 flex items-center gap-3">
      <span className="w-2 h-2 rounded-full bg-brand animate-pulse" />
      <span className="text-sm text-ink-500">正在分析文本特征…</span>
    </div>
  )
}

function ClassifierError({ message }) {
  return (
    <div className="rounded-lg bg-rose-50 border border-rose-100 text-rose-600 text-sm px-3 py-2 flex items-start gap-2">
      <Icon name="alert" className="w-4 h-4 mt-0.5 flex-none" />
      <div>{message}</div>
    </div>
  )
}

function ClassifierResult({
  scenario,
  theme,
  confidence,
  reason,
  extractedSummary,
  model,
  onEnter,
}) {
  const pct = Math.round((confidence ?? 0) * 100)
  const lowConfidence = confidence != null && confidence < LOW_CONFIDENCE_THRESHOLD

  if (lowConfidence) {
    return <LowConfidenceCard pct={pct} reason={reason} extractedSummary={extractedSummary} />
  }

  if (!scenario || !theme) return null
  return (
    <div className={`card p-4 ${theme.border}`}>
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className={`w-7 h-7 rounded-md ${theme.bg} ${theme.accent} flex items-center justify-center`}>
            <Icon name={scenario.icon} className="w-4 h-4" />
          </div>
          <div className="text-sm">
            <span className="text-ink-500">已识别为：</span>
            <span className="font-semibold text-ink-900">{scenario.name}</span>
          </div>
        </div>
        <span className={`tag ${theme.chip}`}>置信度 {pct}%</span>
      </div>

      <div className="mt-2 bg-slate-100 rounded-full h-1.5 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: theme.bar }}
        />
      </div>

      <ExtractedSummaryBlock extractedSummary={extractedSummary} model={model} theme={theme} />

      <div className="mt-3 text-sm text-ink-900 leading-relaxed">
        <span className="text-ink-500 text-xs mr-1">理由：</span>
        {reason}
      </div>

      <button
        type="button"
        className="btn-primary mt-4 w-full"
        style={{ background: theme.bar }}
        onClick={onEnter}
      >
        进入分析
        <Icon name="arrow-right" className="w-4 h-4 ml-1" />
      </button>
    </div>
  )
}

// 低置信度卡片：信息不足时不强行把用户导进某个具体场景，
// 但仍展示 reason 与 extracted_summary，让用户看到系统理解到了什么。
function LowConfidenceCard({ pct, reason, extractedSummary }) {
  return (
    <div className="card p-4 border-dashed border-ink-300">
      <div className="flex items-center justify-between gap-3 mb-2">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-slate-100 text-ink-500 flex items-center justify-center">
            <Icon name="alert" className="w-4 h-4" />
          </div>
          <div className="text-sm">
            <span className="font-semibold text-ink-900">信息不足，暂无法可靠判断场景</span>
          </div>
        </div>
        <span className="tag bg-slate-100 text-ink-500">置信度 {pct}%（偏低）</span>
      </div>

      <div className="mt-2 bg-slate-100 rounded-full h-1.5 overflow-hidden">
        <div className="h-full rounded-full bg-ink-300 transition-all" style={{ width: `${pct}%` }} />
      </div>

      <ExtractedSummaryBlock extractedSummary={extractedSummary} />

      <div className="mt-3 text-sm text-ink-900 leading-relaxed">
        <span className="text-ink-500 text-xs mr-1">理由：</span>
        {reason}
      </div>

      <div className="mt-4 text-xs text-ink-500 leading-relaxed">
        建议补充更多上下文（对话原文、传播过程或事件细节）后再次识别。
      </div>
    </div>
  )
}

// 从用户模糊输入里提炼出的关键线索摘要，让用户看到"系统理解到了什么"。
function ExtractedSummaryBlock({ extractedSummary, model, theme }) {
  if (!extractedSummary) return null
  const accentClass = theme ? theme.accent : 'text-ink-500'
  return (
    <div className="mt-3 rounded-lg bg-slate-50 border border-slate-100 px-3 py-2.5">
      <div className={`flex items-center gap-1.5 text-xs font-medium ${accentClass}`}>
        <Icon name="spark" className="w-3.5 h-3.5" />
        系统理解到的关键线索
        {model && <span className="text-ink-500 font-normal">· {model}</span>}
      </div>
      <div className="mt-1 text-sm text-ink-900 leading-relaxed">{extractedSummary}</div>
    </div>
  )
}
