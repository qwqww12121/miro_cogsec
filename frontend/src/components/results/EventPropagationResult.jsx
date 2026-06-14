import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
} from 'recharts'
import Section from '../Section'
import StatTile from '../StatTile'
import Empty from '../Empty'
import Icon from '../Icon'

/**
 * 消费 /api/cogsec/analyze 的真实返回。事件传播优先使用
 * scenario_extension.propagation，缺失时回退到 branch_a_log / branch_b_log。
 */
export default function EventPropagationResult({ data, loading, error }) {
  if (loading) {
    return (
      <Section title="分析进行中">
        <div className="py-12 text-center text-sm text-ink-500">
          <span className="inline-block w-2 h-2 rounded-full bg-sand mr-2 animate-pulse" />
          推演两条传播路径中…
        </div>
      </Section>
    )
  }
  if (error) {
    return (
      <Section title="分析失败">
        <div className="rounded-md bg-rose-50 border border-rose-100 text-rose-600 text-sm px-3 py-2 flex items-start gap-2">
          <Icon name="alert" className="w-4 h-4 mt-0.5" />
          <div>{String(error)}</div>
        </div>
      </Section>
    )
  }
  if (!data) {
    return (
      <Section title="分析结果">
        <Empty title="尚未运行分析" hint="在左侧填写事件信息后点击「开始分析」。" />
      </Section>
    )
  }

  const profile = data.profile || {}
  const metadata = data.scenario_metadata || {}
  const propagation = data.scenario_extension?.propagation || null
  const branchA = data.branch_a_log || []
  const branchB = data.branch_b_log || []
  const fork = data.fork_comparison || {}
  const counter = data.counterfactual_report || {}
  const strategies = data.strategies || []
  const interventions = data.intervention_prescriptions || []
  const metrics = data.metrics || {}

  const propagationTimeline = buildPropagationTimeline(propagation?.branch_a, propagation?.branch_b)
  const fallbackTimeline = buildBranchTimeline(branchA, branchB)
  const timeline = propagationTimeline.length ? propagationTimeline : fallbackTimeline
  const isPropagationTimeline = propagationTimeline.length > 0
  const totalSteps = isPropagationTimeline
    ? Math.max(propagation?.branch_a?.ticks || 0, propagation?.branch_b?.ticks || 0, timeline.length)
    : Math.max(branchA.length, branchB.length)
  const window = fork.best_intervention_window || counter.best_intervention_window || {}
  const interventionTick = propagation?.fork_point?.intervention_tick ?? propagation?.fork_point?.tick ?? window.open_step
  const interventionHint = propagation?.fork_point?.strategy_type
    || (window.close_step != null ? `窗口到第 ${window.close_step} 步` : '—')
  const trajectoryGap = propagation?.comparison?.coverage_delta
    ?? fork.trajectory_gap
    ?? propagation?.comparison?.peak_risk_delta
  const scenarioType = metadata.canonical || propagation?.branch_a?.scenario_type || profile.scenario_type || '—'

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile
          label="推演总步长"
          value={totalSteps}
          hint={isPropagationTimeline ? 'propagation ticks' : 'branch_a/branch_b 步数'}
          tone="sand"
        />
        <StatTile
          label="路径分离度"
          value={trajectoryGap != null ? trajectoryGap.toFixed(3) : '—'}
          hint={isPropagationTimeline ? 'coverage_delta' : 'fork_comparison.trajectory_gap'}
          tone="brand"
        />
        <StatTile
          label="最佳干预步"
          value={interventionTick != null ? `第 ${interventionTick} 步` : '—'}
          hint={interventionHint}
          tone="leaf"
        />
        <StatTile
          label="端到端耗时"
          value={metrics.end_to_end_ms != null ? `${(metrics.end_to_end_ms / 1000).toFixed(2)} s` : '—'}
          hint={metrics.end_to_end_target_met ? '✓ <30s' : '已完成'}
          tone={metrics.end_to_end_target_met ? 'leaf' : 'brand'}
        />
      </div>

      <Section title="事件场景摘要">
        <div className="text-sm text-ink-900 leading-relaxed">
          {profile.summary || `场景类型：${scenarioType}；脆弱度 ${profile.overall_vulnerability_score?.toFixed?.(1) ?? '—'}/100。`}
        </div>
      </Section>

      <Section title={isPropagationTimeline ? '两条路径的传播覆盖' : '两条路径的累计资产暴露'}>
        {timeline.length === 0 ? (
          <Empty title={isPropagationTimeline ? '后端未返回传播曲线' : '后端未返回分支日志'} />
        ) : (
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={timeline} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="gradA" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#e8736b" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#e8736b" stopOpacity={0.04} />
                  </linearGradient>
                  <linearGradient id="gradB" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#52a882" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#52a882" stopOpacity={0.04} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="step" tick={{ fontSize: 11, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area type="monotone" dataKey="branchA" name="A·攻击路径" stroke="#e8736b" strokeWidth={2} fill="url(#gradA)" />
                <Area type="monotone" dataKey="branchB" name="B·防御路径" stroke="#52a882" strokeWidth={2} fill="url(#gradB)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </Section>

      <Section title="路径分歧风险">
        {timeline.length === 0 ? (
          <Empty title="后端未返回分支日志" />
        ) : (
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart
                data={timeline.map((t) => ({ step: t.step, gap: Number((t.branchA - t.branchB).toFixed(3)) }))}
                margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="step" tick={{ fontSize: 11, fill: '#64748b' }} />
                <YAxis tick={{ fontSize: 11, fill: '#64748b' }} />
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="gap"
                  name={isPropagationTimeline ? 'A−B 覆盖差距' : 'A−B 暴露差距'}
                  stroke="#4a90d9"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </Section>

      <Section title={`关键策略节点 · ${strategies.length} 条`}>
        {strategies.length === 0 ? (
          <Empty title="未识别到关键策略" />
        ) : (
          <ul className="space-y-2">
            {strategies.slice(0, 6).map((s, i) => (
              <li key={i} className="flex items-center gap-3 text-sm">
                <span className="tag bg-sand-50 text-sand-600">{s.tactic_name || s.id}</span>
                <Icon name="arrow-right" className="w-4 h-4 text-ink-300" />
                <span className="text-ink-500 text-xs">{s.cialdini_principle || '—'}</span>
                <span className="ml-auto text-xs text-ink-500">强度 {s.intensity_level ?? '—'}</span>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title={`干预建议 · ${interventions.length} 条`}>
        {interventions.length === 0 ? (
          <Empty title="暂无干预建议" />
        ) : (
          <ol className="space-y-3">
            {interventions.map((p, i) => (
              <li key={i} className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-leaf-50 text-leaf-600 text-xs font-semibold flex items-center justify-center flex-none">
                  {p.step ?? i + 1}
                </div>
                <div className="text-sm text-ink-900 leading-relaxed">
                  <div className="font-medium">{p.action || p.title || `干预 ${i + 1}`}</div>
                  {p.rationale && <div className="text-xs text-ink-500 mt-1">{p.rationale}</div>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Section>

      <Section title="反事实路径报告">
        <div className="text-sm text-ink-900 leading-relaxed whitespace-pre-wrap">
          {counter.summary_branch_a
            ? `[A·攻击路径] ${counter.summary_branch_a}\n[B·防御路径] ${counter.summary_branch_b || ''}`
            : counter.narrative || counter.summary || '后端未返回叙事内容。'}
        </div>
      </Section>
    </>
  )
}

function buildPropagationTimeline(branchA, branchB) {
  const curveA = branchA?.coverage_curve || []
  const curveB = branchB?.coverage_curve || []
  const totalSteps = Math.max(curveA.length, curveB.length)
  if (!totalSteps) return []

  return Array.from({ length: totalSteps }, (_, index) => {
    const pointA = curveA[index] || curveA[curveA.length - 1] || {}
    const pointB = curveB[index] || curveB[curveB.length - 1] || {}
    return {
      step: pointA.tick ?? pointB.tick ?? index + 1,
      branchA: toFixedNumber(pointA.coverage),
      branchB: toFixedNumber(pointB.coverage),
    }
  })
}

function buildBranchTimeline(branchA, branchB) {
  const totalSteps = Math.max(branchA.length, branchB.length)
  const timeline = []
  let aCum = 0
  let bCum = 0

  for (let i = 0; i < totalSteps; i++) {
    aCum += Number(branchA[i]?.asset_exposure_coefficient ?? 0)
    bCum += Number(branchB[i]?.asset_exposure_coefficient ?? 0)
    timeline.push({
      step: i + 1,
      branchA: toFixedNumber(aCum),
      branchB: toFixedNumber(bCum),
    })
  }

  return timeline
}

function toFixedNumber(value) {
  const numeric = Number(value ?? 0)
  return Number.isFinite(numeric) ? Number(numeric.toFixed(3)) : 0
}
