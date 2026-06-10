/**
 * TODO: 对接 GET /api/benchmark/metrics，接口由后端实现，
 * 真实调用代码见 git history。
 *
 * 当前为静态 mock：三个场景各三条评估指标，
 * 列名：场景、评估指标、本系统、基线方法、提升幅度。
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
  { scenario: '诈骗即时通讯', metric: 'FSA · 欺诈策略命中率', ours: 78.4, baseline: 61.2, unit: '%' },
  { scenario: '诈骗即时通讯', metric: 'CPA · 反事实路径准确率', ours: 71.6, baseline: 49.8, unit: '%' },
  { scenario: '诈骗即时通讯', metric: 'EWT · 有效干预窗口', ours: 3.4, baseline: 1.6, unit: '步' },
  { scenario: '舆情分析', metric: '负面情绪检出率', ours: 92.1, baseline: 80.5, unit: '%' },
  { scenario: '舆情分析', metric: '关键词覆盖率', ours: 88.7, baseline: 74.0, unit: '%' },
  { scenario: '舆情分析', metric: '意见领袖识别率', ours: 81.2, baseline: 65.4, unit: '%' },
  { scenario: '事件传播分析', metric: '节点覆盖准确率', ours: 86.3, baseline: 70.1, unit: '%' },
  { scenario: '事件传播分析', metric: '关键路径识别', ours: 79.5, baseline: 58.7, unit: '%' },
  { scenario: '事件传播分析', metric: '峰值预测误差(↓)', ours: 7.8, baseline: 18.4, unit: '%' },
]

const SCENARIO_COLORS = {
  '诈骗即时通讯': '#4a90d9',
  '舆情分析': '#52a882',
  '事件传播分析': '#e8b84b',
}

function deltaText(row) {
  const lowerIsBetter = row.metric.includes('↓')
  const diff = lowerIsBetter ? row.baseline - row.ours : row.ours - row.baseline
  const pct = (diff / row.baseline) * 100
  const sign = pct >= 0 ? '+' : ''
  return { text: `${sign}${pct.toFixed(1)}%`, positive: pct >= 0 }
}

export default function BenchmarkPage() {
  const chartData = ROWS.map((r) => ({
    name: r.metric,
    scenario: r.scenario,
    ours: r.ours,
    baseline: r.baseline,
  }))

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <Breadcrumbs items={[{ label: '首页', to: '/' }, { label: 'Benchmark 对比' }]} />
      <div className="mt-3 mb-6">
        <h1 className="text-xl font-semibold text-ink-900">效果评估与对比</h1>
        <p className="text-xs text-ink-500 mt-1">
          三个场景下，本系统与典型基线方法在关键评估指标上的对比。数据为离线评估集 mock 结果，
          待 <code className="text-ink-900">GET /api/benchmark/metrics</code> 由后端实现后接入真实数据。
        </p>
      </div>

      <Section title="指标对比表">
        <div className="overflow-x-auto -mx-1">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] text-ink-500 border-b border-border">
                <th className="py-2 px-2 font-medium">场景</th>
                <th className="py-2 px-2 font-medium">评估指标</th>
                <th className="py-2 px-2 font-medium text-right">本系统</th>
                <th className="py-2 px-2 font-medium text-right">基线方法</th>
                <th className="py-2 px-2 font-medium text-right">提升幅度</th>
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
                      {r.ours}
                      {r.unit}
                    </td>
                    <td className="py-2.5 px-2 text-right text-ink-500">
                      {r.baseline}
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
              <Bar dataKey="baseline" name="基线方法" fill="#cbd5e1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="ours" name="本系统" fill="#4a90d9" radius={[4, 4, 0, 0]} />
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
          <span className="ml-auto">说明：含 ↓ 标记的指标越低越好；其余越高越好。</span>
        </div>
      </Section>
    </div>
  )
}
