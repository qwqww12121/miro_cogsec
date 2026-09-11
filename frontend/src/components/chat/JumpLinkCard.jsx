import { Link } from 'react-router-dom'
import { THEME_CLASSES } from '../../scenarios/config'
import Icon from '../Icon'

export default function JumpLinkCard({ icon, title, description, tone = 'brand', to, state }) {
  const theme = THEME_CLASSES[tone] || THEME_CLASSES.brand
  return (
    <Link
      to={to}
      state={state}
      className={`group flex items-center gap-3 rounded-2xl border ${theme.border} bg-white/90 px-3.5 py-3 transition-all duration-200 hover:-translate-y-0.5 hover:shadow-cardHover`}
    >
      <div className={`w-9 h-9 rounded-xl ${theme.bg} ${theme.accent} flex items-center justify-center shrink-0`}>
        <Icon name={icon} className="w-4 h-4" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="text-sm font-semibold text-ink-900">{title}</div>
        {description && <div className="mt-0.5 text-xs text-ink-500 leading-relaxed">{description}</div>}
      </div>
      <Icon name="arrow-right" className={`w-4 h-4 ${theme.accent} shrink-0 transition-transform duration-200 group-hover:translate-x-1`} />
    </Link>
  )
}
