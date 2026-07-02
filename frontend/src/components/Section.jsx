import InfoHint from './InfoHint'

export default function Section({ title, action, info, children, className = '' }) {
  return (
    <div className={`card p-5 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink-900 flex items-center gap-1">
          {title}
          {info && <InfoHint text={info} />}
        </h3>
        {action}
      </div>
      {children}
    </div>
  )
}
