<template>
  <section class="screen-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">Screen 4</p>
        <h3 class="title">风险 / 可逆性曲线屏</h3>
      </div>
      <div class="risk-pill" :class="riskLevelClass">{{ breakdown?.risk_level || 'LOW' }}</div>
    </div>

    <div class="kpi-grid">
      <article class="kpi-card">
        <span>FinalRisk</span>
        <strong>{{ Number(breakdown?.final_risk || 0).toFixed(1) }}</strong>
      </article>
      <article class="kpi-card">
        <span>PersonaPrior</span>
        <strong>{{ Number(breakdown?.persona_prior || 0).toFixed(3) }}</strong>
      </article>
      <article class="kpi-card">
        <span>TrajectoryGap</span>
        <strong>{{ Number(breakdown?.trajectory_gap || 0).toFixed(3) }}</strong>
      </article>
      <article class="kpi-card">
        <span>IrreversibilityLoss</span>
        <strong>{{ Number(breakdown?.irreversibility_loss || 0).toFixed(3) }}</strong>
      </article>
    </div>

    <div ref="chartRef" class="chart-shell"></div>

    <div class="formula-card">
      FinalRisk = PersonaPrior × AttackMatch × TrajectoryGap × IrreversibilityLoss × EvidenceConsistency
    </div>

    <div class="anomaly-row">
      <span v-for="item in breakdown?.anomaly_flags || []" :key="item" class="anomaly-pill">{{ item }}</span>
    </div>
  </section>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  forkComparison: {
    type: Object,
    default: () => ({})
  },
  metrics: {
    type: Object,
    default: () => ({})
  }
})

const chartRef = ref(null)
let chartInstance = null

const breakdown = computed(() => props.metrics?.risk_breakdown || {})

const riskLevelClass = computed(() => {
  const level = breakdown.value?.risk_level
  if (level === 'CRITICAL') return 'critical'
  if (level === 'HIGH') return 'high'
  if (level === 'MEDIUM') return 'medium'
  return 'low'
})

const renderChart = () => {
  if (!chartRef.value || !(props.forkComparison?.reversibility_curve || []).length) return
  if (!chartInstance) chartInstance = echarts.init(chartRef.value)

  const curve = props.forkComparison.reversibility_curve || []
  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      bottom: 0,
      textStyle: { color: '#475467' }
    },
    grid: {
      left: 40,
      right: 24,
      top: 28,
      bottom: 44
    },
    xAxis: {
      type: 'category',
      data: curve.map((item) => `T${item.step}`)
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 1,
      splitLine: {
        lineStyle: { color: '#e2e8f0', type: 'dashed' }
      }
    },
    series: [
      {
        type: 'line',
        name: 'Branch A Risk',
        smooth: true,
        data: curve.map((item) => item.branch_a_risk),
        lineStyle: { color: '#dc2626', width: 3 }
      },
      {
        type: 'line',
        name: 'Branch B Risk',
        smooth: true,
        data: curve.map((item) => item.branch_b_risk),
        lineStyle: { color: '#16a34a', width: 3 }
      },
      {
        type: 'line',
        name: 'Branch A Reversibility',
        smooth: true,
        data: curve.map((item) => item.branch_a_reversibility),
        lineStyle: { color: '#f97316', width: 2, type: 'dashed' }
      },
      {
        type: 'line',
        name: 'Branch B Reversibility',
        smooth: true,
        data: curve.map((item) => item.branch_b_reversibility),
        lineStyle: { color: '#0f766e', width: 2, type: 'dashed' }
      }
    ]
  })
}

const handleResize = () => chartInstance?.resize()

watch(() => props.forkComparison, renderChart, { deep: true })

onMounted(() => {
  renderChart()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  chartInstance?.dispose()
  chartInstance = null
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
  color: #b54708;
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

.risk-pill {
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.risk-pill.low {
  background: #ecfdf3;
  color: #166534;
}

.risk-pill.medium {
  background: #fff7ed;
  color: #b45309;
}

.risk-pill.high {
  background: #fef3c7;
  color: #92400e;
}

.risk-pill.critical {
  background: #fee4e2;
  color: #b42318;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.kpi-card {
  background: #f8fafc;
  border: 1px solid #e4ebf3;
  border-radius: 16px;
  padding: 14px;
}

.kpi-card span {
  display: block;
  color: #667085;
  font-size: 12px;
  margin-bottom: 6px;
}

.kpi-card strong {
  color: #0f172a;
  font-size: 20px;
}

.chart-shell {
  height: 340px;
  border: 1px solid #edf2f7;
  border-radius: 18px;
  background: #fffdf9;
}

.formula-card {
  padding: 14px 16px;
  border-radius: 16px;
  background: #fff1d6;
  color: #92400e;
  font-weight: 700;
}

.anomaly-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.anomaly-pill {
  background: #f5f3ff;
  color: #6d28d9;
  border-radius: 999px;
  padding: 6px 10px;
  font-size: 12px;
  font-weight: 700;
}

@media (max-width: 960px) {
  .kpi-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
