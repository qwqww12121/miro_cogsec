<template>
  <section class="screen-card">
    <h3>RiskScorer</h3>
    <div class="kpi-grid">
      <div class="kpi">
        <span>Risk Score</span>
        <strong>{{ Number(finalA?.risk_score || 0).toFixed(1) }}</strong>
      </div>
      <div class="kpi">
        <span>Cognitive Mode</span>
        <strong>{{ finalA?.cognitive_mode || '-' }}</strong>
      </div>
      <div class="kpi">
        <span>Reversibility</span>
        <strong>{{ Number(finalA?.reversibility || 0).toFixed(2) }}</strong>
      </div>
      <div class="kpi">
        <span>Posterior P(scam)</span>
        <strong>{{ Number(finalA?.posterior_probability || 0).toFixed(3) }}</strong>
      </div>
    </div>

    <RiskDashboard
      :profile="profile"
      :score-comparison="scoreComparison"
      :counterfactual-report="counterfactualReport"
    />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import RiskDashboard from '../RiskDashboard.vue'

const props = defineProps({
  profile: {
    type: Object,
    default: () => ({})
  },
  scoreComparison: {
    type: Object,
    default: () => ({})
  },
  counterfactualReport: {
    type: Object,
    default: () => ({})
  }
})

const finalA = computed(() => props.scoreComparison?.branch_a_final || {})
</script>

<style scoped>
.screen-card {
  background: #fff;
  border: 1px solid #d7e3ee;
  border-radius: 18px;
  padding: 18px;
  display: grid;
  gap: 14px;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}
.kpi {
  border: 1px solid #f2dfb6;
  border-radius: 10px;
  background: #fffdf8;
  padding: 10px 12px;
  display: grid;
  gap: 4px;
}
.kpi span {
  color: #667085;
  font-size: 12px;
}
.kpi strong {
  color: #0f172a;
  font-size: 18px;
}
@media (max-width: 960px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
