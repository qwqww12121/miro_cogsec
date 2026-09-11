import { useState } from 'react'
import Icon from '../Icon'
import MiniConstellation from './MiniConstellation'

export default function ThinkingFold({ steps = [], defaultOpen = false }) {
  if (!steps.length) return null
  return (
    <div className="mt-1 mb-4 space-y-1.5">
      {steps.map((step) => (
        <FoldRow key={step.id || step.title} step={step} defaultOpen={defaultOpen} />
      ))}
    </div>
  )
}

function FoldRow({ step, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen)
  const details = (step.details || []).filter(Boolean)
  return (
    <div className="rounded-xl border border-slate-200/80 bg-slate-50/90 overflow-hidden">
      <button type="button" onClick={() => setOpen((value) => !value)} className="w-full flex items-center gap-2 px-3 py-2 text-left">
        <span className={`w-1.5 h-1.5 rounded-full ${open ? 'bg-brand' : 'bg-ink-300'}`} />
        <span className="flex-1 text-xs font-medium text-ink-900">{open ? '已完成 · ' : ''}{step.title}</span>
        <span className="text-[11px] text-ink-500 truncate max-w-[52%]">{open ? '' : step.summary}</span>
        <Icon name="chevron-down" className={`w-3.5 h-3.5 text-ink-500 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>
      {open && (
        <div className="px-3 pb-3 pt-0">
          {step.summary && <p className="text-xs text-ink-500 leading-relaxed">{step.summary}</p>}
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
