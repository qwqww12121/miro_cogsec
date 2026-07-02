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

export default function FraudImResult({ data, loading, error }) {
  if (loading) {
    return (
      <Section title="分析进行中">
        <div className="py-12 flex items-center justify-center gap-2 text-sm text-ink-500">
          <Spinner className="w-4 h-4 text-brand" />
          正在调用 CogSec 引擎，预计 5–30 秒…
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
        <Empty title="尚未运行分析" hint="在左侧填写对话内容并点击「开始分析」。" />
      </Section>
    )
  }

  const profile = data.profile || {}
  const metrics = data.metrics || {}
  const strategies = data.strategies || []
  const counter = data.counterfactual_report || {}
  const interventions = data.intervention_prescriptions || []
  const anomalies = data.anomalies || []
  const t0 = data.t0_fast_response || {}

  const overall = profile.overall_vulnerability_score
  const protection = profile.protection_score
  const cog = describeCognitiveMode(data.persona_state_vector?.cognitive_mode)

  return (
    <>
      <RiskHeadline scenarioType={profile.scenario_type} vulnerabilityScore={overall} />

      {/* 业务指标 normal，技术性能指标 muted（视觉上次要于核心结论） */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <StatTile
          label="保护因子均值"
          value={protection != null ? protection.toFixed(2) : '—'}
          hint="防范习惯均值，越高越安全"
          tone="leaf"
          info={GLOSSARY.protection_score}
        />
        <StatTile
          label="检测到话术数"
          value={strategies.length}
          hint="后端策略库命中"
          tone="brand"
        />
        <StatTile
          label="T0 拦截延迟"
          value={metrics.t0_latency_ms != null ? `${metrics.t0_latency_ms} ms` : '—'}
          hint={metrics.t0_target_met ? '✓ 达成 <500ms' : '未达成'}
          tone={metrics.t0_target_met ? 'leaf' : 'sand'}
          prominence="muted"
          info={GLOSSARY.t0_latency}
        />
        <StatTile
          label="端到端耗时"
          value={metrics.end_to_end_ms != null ? `${(metrics.end_to_end_ms / 1000).toFixed(2)} s` : '—'}
          hint={metrics.end_to_end_target_met ? '✓ 达成 <30s' : '超时降级'}
          tone={metrics.end_to_end_target_met ? 'leaf' : 'sand'}
          prominence="muted"
          info={GLOSSARY.end_to_end}
        />
      </div>

      <Section title="场景与画像摘要">
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
            <div className="text-ink-900 leading-relaxed">{profile.summary || profileSummary(profile)}</div>
          </div>
        </div>
      </Section>

      <Section title={`检索到的攻击策略 · ${strategies.length} 条`}>
        {strategies.length === 0 ? (
          <Empty title="未检索到策略" hint="案例库未匹配，已使用默认 fallback。" />
        ) : (
          <ul className="divide-y divide-border">
            {strategies.slice(0, 6).map((s, i) => (
              <li key={i} className="py-3 first:pt-0 last:pb-0">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium text-ink-900 text-sm">{s.tactic_name || s.id}</div>
                  <div className="flex items-center gap-1.5">
                    <span className="tag bg-brand-50 text-brand-600">{describeCialdini(s.cialdini_principle)}</span>
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

      <div className="grid md:grid-cols-2 gap-4">
        <Section title="T0 即时拦截" info={GLOSSARY.t0_latency}>
          <div className="text-sm space-y-2">
            <Row label="是否命中">
              <span className={`tag ${t0.matched ? 'bg-rose-50 text-rose-600' : 'bg-leaf-50 text-leaf-600'}`}>
                {t0.matched ? '命中高危模式' : '未命中'}
              </span>
            </Row>
            <Row label="匹配规则">
              <span className="text-ink-900">{(t0.matched_patterns || []).join(', ') || '—'}</span>
            </Row>
            <Row label="延迟">
              <span className="text-ink-900">{t0.latency_ms != null ? `${t0.latency_ms} ms` : '—'}</span>
            </Row>
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
      </div>

      <Section title="反事实路径报告" info={GLOSSARY.counterfactual}>
        <div className="text-sm text-ink-900 leading-relaxed whitespace-pre-wrap">
          {counter.narrative || counter.summary || '后端未返回叙事内容。'}
        </div>
      </Section>

      <Section title={`干预处方 · ${interventions.length} 条`} info={GLOSSARY.intervention_window}>
        {interventions.length === 0 ? (
          <Empty title="暂无干预建议" />
        ) : (
          <ol className="space-y-3">
            {interventions.map((p, i) => (
              <li key={i} className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-leaf-50 text-leaf-600 text-xs font-semibold flex items-center justify-center flex-none">
                  {i + 1}
                </div>
                <div className="text-sm">
                  <div className="font-medium text-ink-900">
                    {p.action || p.title || `干预 ${i + 1}`}
                  </div>
                  {p.rationale && <div className="text-xs text-ink-500 mt-1">{p.rationale}</div>}
                </div>
              </li>
            ))}
          </ol>
        )}
      </Section>
    </>
  )
}

// 认知模式那一行复用 InfoHint 组件做悬浮解释

function Row({ label, children }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-ink-500 text-xs">{label}</span>
      <div className="text-right text-sm">{children}</div>
    </div>
  )
}

function profileSummary(profile) {
  if (!profile || !profile.scenario_type) return '—'
  return `场景：${describeScenarioType(profile.scenario_type)}；脆弱度 ${(profile.overall_vulnerability_score ?? 0).toFixed(1)}/100。`
}
