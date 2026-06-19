import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts'
import Breadcrumbs from '../components/Breadcrumbs'
import Section from '../components/Section'

// ── 完整 benchmark 数据（2026-06-19 全量跑完，语义相似度评分 v0.5）──────────────────────
// LLM-only 维度：problem_localization→Detection / mechanism_insight→Reasoning /
//               actionability→Intervention / evidence_grounding→Evidence
const LLM_ONLY = {
  fraud_im:         { RES: 0.714, Detection: 0.892, Reasoning: 0.863, Intervention: 0.330, Evidence: 0.790, Runtime: null },
  public_opinion:   { RES: 0.376, Detection: 0.277, Reasoning: 0.128, Intervention: 0.159, Evidence: 0.843, Runtime: null },
  event_propagation:{ RES: 0.589, Detection: 0.354, Reasoning: 0.413, Intervention: 0.607, Evidence: 0.927, Runtime: null },
}

// Miro 维度映射：RCA→Detection / EAR→Evidence / IWA(CWS)→Intervention /
//               FPA(ANS+PCS)→Reasoning。原始 benchmark_prediction 字段修正后重新打分。
const MIRO = {
  fraud_im:         { RES: 0.712, Detection: 0.825, Reasoning: 0.700, Intervention: 0.800, Evidence: 0.870, Runtime: 1.000, samples: '20/20' },
  public_opinion:   { RES: 0.414, Detection: 0.700, Reasoning: 0.374, Intervention: 0.474, Evidence: 0.738, Runtime: 0.667, samples: '5/5' },
  event_propagation:{ RES: 0.597, Detection: 0.700, Reasoning: 0.613, Intervention: 0.900, Evidence: 0.758, Runtime: 0.667, samples: '5/5' },
}

// fraud_im 细分（Miro vs LLM-only，语义评分 v0.5）
const FRAUD_DETAIL = [
  { key: 'FPA', label: '分叉点准确率',   miro: 70.0,  llm: null },
  { key: 'RCA', label: '风险定级准确率', miro: 82.5,  llm: 95.0 },
  { key: 'ATA', label: '资产识别准确率', miro: 84.2,  llm: 72.5 },
  { key: 'IWA', label: '干预窗口准确率', miro: 80.0,  llm: 65.0 },
  { key: 'EAR', label: '证据归因率',     miro: 87.0,  llm: 79.0 },
]

// event_propagation 细分（Miro vs LLM-only，语义评分 v0.5）
const EVENT_DETAIL = [
  { key: 'RCA', label: '风险定级', miro: 70.0,  llm: 30.0 },
  { key: 'CWS', label: '阻断窗口', miro: 90.0,  llm: 100.0 },
  { key: 'DCS', label: '失真识别', miro: 38.5,  llm: 57.6 },
  { key: 'OVS', label: '源头识别', miro: 41.9,  llm: 25.1 },
  { key: 'EAR', label: '证据归因', miro: 75.8,  llm: 92.7 },
]

// 盲评：Qwen3.7-plus 盲测（无参考答案，结构化 dict 格式，v0.3，最新数据）
const JUDGE = {
  fraud_im:          { miro: 1,  llm: 19, total: 20 },
  public_opinion:    { miro: 0,  llm: 5,  total: 5  },
  event_propagation: { miro: 2,  llm: 3,  total: 5  },
}

const SCENARIO_LABELS = {
  fraud_im: '诈骗即时通讯',
  public_opinion: '舆情分析',
  event_propagation: '事件传播分析',
}

const SCENARIO_COLORS = {
  fraud_im: '#4a90d9',
  public_opinion: '#52a882',
  event_propagation: '#e8b84b',
}

const DIMS = ['Detection', 'Reasoning', 'Intervention', 'Evidence', 'Runtime']
const DIM_ZH = { Detection: '检测', Reasoning: '推理', Intervention: '干预', Evidence: '证据', Runtime: '运行' }

