import InfoHint from './InfoHint'

/**
 * 单个指标卡片。
 * prominence 控制视觉层级，让核心结论明显优先于技术性能指标：
 *  - 'headline' : 核心结论性（大字号、tone 着色）
 *  - 'normal'   : 常规业务指标（默认）
 *  - 'muted'    : 技术性能类（小字号、灰化，视觉次要）
 * info 传入术语解释时，标签旁出现可悬浮的信息图标。
 */
export default function StatTile({
  label,
  value,
  hint,
  tone = 'default',
  prominence = 'normal',
  info,
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
    <div className={cardClass}>
      <div className={`flex items-center gap-1 ${labelWrap}`}>
        <span>{label}</span>
        {info && <InfoHint text={info} />}
      </div>
      <div className={`mt-1 font-semibold ${sizeClass} ${valueColor}`}>{value}</div>
      {hint && <div className="text-[11px] text-ink-300 mt-1">{hint}</div>}
    </div>
  )
}
