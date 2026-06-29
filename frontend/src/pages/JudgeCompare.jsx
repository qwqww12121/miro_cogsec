/**
 * 裁判对比结果展示（轻量版，纯读静态文件，不调后端）。
 *
 * 数据源（已复制到 frontend/public/judge_data/，靠 id join，30 条完整配对）：
 *   /judge_data/judge_results_no_gold_v2.0_direct_actions_v4flash.jsonl  判决
 *   /judge_data/judge_requests_no_gold_v2.0_direct_actions.jsonl         输入+双方报告
 *
 * 关键点：A/B 槽位在生成时按 sha256(id) 随机化过（30 条里 9 条翻转），
 * 这里通过 results 的 answer_a_system/answer_b_system 把槽位归位为
 * ours=miro_cogsec / baseline=llm_only，界面彻底不暴露 A/B。
 */

import { useEffect, useMemo, useState } from 'react'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import Breadcrumbs from '../components/Breadcrumbs'
import Section from '../components/Section'
import JudgeCard from '../components/judge/JudgeCard'

const RESULTS_URL = '/judge_data/judge_results_no_gold_v2.0_direct_actions_v4flash.jsonl'
const REQUESTS_URL = '/judge_data/judge_requests_no_gold_v2.0_direct_actions.jsonl'

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

const SCEN = {
  fraud_im: { label: '诈骗即时通讯', color: '#4a90d9' },
  public_opinion: { label: '舆情分析', color: '#52a882' },
  event_propagation: { label: '事件传播分析', color: '#e8b84b' },
}

const SCEN_ORDER = ['fraud_im', 'public_opinion', 'event_propagation']

function parseJsonl(text) {
  return text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean)
    .map((l) => JSON.parse(l))
}

function buildRecords(results, requests) {
  const reqById = new Map(requests.map((r) => [r.id, r]))
  return results.map((res) => {
    const req = reqById.get(res.id)
    const slotText = {
      a: req?.answer_a?.text ?? '',
      b: req?.answer_b?.text ?? '',
    }
    const slotScores = {
      a: res.answer_a_scores || {},
      b: res.answer_b_scores || {},
    }
    const slotSystem = { a: res.answer_a_system, b: res.answer_b_system }
    // 按系统名找槽位——对 9 条翻转记录同样正确
    const oursSlot = Object.keys(slotSystem).find((k) => slotSystem[k] === 'miro_cogsec')
    const baseSlot = Object.keys(slotSystem).find((k) => slotSystem[k] === 'llm_only')
    return {
      id: res.id,
      scenarioType: res.scenario_type,
      inputText: req?.input?.text ?? '',
      ours: { text: slotText[oursSlot] || '', scores: slotScores[oursSlot] || {} },
      baseline: { text: slotText[baseSlot] || '', scores: slotScores[baseSlot] || {} },
      oursWon: res.winner_system === 'miro_cogsec',
      oursSlot,
      rationale: res.rationale || '',
      judgeModel: res.judge_model || '',
    }
  })
}

function avgScores(records, getter) {
  const out = {}
  DIMS.forEach((d) => {
    out[d] = records.reduce((s, r) => s + Number(getter(r)[d] ?? 0), 0) / (records.length || 1)
  })
  return out
}

