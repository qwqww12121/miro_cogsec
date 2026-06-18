export default function StatTile({ label, value, hint, tone = 'default' }) {
  const toneClasses = {
    default: 'text-ink-900',
    brand: 'text-brand',
    leaf: 'text-leaf',
    sand: 'text-sand',
    danger: 'text-rose-500',
  }
  return (
    <div className="card p-4">
      <div className="text-[11px] text-ink-500">{label}</div>
      <div className={`mt-1 text-xl font-semibold ${toneClasses[tone]}`}>{value}</div>
      {hint && <div className="text-[11px] text-ink-500 mt-1">{hint}</div>}
    </div>
  )
}
