import InfoHint from './InfoHint'

/**
 * 单个指标卡片。
 * prominence 控制视觉层级，让核心结论明显优先于技术性能指标：
 *  - 'headline' : 核心结论性（大字号、tone 着色）
 *  - 'normal'   : 常规业务指标（默认）
 *  - 'muted'    : 技术性能类（小字号、灰化，视觉次要）
 * info 传入术语解释时，标签旁出现可悬浮的信息图标。
 * details 传入真实明细后，鼠标移入卡片会在同宽位置展开详情。
 */
export default function StatTile({
  label,
  value,
  hint,
  tone = 'default',
  prominence = 'normal',
  info,
  details,
}) {
  const toneClasses = {
    default: 'text-ink-900',
    brand: 'text-brand',
    leaf: 'text-leaf',
    sand: 'text-sand',
    danger: 'text-rose-500',
  }

  const sizeClass =
    prominence === 'headline' ? 'text-3xl' : prominence === 'muted' ? 'text-base' : 'text-xl'
  const valueColor = prominence === 'muted' ? 'text-ink-500' : toneClasses[tone]
  const cardClass =
    prominence === 'muted' ? 'card p-3 bg-slate-50 border-border' : 'card p-4'
  const labelWrap =
    prominence === 'muted' ? 'text-[10px] text-ink-300' : 'text-[11px] text-ink-500'

  return (
    <div className="group relative min-w-0">
      <div className={cardClass}>
        <div className={`flex items-center gap-1 ${labelWrap}`}>
          <span>{label}</span>
          {info && <InfoHint text={info} />}
        </div>
        <div className={`mt-1 font-semibold ${sizeClass} ${valueColor}`}>{value}</div>
        {hint && <div className="text-[11px] text-ink-300 mt-1">{hint}</div>}
      </div>
      {details && (
        <div className="pointer-events-none absolute left-0 right-0 top-[calc(100%+0.5rem)] z-30 translate-y-1 opacity-0 transition duration-150 group-hover:pointer-events-auto group-hover:translate-y-0 group-hover:opacity-100 group-focus-within:pointer-events-auto group-focus-within:translate-y-0 group-focus-within:opacity-100">
          <div className="rounded-xl border border-border bg-white p-4 shadow-xl ring-1 ring-black/5">
            <div className="mb-2 text-[11px] font-medium text-ink-500">{label} · 详细数据</div>
            {details}
          </div>
        </div>
      )}
    </div>
  )
}
