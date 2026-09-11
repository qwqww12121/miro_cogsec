import InfoHint from './InfoHint'
import { getRiskBand, GLOSSARY, describeScenarioType, describeRiskType } from '../scenarios/glossary'

/**
 * 核心结论横幅：场景、风险类型、四档风险。
 */
export default function RiskHeadline({ scenarioType, vulnerabilityScore, riskType, extra }) {
  const band = getRiskBand(vulnerabilityScore)
  const num = Number(vulnerabilityScore)
  const scoreText =
    vulnerabilityScore != null && !Number.isNaN(num) ? num.toFixed(1) : '—'
  const pct = Math.round(Math.min(100, Math.max(0, Number.isNaN(num) ? 0 : num)))
  const name = describeScenarioType(scenarioType)
  const typeLabel = describeRiskType(riskType)

  return (
    <div className={`card p-5 ${band ? band.box : 'border-border'}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[11px] text-ink-500">核心结论</div>
          <div className="mt-0.5 text-lg font-semibold text-ink-900 truncate">{name}</div>
          {typeLabel ? (
            <div className="mt-1 text-xs text-ink-500">
              风险类型：<span className="font-medium text-ink-800">{typeLabel}</span>
            </div>
          ) : null}
        </div>
        {band && <span className={`tag flex-none text-sm ${band.badge}`}>{band.label}</span>}
      </div>

      <div className="mt-3 flex items-end gap-1.5">
        <span className={`text-4xl font-bold leading-none ${band ? band.valueText : 'text-ink-900'}`}>
          {scoreText}
        </span>
        <span className="text-sm text-ink-500 mb-0.5 flex items-center gap-1">
          /100
          <InfoHint text={GLOSSARY.vulnerability_score} />
        </span>
      </div>
      <div className="text-xs text-ink-500 mt-1">综合脆弱度评分</div>

      <div className="mt-3 bg-white/70 rounded-full h-2 overflow-hidden">
        <div
          className="h-full rounded-full transition-all"
          style={{ width: `${pct}%`, background: band ? band.bar : '#cbd5e1' }}
        />
      </div>

      {band && (
        <div className="mt-3 text-sm text-ink-900 leading-relaxed">{band.conclusion}</div>
      )}
      {extra && <div className="mt-2 text-xs text-ink-500 leading-relaxed">{extra}</div>}
    </div>
  )
}
