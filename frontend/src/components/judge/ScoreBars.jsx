// 单个系统的 5 维得分条。scores 形如 { problem_localization: 9, ... }，0–10。

const DIMS = [
  'problem_localization',
  'actionability',
  'evidence_grounding',
  'mechanism_insight',
  'output_reliability',
]

const DIM_ZH = {
  problem_localization: '问题定位',
  actionability: '可操作性',
  evidence_grounding: '证据支撑',
  mechanism_insight: '机制洞察',
  output_reliability: '输出可靠性',
}

export default function ScoreBars({ scores = {}, color = '#4a90d9' }) {
  return (
    <div className="space-y-1.5">
      {DIMS.map((d) => {
        const v = Number(scores[d] ?? 0)
        return (
          <div key={d} className="flex items-center gap-2">
            <div className="w-16 shrink-0 text-[11px] text-ink-500">{DIM_ZH[d]}</div>
            <div className="flex-1 h-2 rounded-full bg-slate-100 overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${(v / 10) * 100}%`, background: color }}
              />
            </div>
            <div className="w-7 shrink-0 text-right text-[11px] font-medium text-ink-900">{v}</div>
          </div>
        )
      })}
    </div>
  )
}
