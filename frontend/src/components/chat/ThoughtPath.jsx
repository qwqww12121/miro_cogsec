import { useEffect, useState } from 'react'
import Icon from '../Icon'
import MiniConstellation from './MiniConstellation'
import { isInternalSkipCopy, stripInternalSkipCopy } from '../../lib/hideInternalSkipCopy'

const LIVE_STEPS = [
  { id: 'split', title: '正在切分对话双方' },
  { id: 'role', title: '正在判定发言归属' },
  { id: 'scene', title: '正在识别场景' },
  { id: 'graph', title: '正在整理本轮线索' },
]

export default function ThoughtPath({ steps = [], running = false, durationMs = 0 }) {
  const [open, setOpen] = useState(true)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    if (!running) return undefined
    const started = Date.now()
    const timer = setInterval(() => setElapsed(Date.now() - started), 200)
    return () => clearInterval(timer)
  }, [running])

  if (!running && !steps.length) return null

  const expanded = running || open
  const label = running
    ? `思考过程 · ${formatDuration(elapsed)}`
    : `思考过程 · ${formatDuration(durationMs)}`
  const rows = running ? LIVE_STEPS : steps.filter((step) => !isInternalSkipCopy(step?.title) && !isInternalSkipCopy(step?.summary))

  return (
    <div className="mb-4">
      <button
        type="button"
        onClick={() => !running && setOpen((value) => !value)}
        className="flex items-center gap-2 text-[13px] text-ink-500 hover:text-ink-900"
      >
        <Icon name="chevron-down" className={`w-3.5 h-3.5 transition-transform ${expanded ? '' : '-rotate-90'}`} />
        <span className="font-medium">{label}</span>
        {running && <span className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse" />}
      </button>
      {expanded && (
        <div className="mt-2 pl-1 space-y-1.5">
          {rows.map((step, index) => (
            <ThoughtStep key={step.id || step.title} step={step} running={running} index={index} />
          ))}
        </div>
      )}
    </div>
  )
}

function ThoughtStep({ step, running, index }) {
  const [open, setOpen] = useState(!running)
  const details = stripInternalSkipCopy(step.details || []).filter(Boolean)
  const summary = stripInternalSkipCopy(step.summary)
  const hasBody = Boolean(summary || details.length || step.graph)
  if (running) {
    return (
      <div className="rounded-xl border border-border bg-white px-3 py-2 text-xs text-ink-500 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse" style={{ animationDelay: `${index * 120}ms` }} />
        {step.title}…
      </div>
    )
  }
  return (
    <div className="rounded-xl border border-slate-200/80 bg-slate-50/90 overflow-hidden">
      <button type="button" onClick={() => hasBody && setOpen((value) => !value)} className="w-full flex items-center gap-2 px-3 py-2 text-left">
        <span className="w-1.5 h-1.5 rounded-full bg-brand" />
        <span className="flex-1 text-xs font-medium text-ink-900">{step.title}</span>
        {!open && summary && <span className="text-[11px] text-ink-500 truncate max-w-[52%]">{summary}</span>}
        {hasBody && <Icon name="chevron-down" className={`w-3.5 h-3.5 text-ink-500 transition-transform ${open ? 'rotate-180' : ''}`} />}
      </button>
      {open && hasBody && (
        <div className="px-3 pb-3">
          {summary && <p className="text-xs text-ink-500 leading-relaxed">{summary}</p>}
          {details.length > 0 && (
            <div className="mt-2 space-y-1">
              {details.map((item) => (
                <div key={item} className="text-xs text-ink-900 leading-relaxed pl-2 border-l-2 border-brand-100">{item}</div>
              ))}
            </div>
          )}
          {step.graph && <MiniConstellation graph={step.graph} />}
        </div>
      )}
    </div>
  )
}

function formatDuration(ms) {
  const seconds = Math.max(0, Number(ms) || 0) / 1000
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} 秒`
  const minutes = Math.floor(seconds / 60)
  const rest = Math.round(seconds % 60)
  return `${minutes} 分 ${rest} 秒`
}
