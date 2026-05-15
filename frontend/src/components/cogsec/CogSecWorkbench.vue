<template>
  <div class="cogsec-shell">
    <div v-if="loading" class="status-card">
      正在以 MIRO-FISH 主链运行时生成认知安全反事实推演...
    </div>

    <div v-else-if="error" class="status-card error">
      {{ error }}
    </div>

    <template v-else-if="analysis">
      <section class="hero-card">
        <div>
          <p class="eyebrow">CogSec / COGNITIVE-DEFENSE-X</p>
          <h2 class="hero-title">{{ analysis.profile?.scenario_type || '未知场景' }} 主判别工作台</h2>
          <p class="hero-summary">
            最终风险来自 WorldState + Fork 双分支轨迹差值，而不是单段文本直接判分。
          </p>
        </div>
        <div class="hero-metrics">
          <div class="metric">
            <span>FinalRisk</span>
            <strong>{{ Number(breakdown?.final_risk || 0).toFixed(1) }}</strong>
          </div>
          <div class="metric">
            <span>Fork</span>
            <strong>{{ analysis.fork_comparison?.fork_point_type || 'N/A' }}</strong>
          </div>
          <div class="metric">
            <span>T0</span>
            <strong>{{ Number(analysis.t0_fast_response?.latency_ms || 0).toFixed(1) }}ms</strong>
          </div>
          <div class="metric">
            <span>E2E</span>
            <strong>{{ Number(analysis.metrics?.end_to_end_ms || 0).toFixed(0) }}ms</strong>
          </div>
        </div>
      </section>

      <section class="guardrail-strip">
        <div class="guard-item">
          <span>Privacy</span>
          <strong>{{ analysis.sanitization?.storage_policy || 'session_only' }}</strong>
        </div>
        <div class="guard-item">
          <span>T0 &lt; 500ms</span>
          <strong>{{ analysis.metrics?.t0_target_met ? 'PASS' : 'WARN' }}</strong>
        </div>
        <div class="guard-item">
          <span>Runtime &lt; 30s</span>
          <strong>{{ analysis.metrics?.end_to_end_target_met ? 'PASS' : 'WARN' }}</strong>
        </div>
        <div class="guard-item">
          <span>Anomalies</span>
          <strong>{{ (analysis.anomalies || []).length }}</strong>
        </div>
      </section>

      <nav class="screen-nav">
        <button
          v-for="item in screens"
          :key="item.key"
          class="screen-btn"
          :class="{ active: activeScreen === item.key }"
          @click="activeScreen = item.key"
        >
          {{ item.label }}
        </button>
      </nav>

      <DigitalTwinScreen
        v-if="activeScreen === 'twin'"
        :profile="analysis.profile"
        :persona-state-vector="analysis.persona_state_vector"
        :sanitization="analysis.sanitization"
        :t0-data="analysis.t0_fast_response"
      />

      <RiskGraphScreen
        v-else-if="activeScreen === 'graph'"
        :graph-bundle="analysis.risk_graph_bundle"
      />

      <CounterfactualEvolutionScreen
        v-else-if="activeScreen === 'fork'"
        :branch-a="analysis.branch_a_log"
        :branch-b="analysis.branch_b_log"
        :fork-comparison="analysis.fork_comparison"
      />

      <RiskCurveScreen
        v-else-if="activeScreen === 'curve'"
        :fork-comparison="analysis.fork_comparison"
        :metrics="analysis.metrics"
      />

      <InterventionPrescriptionScreen
        v-else
        :prescriptions="analysis.intervention_prescriptions || []"
        :report="analysis.counterfactual_report || {}"
        :implementation-status="analysis.implementation_status || {}"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { getCogSecByReport } from '../../api/cogsec'
import CounterfactualEvolutionScreen from './screens/CounterfactualEvolutionScreen.vue'
import DigitalTwinScreen from './screens/DigitalTwinScreen.vue'
import InterventionPrescriptionScreen from './screens/InterventionPrescriptionScreen.vue'
import RiskCurveScreen from './screens/RiskCurveScreen.vue'
import RiskGraphScreen from './screens/RiskGraphScreen.vue'

const props = defineProps({
  reportId: {
    type: String,
    default: ''
  }
})

const loading = ref(false)
const error = ref('')
const analysis = ref(null)
const activeScreen = ref('twin')

const screens = [
  { key: 'twin', label: '1. 用户数字孪生' },
  { key: 'graph', label: '2. 攻击-人-环境图谱' },
  { key: 'fork', label: '3. 双分支反事实推演' },
  { key: 'curve', label: '4. 风险 / 可逆性曲线' },
  { key: 'prescription', label: '5. 个性化干预处方' }
]

const breakdown = computed(() => analysis.value?.metrics?.risk_breakdown || {})

const loadAnalysis = async () => {
  if (!props.reportId) return
  loading.value = true
  error.value = ''

  try {
    const res = await getCogSecByReport(props.reportId)
    analysis.value = res.data
  } catch (err) {
    error.value = err.message || 'CogSec 数据加载失败'
  } finally {
    loading.value = false
  }
}

watch(() => props.reportId, loadAnalysis, { immediate: true })
</script>

<style scoped>
.cogsec-shell {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 18px;
  height: 100%;
  overflow-y: auto;
  background: linear-gradient(180deg, #f6f7f2 0%, #fdfcf7 35%, #ffffff 100%);
}

.status-card,
.hero-card,
.guardrail-strip {
  border-radius: 18px;
  padding: 18px;
  border: 1px solid #dbe4ee;
  background: #ffffff;
}

.status-card {
  min-height: 180px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-weight: 700;
}

.status-card.error {
  color: #b42318;
  border-color: #fecdca;
  background: #fffbfa;
}

.hero-card {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  background:
    radial-gradient(circle at top left, rgba(12, 166, 120, 0.11), transparent 30%),
    linear-gradient(135deg, #0f172a 0%, #122b39 55%, #173f47 100%);
  color: #f8fafc;
  border: none;
}

.hero-title {
  margin: 0;
  font-size: 28px;
}

.hero-summary {
  margin: 10px 0 0 0;
  color: rgba(248, 250, 252, 0.84);
  line-height: 1.7;
}

.eyebrow {
  margin: 0 0 6px 0;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  opacity: 0.72;
}

.hero-metrics {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  min-width: 320px;
}

.metric {
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 12px;
}

.metric span {
  display: block;
  font-size: 12px;
  color: rgba(248, 250, 252, 0.72);
  margin-bottom: 6px;
}

.metric strong {
  font-size: 22px;
}

.guardrail-strip {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.guard-item {
  border-radius: 12px;
  background: #f8fafc;
  border: 1px solid #e4ebf3;
  padding: 12px;
}

.guard-item span {
  display: block;
  color: #667085;
  font-size: 12px;
  margin-bottom: 4px;
}

.guard-item strong {
  color: #0f172a;
}

.screen-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.screen-btn {
  border: 1px solid #d7e3ee;
  background: #fff;
  color: #334155;
  border-radius: 999px;
  padding: 10px 14px;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
}

.screen-btn.active {
  background: #0f766e;
  border-color: #0f766e;
  color: #fff;
}

@media (max-width: 1100px) {
  .hero-card,
  .guardrail-strip {
    grid-template-columns: 1fr;
    display: grid;
  }

  .hero-metrics {
    min-width: 0;
  }
}
</style>
