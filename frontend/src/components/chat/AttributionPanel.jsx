import { useState } from 'react'
import Icon from '../Icon'

const TONE = {
  suspect: {
    wrap: 'from-rose-50 to-white border-rose-100',
    chip: 'bg-rose-100 text-rose-700',
  },
  victim: {
    wrap: 'from-leaf-50 to-white border-leaf-100',
    chip: 'bg-leaf-100 text-leaf-700',
  },
  witness: {
    wrap: 'from-sand-50 to-white border-sand-100',
    chip: 'bg-sand-100 text-sand-700',
  },
  unknown: {
    wrap: 'from-slate-50 to-white border-slate-200',
    chip: 'bg-slate-100 text-ink-500',
  },
}

export default function AttributionPanel({ attribution }) {
  if (!attribution || !Array.isArray(attribution.utterances) || attribution.utterances.length === 0) return null
  return (
    <div className="mt-4 space-y-2">
      <div className="text-[11px] font-medium text-ink-500">发言归属 · 点开卡片看判定理由</div>
      <div className="grid grid-cols-1 gap-2">
        {attribution.utterances.map((item, index) => (
          <ReasonCard key={`${item.speaker}-${index}`} item={item} />
        ))}
      </div>
      {!attribution.victim_present && (
        <div className="text-[11px] text-amber-800 bg-amber-50 border border-amber-100 rounded-2xl px-3 py-2 leading-relaxed">
          本段没有受害人原话。像「我是秦始皇，打钱」这样的输入，会被当成疑似施害者独白，而不是双方已经开始对话。
        </div>
      )}
    </div>
  )
}

function ReasonCard({ item }) {
  const [open, setOpen] = useState(false)
  const tone = TONE[item.speaker] || TONE.unknown
  return (
    <button
      type="button"
      onClick={() => setOpen((value) => !value)}
      className={`text-left rounded-2xl border bg-gradient-to-r ${tone.wrap} px-3.5 py-3 transition-all hover:-translate-y-0.5 hover:shadow-card`}
    >
      <div className="flex items-start gap-3">
        <span className={`text-[10px] font-semibold px-2 py-0.5 rounded-full ${tone.chip}`}>{item.speaker_label}</span>
        <div className="min-w-0 flex-1">
          <div className="text-sm text-ink-900 leading-relaxed">{item.text}</div>
          <div className="mt-1.5 text-[11px] text-brand underline decoration-brand/30 underline-offset-2">
            {open ? '收起判定理由' : '查看这段为什么这样切分'}
          </div>
          {open && (
            <div className="mt-2 rounded-xl bg-white/80 border border-black/5 px-3 py-2 text-xs leading-relaxed text-ink-500">
              {item.reason}
              {item.evidence ? ` 依据：${item.evidence}` : ''}
              {typeof item.confidence === 'number' ? ` 把握 ${Math.round(item.confidence * 100)}%。` : ''}
            </div>
          )}
        </div>
        <Icon name="arrow-right" className={`w-4 h-4 mt-0.5 shrink-0 text-ink-300 transition-transform ${open ? 'rotate-90' : ''}`} />
      </div>
    </button>
  )
}