export default function JudgeCompare() {
  const [records, setRecords] = useState(null)
  const [error, setError] = useState(null)
  const [scenario, setScenario] = useState('all')
  const [outcome, setOutcome] = useState('all')

  useEffect(() => {
    let cancelled = false
    Promise.all([
      fetch(RESULTS_URL).then((r) => r.text()),
      fetch(REQUESTS_URL).then((r) => r.text()),
    ])
      .then(([rt, qt]) => {
        if (cancelled) return
        setRecords(buildRecords(parseJsonl(rt), parseJsonl(qt)))
      })
      .catch((e) => {
        if (!cancelled) setError(String(e))
      })
    return () => {
      cancelled = true
    }
  }, [])

  const stats = useMemo(() => {
    if (!records) return null
    const total = records.length
    const oursWins = records.filter((r) => r.oursWon).length
    const byScen = {}
    for (const k of SCEN_ORDER) {
      const sub = records.filter((r) => r.scenarioType === k)
      const w = sub.filter((r) => r.oursWon).length
      byScen[k] = { total: sub.length, wins: w, rate: sub.length ? (w / sub.length) * 100 : 0 }
    }
    const oursAvg = avgScores(records, (r) => r.ours.scores)
    const baseAvg = avgScores(records, (r) => r.baseline.scores)
    return { total, oursWins, baseWins: total - oursWins, winRate: (oursWins / total) * 100, byScen, oursAvg, baseAvg }
  }, [records])

  const radarData = useMemo(() => {
    if (!stats) return []
    return DIMS.map((d) => ({
      dim: DIM_ZH[d],
      我方: +stats.oursAvg[d].toFixed(2),
      Baseline: +stats.baseAvg[d].toFixed(2),
    }))
  }, [stats])

  const filtered = useMemo(() => {
    if (!records) return []
    return records.filter((r) => {
      if (scenario !== 'all' && r.scenarioType !== scenario) return false
      if (outcome === 'ours' && !r.oursWon) return false
      if (outcome === 'baseline' && r.oursWon) return false
      return true
    })
  }, [records, scenario, outcome])

  if (error) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-10 text-sm text-rose-600">
        裁判数据加载失败：{error}
      </div>
    )
  }
  if (!records) {
    return (
      <div className="max-w-7xl mx-auto px-6 py-10 text-sm text-ink-500">加载裁判数据…</div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-6 py-6">
      <Breadcrumbs items={[{ label: '首页', to: '/' }, { label: '裁判对比' }]} />

      <div className="mt-3 mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-ink-900">裁判对比结果</h1>
          <p className="text-xs text-ink-500 mt-1">
            闭源大模型对"我方系统 vs LLM-only baseline"做盲评，相同输入下逐条判定胜方与五维得分。
          </p>
        </div>
        <div className="text-[11px] text-ink-300 text-right shrink-0 hidden sm:block">
          采用闭源大模型盲评
          <br />
          + 答案位置随机化，避免位置偏见
        </div>
      </div>

      {/* 顶部成果总览 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-5">
        {/* 总胜率 */}
        <div className="card p-5 flex flex-col justify-center">
          <div className="text-xs text-ink-500 mb-1">总胜率（我方系统）</div>
          <div className="flex items-baseline gap-2">
            <span className="text-4xl font-bold text-brand">{stats.winRate.toFixed(2)}%</span>
          </div>
          <div className="text-xs text-ink-500 mt-2">
            <span className="text-leaf-600 font-medium">{stats.oursWins} 胜</span>
            <span className="mx-1">/</span>
            <span className="text-sand-600 font-medium">{stats.baseWins} 负</span>
            <span className="ml-2 text-ink-300">共 {stats.total} 条</span>
          </div>
        </div>

        {/* 分场景胜率 */}
        <div className="card p-5 lg:col-span-2">
          <div className="text-xs text-ink-500 mb-3">分场景胜率</div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {SCEN_ORDER.map((k) => {
              const s = stats.byScen[k]
              const meta = SCEN[k]
              return (
                <div key={k} className="rounded-lg border border-border bg-bg p-3">
                  <div className="flex items-center gap-1.5 mb-2">
                    <span className="w-2 h-2 rounded-sm" style={{ background: meta.color }} />
                    <span className="text-[11px] text-ink-500">{meta.label}</span>
                  </div>
                  <div className="text-2xl font-semibold text-ink-900">
                    {s.rate.toFixed(0)}%
                  </div>
                  <div className="text-[11px] text-ink-300 mt-0.5">
                    {s.wins} 胜 / {s.total} 条
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      </div>

      {/* 雷达图：五维平均分对比 */}
      <Section title="五维平均分对比（我方 vs baseline）" className="mb-5">
        <div className="h-[340px]">
          <ResponsiveContainer width="100%" height="100%">
            <RadarChart data={radarData} outerRadius="72%">
              <PolarGrid stroke="#e2e8f0" />
              <PolarAngleAxis dataKey="dim" tick={{ fontSize: 12, fill: '#64748b' }} />
              <PolarRadiusAxis domain={[0, 10]} tick={{ fontSize: 10, fill: '#cbd5e1' }} />
              <Radar name="我方系统" dataKey="我方" stroke="#4a90d9" strokeWidth={2} fill="#4a90d9" fillOpacity={0.25} />
              <Radar name="Baseline" dataKey="Baseline" stroke="#94a3b8" strokeWidth={2} fill="#94a3b8" fillOpacity={0.12} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Tooltip contentStyle={{ borderRadius: 8, borderColor: '#e2e8f0', fontSize: 12 }} />
            </RadarChart>
          </ResponsiveContainer>
        </div>
      </Section>

      {/* 筛选器 */}
      <div className="flex flex-wrap items-center gap-4 mb-4">
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-ink-500 mr-1">场景</span>
          <FilterPill active={scenario === 'all'} onClick={() => setScenario('all')} label="全部" />
          {SCEN_ORDER.map((k) => (
            <FilterPill
              key={k}
              active={scenario === k}
              onClick={() => setScenario(k)}
              label={SCEN[k].label}
            />
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[11px] text-ink-500 mr-1">胜负</span>
          <FilterPill active={outcome === 'all'} onClick={() => setOutcome('all')} label="全部" />
          <FilterPill active={outcome === 'ours'} onClick={() => setOutcome('ours')} label="我方胜" />
          <FilterPill
            active={outcome === 'baseline'}
            onClick={() => setOutcome('baseline')}
            label="Baseline 胜"
          />
        </div>
        <div className="text-[11px] text-ink-300 ml-auto">展示 {filtered.length} / {records.length} 条</div>
      </div>

      {/* 逐条对比卡片 */}
      <div className="space-y-3">
        {filtered.map((r) => (
          <JudgeCard key={r.id} record={r} />
        ))}
        {filtered.length === 0 && (
          <div className="card p-8 text-center text-sm text-ink-500">当前筛选下没有记录。</div>
        )}
      </div>
    </div>
  )
}

function FilterPill({ active, onClick, label }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-3 py-1 rounded-full text-xs transition-colors ${
        active
          ? 'bg-brand text-white font-medium'
          : 'bg-white border border-border text-ink-500 hover:bg-slate-50'
      }`}
    >
      {label}
    </button>
  )
}
