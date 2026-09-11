import { useEffect, useState } from 'react'
import Breadcrumbs from './Breadcrumbs'
import { THEME_CLASSES } from '../scenarios/config'

export default function ScenarioLayout({ scenario, input, result }) {
  const [expanded, setExpanded] = useState(false)
  const theme = THEME_CLASSES[scenario.theme]

  useEffect(() => {
    if (!expanded) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') setExpanded(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [expanded])
  const toggleExpand = () => {
    setExpanded((open) => !open)
  }

  const resultPane = (
    <section className={expanded ? 'fixed inset-0 z-50 bg-[#f4f7fb] overflow-auto p-5 sm:p-8' : 'space-y-4 min-w-0'}>
      <div className={`flex items-center justify-between gap-3 ${expanded ? 'max-w-5xl mx-auto mb-4' : 'mb-1'}`}>
        {expanded ? (
          <div>
            <div className="text-sm font-semibold text-ink-900">{scenario.name} · 全屏结果</div>
            <p className="text-xs text-ink-500 mt-0.5">每一步都用人话写清楚。按 Esc 或点右侧按钮退出。</p>
          </div>
        ) : <span />}
        <button type="button" className="btn-ghost text-xs shrink-0" onClick={toggleExpand}>
          {expanded ? '退出全屏' : '全屏查看结果'}
        </button>
      </div>
      <div className={expanded ? 'max-w-5xl mx-auto space-y-4' : 'space-y-4'}>{result}</div>
    </section>
  )

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
        {resultPane}
      </div>
    </div>
  )
}
