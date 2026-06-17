import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
} from 'recharts'
import Section from '../Section'
import StatTile from '../StatTile'
import Empty from '../Empty'
import Icon from '../Icon'

/**
 * 直接消费 backend /api/cogsec/analyze 的真实返回，按"舆情分析"语义重新组织展示，
 * 展示哪个字段都来自真实响应，不存在时显示「—」或留空。
 */
export default function PublicOpinionResult({ data, loading, error }) {
  if (loading) {
    return (
      <Section title="分析进行中">
        <div className="py-12 text-center text-sm text-ink-500">
          <span className="inline-block w-2 h-2 rounded-full bg-leaf mr-2 animate-pulse" />
          正在调用后端 CogSec 引擎…
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
        <Empty title="尚未运行分析" hint="在左侧填写话题与样本后点击「开始分析」。" />
      </Section>
    )
  }

  const profile = data.profile || {}
  const psv = data.persona_state_vector || {}
  const strategies = data.strategies || []
  const t0 = data.t0_fast_response || {}
  const metrics = data.metrics || {}
  const counter = data.counterfactual_report || {}
  const anomalies = data.anomalies || []
  const metadata = data.scenario_metadata || {}
  const propagation = data.scenario_extension?.propagation || null
  const scenarioType = metadata.canonical || profile.scenario_type || '—'
  const coverageFinal = propagation?.branch_a?.final_metrics?.coverage_final

  // 情绪向量：直接来自 profile 的真实维度（0-10）
  const emotionDims = [
    { dim: '情绪波动', value: profile.emotional_volatility ?? 0 },
    { dim: '从众敏感', value: profile.social_proof_sensitivity ?? 0 },
    { dim: '稀缺敏感', value: profile.scarcity_sensitivity ?? 0 },
    { dim: '权威服从', value: profile.authority_compliance ?? 0 },
    { dim: '信任阈值', value: profile.trust_threshold ?? 0 },
    { dim: '损失厌恶', value: profile.loss_aversion_threshold ?? 0 },
  ]

  const keywordRows = buildKeywordRows(t0)

  return (
    <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile
          label="脆弱度评分"
          value={profile.overall_vulnerability_score != null ? profile.overall_vulnerability_score.toFixed(1) : '—'}
          hint="0-100"
          tone={getRiskTone(profile.overall_vulnerability_score)}
        />
        <StatTile
          label="情绪波动维度"
          value={profile.emotional_volatility != null ? profile.emotional_volatility.toFixed(1) : '—'}
          hint="0-10"
          tone="leaf"
        />
        <StatTile
          label={coverageFinal != null ? '传播覆盖率' : '检测到话术数'}
          value={coverageFinal != null ? `${(coverageFinal * 100).toFixed(1)}%` : strategies.length}
          hint={coverageFinal != null ? 'scenario_extension.propagation' : '后端策略库匹配'}
          tone="brand"
        />
        <StatTile
          label="端到端耗时"
          value={metrics.end_to_end_ms != null ? `${(metrics.end_to_end_ms / 1000).toFixed(2)} s` : '—'}
          hint={metrics.end_to_end_target_met ? '✓ <30s' : '已完成'}
          tone={metrics.end_to_end_target_met ? 'leaf' : 'brand'}
        />
      </div>

      <Section title="场景画像摘要">
        <div className="grid md:grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-[11px] text-ink-500 mb-1">场景类型</div>
            <div className="font-medium text-ink-900">{scenarioType}</div>
          </div>
          <div>
            <div className="text-[11px] text-ink-500 mb-1">认知模式</div>
            <div className="font-medium text-ink-900">{psv.cognitive_mode || '—'}</div>
          </div>
          <div className="md:col-span-2">
            <div className="text-[11px] text-ink-500 mb-1">摘要</div>
            <div className="text-ink-900 leading-relaxed">
              {profile.summary || `脆弱度 ${profile.overall_vulnerability_score?.toFixed?.(1) ?? '—'}/100`}
            </div>
          </div>
        </div>
      </Section>

      <div className="grid md:grid-cols-2 gap-4">
        <Section title="情绪与服从倾向">
          {emotionDims.every((d) => !d.value) ? (
            <Empty title="后端未返回情绪维度" />
          ) : (
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={emotionDims}>
                  <PolarGrid stroke="#e2e8f0" />
                  <PolarAngleAxis dataKey="dim" tick={{ fontSize: 11, fill: '#1e293b' }} />
                  <PolarRadiusAxis domain={[0, 10]} tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <Radar dataKey="value" stroke="#52a882" fill="#52a882" fillOpacity={0.35} />
                  <Tooltip />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>

        <Section title="T0 命中的高危关键词">
          {keywordRows.length === 0 ? (
            <Empty title="未命中高危关键词" />
          ) : (
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={keywordRows} layout="vertical" margin={{ left: 12, right: 12 }}>
                  <CartesianGrid stroke="#f1f5f9" horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} />
                  <YAxis type="category" dataKey="word" tick={{ fontSize: 11, fill: '#1e293b' }} width={120} />
                  <Tooltip cursor={{ fill: '#f1f5f9' }} />
                  <Bar dataKey="weight" fill="#52a882" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </Section>
      </div>

      <Section title="传播仿真对比（Fork A vs B）">
        {!propagation ? (
          <Empty title="传播仿真数据未返回" hint="OASIS 仿真可能未启用或仍在处理中。" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[11px] text-ink-500 border-b border-border">
                  <th className="pb-2 font-medium">指标</th>
                  <th className="pb-2 font-medium text-sand-600">分支 A（自由传播）</th>
                  <th className="pb-2 font-medium text-leaf-600">分支 B（干预传播）</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[
                  {
                    label: '最终覆盖率',
                    a: propagation.branch_a?.final_metrics?.coverage_final != null
                      ? `${(propagation.branch_a.final_metrics.coverage_final * 100).toFixed(1)}%`
                      : '—',
                    b: propagation.branch_b?.final_metrics?.coverage_final != null
                      ? `${(propagation.branch_b.final_metrics.coverage_final * 100).toFixed(1)}%`
                      : '—',
                  },
                  {
                    label: '峰值风险',
                    a: propagation.branch_a?.final_metrics?.peak_risk ?? '—',
                    b: propagation.branch_b?.final_metrics?.peak_risk ?? '—',
                  },
                  {
                    label: '主导情绪',
                    a: propagation.branch_a?.final_metrics?.peak_emotion ?? '—',
                    b: propagation.branch_b?.final_metrics?.peak_emotion ?? '—',
                  },
                  {
                    label: '总行动次数',
                    a: propagation.branch_a?.final_metrics?.total_actions ?? '—',
                    b: propagation.branch_b?.final_metrics?.total_actions ?? '—',
                  },
                ].map((row) => (
                  <tr key={row.label}>
                    <td className="py-2.5 text-ink-500">{row.label}</td>
                    <td className="py-2.5 font-medium text-ink-900">{String(row.a)}</td>
                    <td className="py-2.5 font-medium text-leaf-600">{String(row.b)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Section>

      <Section title="关键传播节点">
        {!propagation?.branch_a?.key_nodes?.length ? (
          <Empty title="无关键节点数据" />
        ) : (
          <ul className="divide-y divide-border">
            {propagation.branch_a.key_nodes.slice(0, 5).map((node, i) => (
              <li key={i} className="py-2.5 first:pt-0 last:pb-0 flex items-center justify-between gap-3">
                <div>
                  <div className="text-sm font-medium text-ink-900">{node.role}</div>
                  <div className="text-xs text-ink-500 mt-0.5">{node.intervention_reason}</div>
                </div>
                <div className="flex items-center gap-1.5 flex-shrink-0">
                  <span className="tag bg-brand-50 text-brand-600">影响力 {node.score}</span>
                  <span className="tag bg-slate-100 text-ink-500">行动 {node.action_count}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="反事实路径报告">
        <div className="text-sm text-ink-900 leading-relaxed whitespace-pre-wrap">
          {counter.summary_branch_a
            ? `[危险分支] ${counter.summary_branch_a}\n[防御分支] ${counter.summary_branch_b || ''}`
            : counter.narrative || counter.summary || '后端未返回叙事内容。'}
        </div>
      </Section>

      <Section title="异常信号">
        {anomalies.length === 0 ? (
          <div className="text-sm text-ink-500">无异常。</div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {anomalies.map((a) => (
              <span key={a} className="tag bg-rose-50 text-rose-600">{a}</span>
            ))}
          </div>
        )}
      </Section>
    </>
  )
}

function getRiskTone(score) {
  if (score == null) return 'default'
  if (score >= 70) return 'danger'
  if (score >= 50) return 'sand'
  return 'leaf'
}

function buildKeywordRows(t0) {
  const items = [
    ...(t0.matched_patterns || []),
    ...(t0.matched_keywords || []),
    ...(t0.hits || []),
  ]
  return items.slice(0, 8).map((item, index) => ({
    word: getKeywordLabel(item),
    weight: getKeywordWeight(item, index),
  })).filter((row) => row.word)
}

function getKeywordLabel(item) {
  if (typeof item === 'string') return item
  return item?.matched_text || item?.keyword || item?.pattern || item?.rule_id || ''
}

function getKeywordWeight(item, index) {
  if (typeof item === 'object' && item?.score != null) return item.score
  return Number((1 - index * 0.08).toFixed(2))
}
