/**
 * 正式评测数据(v4_final,2026-08-06 自动 Benchmark,30 例)。
 * 来源:benchmark 正式自动评测,RES = 场景综合评分(0-1,越高越好)。
 * 负向差值(fraud_im、按样本数加权)如实保留,不做修饰。
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
  { scenario: '诈骗即时通讯', metric: 'RES 综合评分', ours: 0.779, baseline: 0.813, cases: 20 },
  { scenario: '舆情分析', metric: 'RES 综合评分', ours: 0.544, baseline: 0.481, cases: 5 },
  { scenario: '事件传播分析', metric: 'RES 综合评分', ours: 0.769, baseline: 0.745, cases: 5 },
]

const SUMMARY_ROWS = [
  { scenario: '汇总', metric: '宏平均(三场景等权)', ours: 0.697, baseline: 0.680 },
  { scenario: '汇总', metric: '按样本数加权平均', ours: 0.738, baseline: 0.746 },
]

const SCENARIO_COLORS = {
  '诈骗即时通讯': '#4a90d9',
  '舆情分析': '#52a882',
  '事件传播分析': '#e8b84b',
  '汇总': '#8b9dc3',
}

function deltaText(row) {
  const diff = row.ours - row.baseline
  const pct = (diff / row.baseline) * 100
  const sign = diff >= 0 ? '+' : ''
  return { text: `${sign}${diff.toFixed(3)}(${sign}${pct.toFixed(1)}%)`, positive: diff >= 0 }
}

export default function BenchmarkPage() {
  const chartData = ROWS.map((r) => ({
    name: r.scenario,
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
          三个场景下,本系统与 LLM-only 基线在 RES 综合评分上的对比。数据来源:v4_final
          正式自动评测(2026-08-06),旁路指标,不影响用户可见输出。
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
                <th className="py-2 px-2 font-medium text-right">LLM-only 基线</th>
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
                    <td className="py-2.5 px-2 text-ink-900">{r.metric}<span className="text-ink-300 ml-1">({r.cases} 例)</span></td>
                    <td className="py-2.5 px-2 text-right font-medium text-ink-900">
                      {r.ours.toFixed(3)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-ink-500">
                      {r.baseline.toFixed(3)}
                    </td>
                    <td className="py-2.5 px-2 text-right">
                      <span className={`tag ${delta.positive ? 'bg-leaf-50 text-leaf-600' : 'bg-amber-50 text-amber-700'}`}>
                        {delta.text}
                      </span>
                    </td>
                  </tr>
                )
              })}
              {SUMMARY_ROWS.map((r, i) => {
                const delta = deltaText(r)
                return (
                  <tr key={`sum-${i}`} className="border-b border-border last:border-0 bg-slate-50/40">
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
                      {r.ours.toFixed(3)}
                    </td>
                    <td className="py-2.5 px-2 text-right text-ink-500">
                      {r.baseline.toFixed(3)}
                    </td>
                    <td className="py-2.5 px-2 text-right">
                      <span className={`tag ${delta.positive ? 'bg-leaf-50 text-leaf-600' : 'bg-amber-50 text-amber-700'}`}>
                        {delta.text}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
        <div className="text-[11px] text-ink-500 mt-3 leading-relaxed">
          数据说明:RES 为场景综合评分(0-1,越高越好);评测集共 30 例(诈骗即时通讯 20、舆情分析 5、事件传播 5),
          与 LLM-only 基线同输入对比。宏平均与按样本数加权两种口径已在表中如实并列;
          诈骗即时通讯场景本系统低于基线,已如实标注。评测日期 2026-08-06。
        </div>
      </Section>

      <Section title="可视化对比" className="mt-5">
        <div className="h-[380px]">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData} margin={{ top: 16, right: 16, left: 0, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis
                dataKey="name"
                tick={{ fontSize: 12, fill: '#64748b' }}
                interval={0}
                height={40}
              />
              <YAxis tick={{ fontSize: 11, fill: '#64748b' }} domain={[0, 1]} />
              <Tooltip
                contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }}
                cursor={{ fill: '#f8fafc' }}
              />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="baseline" name="LLM-only 基线" fill="#cbd5e1" radius={[4, 4, 0, 0]} />
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
          <span className="ml-auto">RES 综合评分:0-1,越高越好。数据:2026-08-06 正式自动评测。</span>
        </div>
      </Section>
    </div>
  )
}
