import ExpandableFrame from './ExpandableFrame'
import InfoHint from './InfoHint'

export default function Section({ title, action, info, hint, children, className = '', expandable = false, size = 'lg', trigger = 'card' }) {
  if (expandable) {
    return (
      <ExpandableFrame title={title} hint={hint || (typeof info === 'string' ? info : '')} size={size} className={className} trigger={trigger}>
        <div className="p-5" onClick={(event) => event.stopPropagation()}>
          {info && typeof info !== 'string' ? <div className="mb-3"><InfoHint text={info} /></div> : null}
          {action ? <div className="mb-3 flex justify-end">{action}</div> : null}
          {children}
        </div>
      </ExpandableFrame>
    )
  }
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
