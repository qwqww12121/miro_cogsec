import { describeAnomaly } from '../scenarios/glossary'

/**
 * 异常信号标签：主展示中文短语，hover 显示后端英文原名（小字补充）。
 * 未知名仍原样展示（不会让页面崩），只是没有 hover 译文。
 */
export default function AnomalyTag({ raw }) {
  const { label, original, known } = describeAnomaly(raw)
  if (!known) {
    return <span className="tag bg-rose-50 text-rose-600">{label}</span>
  }
  return (
    <span className="relative inline-flex group/anom">
      <span className="tag bg-rose-50 text-rose-600 cursor-help underline decoration-dotted underline-offset-2">
        {label}
      </span>
      <span className="pointer-events-none absolute left-0 top-full mt-1 z-30 hidden group-hover/anom:block group-focus-within/anom:block">
        <span className="block rounded-md bg-ink-900 px-2 py-1 text-[10px] leading-tight text-white whitespace-nowrap shadow-card">
          后端标记：{original}
        </span>
      </span>
    </span>
  )
}
