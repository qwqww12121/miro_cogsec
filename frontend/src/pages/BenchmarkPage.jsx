/**
 * CJY benchmark v0.1 离线摘要。
 * 数据对应 benchmark/README.md 中已经记录的 AQS 与 LLM-only baseline 汇总。
 */

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import Breadcrumbs from '../components/Breadcrumbs'
import Section from '../components/Section'

const ROWS = [
  { scenario: '诈骗即时通讯', metric: 'AQS · gold 标注质量', current: 100.0, reference: 100.0, unit: '%' },
  { scenario: '诈骗即时通讯', metric: '格式通过率 · LLM-only', current: 100.0, reference: 100.0, unit: '%' },
  { scenario: '诈骗即时通讯', metric: 'RES · LLM-only', current: 78.9, reference: 65.0, unit: '%' },
  { scenario: '舆情分析', metric: 'AQS · gold 标注质量', current: 100.0, reference: 100.0, unit: '%' },
  { scenario: '舆情分析', metric: '格式通过率 · LLM-only', current: 100.0, reference: 100.0, unit: '%' },
  { scenario: '舆情分析', metric: 'RES · LLM-only', current: 39.9, reference: 65.0, unit: '%' },
  { scenario: '事件传播分析', metric: 'AQS · gold 标注质量', current: 100.0, reference: 100.0, unit: '%' },
  { scenario: '事件传播分析', metric: '格式通过率 · LLM-only', current: 100.0, reference: 100.0, unit: '%' },
  { scenario: '事件传播分析', metric: 'RES · LLM-only', current: 70.1, reference: 65.0, unit: '%' },
]

const SCENARIO_COLORS = {
  '诈骗即时通讯': '#4a90d9',
  '舆情分析': '#52a882',
  '事件传播分析': '#e8b84b',
}

function deltaText(row) {
  const lowerIsBetter = row.metric.includes('↓')
  const diff = lowerIsBetter ? row.reference - row.current : row.current - row.reference
  const pct = row.reference === 0 ? 0 : (diff / row.reference) * 100
  const sign = pct >= 0 ? '+' : ''
  return { text: `${sign}${pct.toFixed(1)}%`, positive: pct >= 0 }
}

export default function BenchmarkPage() {
  const chartData = ROWS.map((r) => ({
    name: r.metric,
    scenario: r.scenario,
    current: r.current,
    reference: r.reference,
  }))

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <Breadcrumbs items={[{ label: '首页', to: '/' }, { label: 'Benchmark 对比' }]} />
      <div className="mt-3 mb-6">
        <h1 className="text-xl font-semibold text-ink-900">效果评估与对比</h1>
        <p className="text-xs text-ink-500 mt-1">
          三个场景下，CJY benchmark v0.1 已记录指标与参考线的对比。数据来自后端 benchmark 文档中的离线汇总。
        </p>
      </div>

      <Section title="指标对比表">
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] text-ink-500 border-b border-border">
                <th className="py-2 px-2 font-medium">场景</th>
                <th className="py-2 px-2 font-medium">评估指标</th>
                <th className="py-2 px-2 font-medium text-right">当前记录</th>
                <th className="py-2 px-2 font-medium text-right">参考线</th>
                <th className="py-2 px-2 font-medium text-right">差值</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r, i) => {
                const delta = deltaText(r)
                return (
                  <tr key={i} className="border-b border-border last:border-0 hover:bg-slate-50/60">
                    <td className="py-2.5 px-2">
                      <span
                        className="tag"
                        style={{
                          background: SCENARIO_COLORS[r.scenario] + '1A',
                          color: SCENARIO_COLORS[r.scenario],
                        }}
                      >
                        {r.scenario}
                      </span>
                    </td>
                    <td className="py-2.5 px-2 text-ink-900">{r.metric}</td>
                    <td className="py-2.5 px-2 text-right font-medium text-ink-900">
                      {r.current}
                      {r.unit}
                    </td>
                    <td className="py-2.5 px-2 text-right text-ink-500">
                      {r.reference}
                      {r.unit}
                    </td>
                    <td className="py-2.5 px-2 text-right">
                      <span className={`tag ${delta.positive ? 'bg-leaf-50 text-leaf-600' : 'bg-rose-50 text-rose-600'}`}>
                        {delta.text}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="可视化对比" className="mt-5">
        <div className="h-[460px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 16, right: 16, left: 0, bottom: 80 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 11, fill: '#64748b' }}
                interval={0}
                angle={-22}
                textAnchor="end"
                height={80}
              />
              <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
              <Tooltip
                contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }}
                cursor={{ fill: '#f8fafc' }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="reference" name="参考线" fill="#cbd5e1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="current" name="当前记录" fill="#4a90d9" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-wrap gap-3 mt-3 text-[11px] text-ink-500">
          {Object.entries(SCENARIO_COLORS).map(([name, c]) => (
            <span key={name} className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-sm" style={{ background: c }} />
              {name}
            </span>
          ))}
          <span className="ml-auto">说明：AQS / 格式通过率参考线为 100%；RES 参考线暂按 65%。</span>
        </div>
      </Section>
    </div>
  )
}
