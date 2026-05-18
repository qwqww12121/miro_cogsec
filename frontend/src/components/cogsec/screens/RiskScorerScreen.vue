<template>
  <section class="screen-card">
    <h3>风险评分器</h3>
    <div class="kpi-grid">
      <div class="kpi">
        <span>最终风险</span>
        <strong>{{ Number(scoreComparison?.final_risk || scoreComparison?.risk_breakdown?.final_risk || 0).toFixed(1) }}</strong>
      </div>
      <div class="kpi">
        <span>认知模式</span>
        <strong>{{ finalA?.cognitive_mode || '-' }}</strong>
      </div>
      <div class="kpi">
        <span>可逆性 (A末)</span>
        <strong>{{ Number(finalA?.reversibility ?? 0).toFixed(3) }}</strong>
      </div>
      <div class="kpi">
        <span>后验风险 (A末)</span>
        <strong>{{ Number(finalA?.posterior_risk ?? 0).toFixed(3) }}</strong>
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

const finalA = computed(() => {
  const timeline = props.scoreComparison?.timeline_a || []
  return timeline.length ? timeline[timeline.length - 1] : {}
})
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
