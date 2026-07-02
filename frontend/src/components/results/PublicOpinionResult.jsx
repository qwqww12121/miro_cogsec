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
import InfoHint from '../InfoHint'
import RiskHeadline from '../RiskHeadline'
import Spinner from '../Spinner'
import AnomalyTag from '../AnomalyTag'
import {
  GLOSSARY,
  describeCialdini,
  describeCognitiveMode,
  describeScenarioType,
} from '../../scenarios/glossary'

/**
 * 直接消费 backend /api/cogsec/analyze 的真实返回，按"舆情分析"语义重新组织展示，
 * 不再使用 mock。展示哪个字段都来自真实响应，不存在时显示「—」或留空。
 */
export default function PublicOpinionResult({ data, loading, error }) {
  if (loading) {
    return (
      <Section title="分析进行中">
        <div className="py-12 flex items-center justify-center gap-2 text-sm text-ink-500">
          <Spinner className="w-4 h-4 text-leaf" />
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

  const cog = describeCognitiveMode(psv.cognitive_mode)
  const overall = profile.overall_vulnerability_score

  // 情绪向量：直接来自 profile 的真实维度（0-10）
  const emotionDims = [
    { dim: '情绪波动', value: profile.emotional_volatility ?? 0 },
    { dim: '从众敏感', value: profile.social_proof_sensitivity ?? 0 },
    { dim: '稀缺敏感', value: profile.scarcity_sensitivity ?? 0 },
    { dim: '权威服从', value: profile.authority_compliance ?? 0 },
    { dim: '信任阈值', value: profile.trust_threshold ?? 0 },
    { dim: '损失厌恶', value: profile.loss_aversion_threshold ?? 0 },
  ]

  // 关键词热度：用真实 t0_fast_response.matched_patterns + matched_keywords
  const keywordItems = [
    ...(t0.matched_patterns || []),
    ...(t0.matched_keywords || []),
  ]
  const keywordRows = keywordItems.length
    ? keywordItems.slice(0, 8).map((k, i) => ({
        word: typeof k === 'string' ? k : k.pattern || k.keyword || JSON.stringify(k),
        weight: typeof k === 'object' && k.score != null ? k.score : 1 - i * 0.08,
      }))
    : []

  return (
    <>
      <RiskHeadline scenarioType={profile.scenario_type} vulnerabilityScore={overall} />

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile
          label="情绪波动维度"
          value={profile.emotional_volatility != null ? profile.emotional_volatility.toFixed(1) : '—'}
          hint="0–10，越高越易被情绪带动"
          tone="leaf"
        />
        <StatTile
          label="检测到话术数"
          value={strategies.length}
          hint="后端策略库匹配"
          tone="brand"
        />
        <StatTile
          label="命中高危关键词"
          value={keywordItems.length}
          hint="T0 即时检测"
          tone="sand"
        />
        <StatTile
          label="端到端耗时"
          value={metrics.end_to_end_ms != null ? `${(metrics.end_to_end_ms / 1000).toFixed(2)} s` : '—'}
          hint={metrics.end_to_end_target_met ? '✓ <30s' : '超时降级'}
          tone={metrics.end_to_end_target_met ? 'leaf' : 'sand'}
          prominence="muted"
          info={GLOSSARY.end_to_end}
        />
      </div>

      <Section title="场景画像摘要">
        <div className="grid md:grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-[11px] text-ink-500 mb-1">场景类型</div>
            <div className="font-medium text-ink-900">{describeScenarioType(profile.scenario_type)}</div>
          </div>
          <div>
            <div className="text-[11px] text-ink-500 mb-1 flex items-center gap-1">
              认知模式
              <InfoHint text={GLOSSARY.cognitive_mode} />
            </div>
            <div className="font-medium text-ink-900">{cog.label}</div>
          </div>
          <div className="md:col-span-2">
            <div className="text-[11px] text-ink-500 mb-1">摘要</div>
            <div className="text-ink-900 leading-relaxed">
              {profile.summary || `脆弱度 ${overall?.toFixed?.(1) ?? '—'}/100`}
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

        <Section title="T0 命中的高危关键词" info={GLOSSARY.t0_latency}>
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

      <Section title={`话术策略链 · ${strategies.length} 条`}>
        {strategies.length === 0 ? (
          <Empty title="未检索到话术策略" />
        ) : (
          <ul className="divide-y divide-border">
            {strategies.slice(0, 6).map((s, i) => (
              <li key={i} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-ink-900 text-sm">{s.tactic_name || s.id}</div>
                  <div className="flex items-center gap-1.5">
                    <span className="tag bg-leaf-50 text-leaf-600">{describeCialdini(s.cialdini_principle)}</span>
                    <span className="tag bg-slate-100 text-ink-500">强度 {s.intensity_level ?? '—'}</span>
                  </div>
                </div>
                {s.description && (
                  <div className="text-xs text-ink-500 mt-1.5 leading-relaxed">{s.description}</div>
                )}
                {s.typical_dialogue && (
                  <div className="text-xs italic text-ink-500 mt-1.5">"{s.typical_dialogue}"</div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Section title="反事实路径报告" info={GLOSSARY.counterfactual}>
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
              <AnomalyTag key={a} raw={a} />
            ))}
          </div>
        )}
      </Section>
    </>
  )
}
