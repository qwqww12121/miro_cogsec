<template>
  <section class="screen-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">Screen 1</p>
        <h3 class="title">用户数字孪生屏</h3>
      </div>
      <div class="mode-pill" :class="personaStateVector?.cognitive_mode === 'SYSTEM_1' ? 'danger' : 'safe'">
        {{ personaStateVector?.cognitive_mode || 'SYSTEM_2' }}
      </div>
    </div>

    <p class="summary">{{ profile?.summary || profileSummary }}</p>

    <div class="stats-grid">
      <article class="stat-card">
        <span>Confidence</span>
        <strong>{{ Number(personaStateVector?.confidence_level || 0).toFixed(2) }}</strong>
      </article>
      <article class="stat-card">
        <span>Storage Policy</span>
        <strong>{{ personaStateVector?.storage_policy?.default || sanitization?.storage_policy || 'session_only' }}</strong>
      </article>
      <article class="stat-card">
        <span>T0 Latency</span>
        <strong>{{ Number(t0Data?.latency_ms || 0).toFixed(2) }} ms</strong>
      </article>
      <article class="stat-card">
        <span>PII Retry</span>
        <strong>{{ sanitization?.retry_count || 0 }}</strong>
      </article>
    </div>

    <div class="vector-grid">
      <article
        v-for="item in vectorItems"
        :key="item.key"
        class="vector-card"
      >
        <span>{{ item.key }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div class="aux-grid">
      <section class="aux-card">
        <h4>System Switch Policy</h4>
        <p>System 1 trigger: time_pressure &gt; 7 and emotional_volatility &gt; 7</p>
        <p>System 2 re-entry: verification_habit &gt;= 6 and decision_delay &gt;= 6</p>
      </section>
      <section class="aux-card">
        <h4>Privacy Guardrail</h4>
        <p>minimal_necessary: {{ sanitization?.minimal_necessary ? 'true' : 'false' }}</p>
        <p>session_only: {{ sanitization?.storage_policy || 'session_only' }}</p>
        <p>PII leak detected: {{ sanitization?.pii_leak_detected ? 'true' : 'false' }}</p>
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

.stats-grid,
.aux-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  .vector-grid,
  .aux-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
