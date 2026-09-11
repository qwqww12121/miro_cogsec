import { describeTraceEvent } from '../../lib/humanizeSim'
import { isInternalSkipCopy } from '../../lib/hideInternalSkipCopy'

export default function AgentTracePanel({ events = [], title = '', scenario = '' }) {
  const visible = (Array.isArray(events) ? events : []).filter((event) => (
    !event?.skipped && !isInternalSkipCopy(event?.action) && !isInternalSkipCopy(event?.content)
  ))
  if (!visible.length) return null
  return (
    <div>
      {title ? <div className="px-4 pt-3 text-xs font-semibold text-ink-900">{title}</div> : null}
      <div className="trace-list max-h-56 overflow-y-auto divide-y divide-border/70">
        {visible.map((event, index) => {
          const view = describeTraceEvent(event, scenario)
          return (
            <div key={`${view.time}-${index}`} className="px-4 py-2.5 text-xs leading-relaxed text-ink-900">
              <div className="flex gap-2 text-[11px] text-ink-400">
                <span className="font-mono">{view.time || `--:${String(index + 1).padStart(2, '0')}`}</span>
                <span>{view.actor}</span>
                {view.target && <span>→ {view.target}</span>}
              </div>
              {view.headline && <div className="mt-1 font-medium">{view.headline}</div>}
              <div className="mt-1 text-ink-500">{view.meaning}</div>
              {view.amplify ? <div className="mt-0.5 text-[11px] text-ink-400">扩大 / 标记：{view.amplify}</div> : null}
            </div>
          )
        })}
      </div>
    </div>
  )
}
