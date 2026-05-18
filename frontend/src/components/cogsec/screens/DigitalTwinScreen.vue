<template>
  <section class="screen-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">模块 1</p>
        <h3 class="title">用户数字孪生屏</h3>
      </div>
      <div class="mode-pill" :class="personaStateVector?.cognitive_mode === 'SYSTEM_1' ? 'danger' : 'safe'">
        {{ personaStateVector?.cognitive_mode || 'SYSTEM_2' }}
      </div>
    </div>

    <p class="summary">{{ profile?.summary || profileSummary }}</p>

    <div class="stats-grid">
      <article class="stat-card">
        <span>置信度</span>
        <strong>{{ Number(personaStateVector?.confidence_level || 0).toFixed(2) }}</strong>
      </article>
      <article class="stat-card">
        <span>存储策略</span>
        <strong>{{ personaStateVector?.storage_policy?.default || sanitization?.storage_policy || 'session_only' }}</strong>
      </article>
      <article class="stat-card">
        <span>T0 延迟</span>
        <strong>{{ Number(t0Data?.latency_ms || 0).toFixed(2) }} ms</strong>
      </article>
      <article class="stat-card">
        <span>PII 重试</span>
        <strong>{{ sanitization?.retry_count || 0 }}</strong>
      </article>
    </div>

    <div class="vector-grid">
      <article
        v-for="item in vectorItems"
        :key="item.key"
        class="vector-card"
      >
        <span>{{ keyLabels[item.key] || item.key }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div class="aux-grid">
      <section class="aux-card">
        <h4>系统切换规则</h4>
        <p>系统1 触发条件：time_pressure &gt; 7 且 emotional_volatility &gt; 7</p>
        <p>系统2 恢复条件：verification_habit &gt;= 6 且 decision_delay &gt;= 6</p>
      </section>
      <section class="aux-card">
        <h4>隐私防护</h4>
        <p>最小必要原则：{{ sanitization?.minimal_necessary ? '已启用' : '未启用' }}</p>
        <p>存储策略：{{ sanitization?.storage_policy || 'session_only' }}</p>
        <p>PII 泄露检测：{{ sanitization?.pii_leak_detected ? '已检出' : '未检出' }}</p>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  profile: {
    type: Object,
    default: () => ({})
  },
  personaStateVector: {
    type: Object,
    default: () => ({})
  },
  sanitization: {
    type: Object,
    default: () => ({})
  },
  t0Data: {
    type: Object,
    default: () => ({})
  }
})

const keyLabels = {
  analytic_control: '分析控制力',
  asset_sensitivity: '资产敏感度',
  authority_compliance: '权威服从度',
  confidence_level: '置信度',
  digital_trust_boundary: '数字信任边界',
  emotional_volatility: '情绪波动性',
  financial_stress: '财务压力',
  fomo_susceptibility: '紧迫感易感性',
  help_seeking_tendency: '求助倾向',
  loss_aversion: '损失厌恶',
  risk_recovery_awareness: '风险复原意识',
  system1_bias: '系统1偏倚',
  system2_control: '系统2控制',
  time_pressure_sensitivity: '时间压力敏感度',
  verification_habit: '核实习惯',
  decision_delay: '决策延迟',
  cognitive_load: '认知负荷',
  social_influence: '社会影响力',
}

const excludedKeys = new Set(['switch_policy', 'storage_policy', 'source_profile', 'cognitive_mode'])

const vectorItems = computed(() => Object.entries(props.personaStateVector || {})
  .filter(([key, value]) => !excludedKeys.has(key) && typeof value !== 'object')
  .map(([key, value]) => ({
    key,
    value: typeof value === 'number' ? value.toFixed(2) : value
  })))

const profileSummary = computed(() => {
  const scenario = props.profile?.scenario_type || 'unknown'
  const vulnerability = Number(props.profile?.overall_vulnerability_score || 0).toFixed(1)
  return `场景 ${scenario}，综合脆弱度 ${vulnerability}，当前画像已作为 MIRO-FISH 主判别运行时输入。`
})
</script>

<style scoped>
.screen-card {
  display: grid;
  gap: 16px;
  background: #fff;
  border: 1px solid #dbe4ee;
  border-radius: 20px;
  padding: 20px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.eyebrow {
  margin: 0 0 6px 0;
  color: #0f766e;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
}

.title {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
}

.mode-pill {
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.mode-pill.safe {
  background: #ecfdf3;
  color: #166534;
}

.mode-pill.danger {
  background: #fee4e2;
  color: #b42318;
}

.summary {
  margin: 0;
  color: #475467;
  line-height: 1.7;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.aux-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.stat-card,
.aux-card {
  background: #f8fafc;
  border: 1px solid #e4ebf3;
  border-radius: 16px;
  padding: 14px;
}

.stat-card span {
  display: block;
  color: #667085;
  font-size: 12px;
  margin-bottom: 6px;
}

.stat-card strong {
  color: #0f172a;
  font-size: 20px;
}

.vector-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.vector-card {
  background: linear-gradient(180deg, #fffdf8 0%, #ffffff 100%);
  border: 1px solid #f2dfb6;
  border-radius: 14px;
  padding: 12px;
  display: grid;
  gap: 6px;
}

.vector-card span,
.aux-card p {
  color: #475467;
  font-size: 13px;
  margin: 0;
  line-height: 1.6;
}

.vector-card strong,
.aux-card h4 {
  color: #0f172a;
  margin: 0;
}

@media (max-width: 1100px) {
  .stats-grid,
  .vector-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .aux-grid {
    grid-template-columns: 1fr;
  }
}
</style>
