import Icon from './Icon'

export default function Empty({ title = '暂无结果', hint }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="w-12 h-12 rounded-full bg-slate-100 text-ink-300 flex items-center justify-center mb-3">
        <Icon name="spark" className="w-5 h-5" />
      </div>
      <div className="text-sm font-medium text-ink-900">{title}</div>
      {hint && <div className="text-xs text-ink-500 mt-1 max-w-xs">{hint}</div>}
    </div>
  )
}
