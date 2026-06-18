import Breadcrumbs from './Breadcrumbs'
import { THEME_CLASSES } from '../scenarios/config'

export default function ScenarioLayout({ scenario, input, result }) {
  const theme = THEME_CLASSES[scenario.theme]
  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <Breadcrumbs
        items={[
          { label: '首页', to: '/' },
          { label: '场景分析' },
          { label: scenario.name },
        ]}
      />
      <div className="mt-3 mb-5 flex items-center gap-3">
        <h1 className="text-xl font-semibold text-ink-900">{scenario.name}</h1>
        <span className={`tag ${theme.chip}`}>{scenario.short}</span>
        <span className="text-xs text-ink-500">{scenario.description}</span>
      </div>
      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
        <aside className="space-y-4">{input}</aside>
        <section className="space-y-4 min-w-0">{result}</section>
      </div>
    </div>
  )
}
