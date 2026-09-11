import { Link } from 'react-router-dom'
import { THEME_CLASSES } from '../scenarios/config'
import Icon from './Icon'

export default function ScenarioCard({ scenario, compact = false }) {
  const theme = THEME_CLASSES[scenario.theme]

  if (compact) {
    return (
      <Link
        to={scenario.path}
        className={`card-hoverable px-4 py-3.5 flex items-center gap-3.5 focus:outline-none focus:ring-2 ${theme.ring}`}
      >
        <div className={`w-9 h-9 rounded-lg ${theme.bg} ${theme.accent} flex items-center justify-center flex-none`}>
          <Icon name={scenario.icon} className="w-4 h-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-1.5">
            <h3 className="text-sm font-semibold text-ink-900 truncate">{scenario.name}</h3>
            <span className={`tag ${theme.chip} text-[10px]`}>{scenario.short}</span>
          </div>
          <p className="text-xs text-ink-500 mt-0.5 line-clamp-1">{scenario.description}</p>
        </div>
        <Icon name="arrow-right" className={`w-4 h-4 flex-none ${theme.accent}`} />
      </Link>
    )
  }

  return (
    <Link
      to={scenario.path}
      className={`card-hoverable p-6 flex flex-col h-full focus:outline-none focus:ring-2 ${theme.ring}`}
    >
      <div className={`w-11 h-11 rounded-lg ${theme.bg} ${theme.accent} flex items-center justify-center mb-4`}>
        <Icon name={scenario.icon} className="w-5 h-5" />
      </div>
      <div className="flex items-baseline gap-2 mb-1.5">
        <h3 className="text-base font-semibold text-ink-900">{scenario.name}</h3>
        <span className={`tag ${theme.chip}`}>{scenario.short}</span>
      </div>
      <p className="text-sm text-ink-500 leading-relaxed flex-1">{scenario.description}</p>
      <div className={`mt-4 inline-flex items-center text-sm font-medium ${theme.accent}`}>
        进入分析
        <Icon name="arrow-right" className="w-4 h-4 ml-1" />
      </div>
    </Link>
  )
}