export default function BenchmarkPage() {
  const resData = Object.keys(LLM_ONLY).map((k) => ({
    name: SCENARIO_LABELS[k],
    scenario: k,
    'Miro-CogSec': MIRO[k].RES,
    'LLM-only': LLM_ONLY[k].RES,
  }))

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <Breadcrumbs items={[{ label: '首页', to: '/' }, { label: 'Benchmark 对比' }]} />
      <div className="mt-3 mb-6">
        <h1 className="text-xl font-semibold text-ink-900">效果评估与对比</h1>
        <p className="text-xs text-ink-500 mt-1">
          三个场景全量跑完（2026-06-19）。Miro-CogSec vs DeepSeek LLM-only baseline。
          含三项评测：① RES 语义总分 ② 分维度得分 ③ Qwen3.7-plus 盲评胜率。
        </p>
      </div>

      {/* RES 总分对比 */}
      <Section title="RES 总分对比">
        <div className="h-56">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={resData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} />
              <YAxis domain={[0, 1]} tickFormatter={(v) => v.toFixed(1)} tick={{ fontSize: 11, fill: '#64748b' }} />
              <Tooltip formatter={(v) => v.toFixed(3)} contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="LLM-only" fill="#cbd5e1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Miro-CogSec" fill="#4a90d9" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <p className="text-[11px] text-ink-500 mt-2">
          评分方法：语义相似度 v0.5（自由文本字段用向量余弦，分类字段用软匹配）。Miro 在舆情与事件传播场景超过 LLM-only，诈骗 IM 几乎持平。
        </p>
      </Section>

      {/* 盲评胜率 */}
      <Section title="盲评胜率（Qwen3.7-plus 盲测）">
        <div className="h-52">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={Object.keys(JUDGE).map((k) => ({
                name: SCENARIO_LABELS[k],
                'Miro-CogSec': +(JUDGE[k].miro / JUDGE[k].total * 100).toFixed(1),
                'LLM-only': +(JUDGE[k].llm / JUDGE[k].total * 100).toFixed(1),
              }))}
              margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="name" tick={{ fontSize: 12, fill: '#64748b' }} />
              <YAxis domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: '#64748b' }} />
              <Tooltip formatter={(v) => `${v}%`} contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Bar dataKey="LLM-only" fill="#cbd5e1" radius={[4, 4, 0, 0]} />
              <Bar dataKey="Miro-CogSec" fill="#4a90d9" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] text-ink-500 border-b border-border">
                <th className="py-2 px-2 font-medium">场景</th>
                <th className="py-2 px-2 font-medium text-right">样本数</th>
                <th className="py-2 px-2 font-medium text-right">Miro 胜</th>
                <th className="py-2 px-2 font-medium text-right">LLM 胜</th>
                <th className="py-2 px-2 font-medium text-right">Miro 胜率</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(JUDGE).map((k) => {
                const j = JUDGE[k]
                const pct = (j.miro / j.total * 100).toFixed(0)
                return (
                  <tr key={k} className="border-b border-border hover:bg-slate-50/60">
                    <td className="py-2 px-2">
                      <span className="tag" style={{ background: SCENARIO_COLORS[k] + '1A', color: SCENARIO_COLORS[k] }}>
                        {SCENARIO_LABELS[k]}
                      </span>
                    </td>
                    <td className="py-2 px-2 text-right text-ink-500">{j.total}</td>
                    <td className="py-2 px-2 text-right font-medium text-brand">{j.miro}</td>
                    <td className="py-2 px-2 text-right text-ink-500">{j.llm}</td>
                    <td className="py-2 px-2 text-right font-semibold" style={{ color: +pct >= 40 ? '#4a90d9' : '#94a3b8' }}>
                      {pct}%
                    </td>
                  </tr>
                )
              })}
              <tr className="bg-slate-50/80">
                <td className="py-2 px-2 font-medium text-ink-700">合计</td>
                <td className="py-2 px-2 text-right font-medium text-ink-700">30</td>
                <td className="py-2 px-2 text-right font-medium text-brand">3</td>
                <td className="py-2 px-2 text-right text-ink-500">27</td>
                <td className="py-2 px-2 text-right font-semibold text-ink-500">10%</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-ink-500 mt-2">
          Qwen3.7-plus 盲测，无参考答案，结构化预测 dict 格式，温度 0.0。
          LLM-only 以自然语言叙述风格取得优势；Miro 在事件传播场景胜率 40%。
          盲评反映表达流畅度，RES 语义评分反映字段精确度，两者衡量维度不同。
        </p>
      </Section>

      {/* 分维度明细表 */}
      <Section title="分维度得分明细">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-[11px] text-ink-500 border-b border-border">
                <th className="py-2 px-2 font-medium">场景</th>
                <th className="py-2 px-2 font-medium">系统</th>
                <th className="py-2 px-2 font-medium text-right">样本</th>
                {DIMS.map((d) => (
                  <th key={d} className="py-2 px-2 font-medium text-right">{DIM_ZH[d]}</th>
                ))}
                <th className="py-2 px-2 font-medium text-right">RES</th>
              </tr>
            </thead>
            <tbody>
              {Object.keys(LLM_ONLY).map((k) => (
                <>
                  <tr key={k + '-miro'} className="border-b border-border hover:bg-slate-50/60">
                    <td className="py-2 px-2" rowSpan={2}>
                      <span className="tag" style={{ background: SCENARIO_COLORS[k] + '1A', color: SCENARIO_COLORS[k] }}>
                        {SCENARIO_LABELS[k]}
                      </span>
                    </td>
                    <td className="py-2 px-2 font-medium text-brand">Miro</td>
                    <td className="py-2 px-2 text-right text-xs text-ink-500">{MIRO[k].samples}</td>
                    {DIMS.map((d) => (
                      <td key={d} className="py-2 px-2 text-right">
                        {MIRO[k][d] != null ? MIRO[k][d].toFixed(3) : '—'}
                      </td>
                    ))}
                    <td className="py-2 px-2 text-right font-semibold text-brand">{MIRO[k].RES.toFixed(3)}</td>
                  </tr>
                  <tr key={k + '-llm'} className="border-b border-border hover:bg-slate-50/60">
                    <td className="py-2 px-2 text-ink-500">LLM-only</td>
                    <td className="py-2 px-2 text-right text-xs text-ink-500">
                      {k === 'fraud_im' ? '20/20' : '5/5'}
                    </td>
                    {DIMS.map((d) => (
                      <td key={d} className="py-2 px-2 text-right text-ink-500">
                        {LLM_ONLY[k][d] != null ? LLM_ONLY[k][d].toFixed(3) : '—'}
                      </td>
                    ))}
                    <td className="py-2 px-2 text-right font-semibold text-ink-500">{LLM_ONLY[k].RES.toFixed(3)}</td>
                  </tr>
                </>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* 雷达图：细分指标对比（Miro vs LLM-only） */}
      <div className="grid md:grid-cols-2 gap-4">
        <Section title="诈骗IM · 细分指标对比">
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={FRAUD_DETAIL.map((r) => ({ subject: r.label, miro: r.miro, llm: r.llm }))}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: '#1e293b' }} />
                <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#94a3b8' }} />
                <Radar name="Miro" dataKey="miro" stroke="#4a90d9" fill="#4a90d9" fillOpacity={0.35} />
                <Radar name="LLM-only" dataKey="llm" stroke="#94a3b8" fill="#94a3b8" fillOpacity={0.15} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => v != null ? `${v}%` : '—'} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-ink-500 mt-1">Miro: FPA 70% · RCA 82.5% · EAR 87% · IWA 80% · ATA 84%</p>
        </Section>

        <Section title="事件传播 · 细分指标对比">
          <div className="h-52">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={EVENT_DETAIL.map((r) => ({ subject: r.label, miro: r.miro, llm: r.llm }))}>
                <PolarGrid stroke="#e2e8f0" />
                <PolarAngleAxis dataKey="subject" tick={{ fontSize: 11, fill: '#1e293b' }} />
                <PolarRadiusAxis domain={[0, 100]} tick={{ fontSize: 9, fill: '#94a3b8' }} />
                <Radar name="Miro" dataKey="miro" stroke="#e8b84b" fill="#e8b84b" fillOpacity={0.35} />
                <Radar name="LLM-only" dataKey="llm" stroke="#94a3b8" fill="#94a3b8" fillOpacity={0.15} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => v != null ? `${v}%` : '—'} />
              </RadarChart>
            </ResponsiveContainer>
          </div>
          <p className="text-[11px] text-ink-500 mt-1">Miro: RCA 70% · CWS 90% · ANS 65.5% · EAR 75.8% · OVS 41.9%</p>
        </Section>
      </div>

      {/* 说明 */}
      <Section title="评分维度说明">
        <div className="grid md:grid-cols-2 gap-x-8 gap-y-1 text-xs text-ink-700">
          {[
            ['Detection', '检测', '场景识别正确 + 风险等级判断'],
            ['Reasoning', '推理', '风险机制、分叉点、传播节点、失真点'],
            ['Intervention', '干预', '干预窗口 + 可执行建议'],
            ['Evidence', '证据', '输出结论能否对应输入文本片段'],
            ['Runtime', '运行', '跑通率、延迟、传播结果存在性'],
            ['RES', '总分', '各维度加权综合得分'],
          ].map(([en, zh, desc]) => (
            <div key={en} className="flex gap-2 py-1 border-b border-border last:border-0">
              <span className="font-mono font-medium text-ink-900 w-24 flex-none">{en} · {zh}</span>
              <span className="text-ink-500">{desc}</span>
            </div>
          ))}
        </div>
        <div className="mt-3 rounded-md bg-sand/10 border border-sand/30 px-3 py-2 text-[11px] text-ink-600 leading-relaxed">
          <strong>Miro-CogSec vs LLM-only 总结</strong><br />
          修正 benchmark_prediction 字段映射后（语义评分 v0.5），Miro 在舆情（+3.8%）和事件传播（+0.8%）场景超过 LLM-only 基线，诈骗 IM 几乎持平（差 0.2%）。
          Miro 的优势在于干预窗口（IWA 80%）、资产识别（ATA 84%）和证据归因（EAR 87%），
          弱点是风险定级准确率（RCA 82.5% vs LLM 95%）和分叉点识别（FPA 70%）。
        </div>
      </Section>
    </div>
  )
}
