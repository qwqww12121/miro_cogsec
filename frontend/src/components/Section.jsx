export default function Section({ title, action, children, className = '' }) {
  return (
    <div className={`card p-5 ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-ink-900">{title}</h3>
        {action}
      </div>
      {children}
    </div>
  )
}
