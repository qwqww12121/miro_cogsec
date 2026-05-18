<template>
  <section class="dashboard-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">风险仪表板</p>
        <h3 class="title">四维风险仪表板</h3>
      </div>
      <div class="score-pills">
        <span class="pill">{{ profile?.scenario_type || 'unknown' }}</span>
        <span class="pill strong">{{ counterfactualReport?.risk_level || 'LOW' }}</span>
      </div>
    </div>

    <div class="stats-grid">
      <div class="stat-item">
        <span class="label">综合脆弱度</span>
        <strong>{{ Number(profile?.overall_vulnerability_score || 0).toFixed(1) }}</strong>
      </div>
      <div class="stat-item">
        <span class="label">保护习惯</span>
        <strong>{{ Number(profile?.protection_score || 0).toFixed(1) }}</strong>
      </div>
      <div class="stat-item">
        <span class="label">危险分支 ASS</span>
        <strong>{{ Number(scoreComparison?.branch_a_final?.ASS || 0).toFixed(1) }}</strong>
      </div>
      <div class="stat-item">
        <span class="label">防御分支 ASS</span>
        <strong>{{ Number(scoreComparison?.branch_b_final?.ASS || 0).toFixed(1) }}</strong>
      </div>
    </div>

    <div class="chart-grid">
      <div ref="radarRef" class="chart-shell"></div>
      <div ref="lineRef" class="chart-shell"></div>
    </div>
  </section>
</template>

<script setup>
import * as echarts from 'echarts'
import { onMounted, onUnmounted, ref, watch } from 'vue'

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

const radarRef = ref(null)
const lineRef = ref(null)
let radarChart = null
let lineChart = null

const renderRadar = () => {
  if (!radarRef.value || !props.scoreComparison?.branch_a_final) return
  if (!radarChart) radarChart = echarts.init(radarRef.value)

  const branchA = props.scoreComparison.branch_a_final || {}
  const branchB = props.scoreComparison.branch_b_final || {}

  radarChart.setOption({
    tooltip: { trigger: 'item' },
    legend: {
      bottom: 0,
      textStyle: { color: '#475467' }
    },
    radar: {
      radius: '62%',
      indicator: [
        { name: 'CHS', max: 100 },
        { name: 'ASS', max: 100 },
        { name: 'SSS', max: 100 },
        { name: 'EES', max: 100 }
      ],
      axisName: { color: '#334155', fontWeight: 700 },
      splitArea: { areaStyle: { color: ['#fffaf0', '#fffdf8'] } },
      splitLine: { lineStyle: { color: '#fde7c2' } },
      axisLine: { lineStyle: { color: '#f5d9a8' } }
    },
    series: [
      {
        type: 'radar',
        data: [
          {
            value: [branchA.CHS || 0, branchA.ASS || 0, branchA.SSS || 0, branchA.EES || 0],
            name: '危险分支 A',
            areaStyle: { color: 'rgba(217, 45, 32, 0.18)' },
            lineStyle: { color: '#d92d20', width: 2.5 },
            itemStyle: { color: '#d92d20' }
          },
          {
            value: [branchB.CHS || 0, branchB.ASS || 0, branchB.SSS || 0, branchB.EES || 0],
            name: '防御分支 B',
            areaStyle: { color: 'rgba(2, 122, 72, 0.18)' },
            lineStyle: { color: '#027a48', width: 2.5 },
            itemStyle: { color: '#027a48' }
          }
        ]
      }
    ]
  })
}

const renderLine = () => {
  if (!lineRef.value || !props.scoreComparison?.timeline_a?.length) return
  if (!lineChart) lineChart = echarts.init(lineRef.value)

  const timelineA = props.scoreComparison.timeline_a || []
  const timelineB = props.scoreComparison.timeline_b || []

  const buildSeries = (key, label, color, timeline, dashed = false) => ({
    type: 'line',
    name: label,
    smooth: true,
    showSymbol: false,
    data: timeline.map((item) => [item.t, item[key] ?? 0]),
    lineStyle: {
      color,
      width: 2.2,
      type: dashed ? 'dashed' : 'solid'
    }
  })

  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: {
      bottom: 0,
      textStyle: { color: '#475467', fontSize: 11 }
    },
    grid: {
      left: 44,
      right: 18,
      top: 24,
      bottom: 44
    },
    xAxis: {
      type: 'value',
      minInterval: 1,
      axisLabel: { formatter: (value) => `T${value}` }
    },
    yAxis: {
      type: 'value',
      min: 0,
      max: 100,
      splitLine: { lineStyle: { color: '#e2e8f0', type: 'dashed' } }
    },
    series: [
      buildSeries('CHS', 'A-CHS', '#d92d20', timelineA),
      buildSeries('ASS', 'A-ASS', '#f79009', timelineA),
      buildSeries('CHS', 'B-CHS', '#027a48', timelineB, true),
      buildSeries('ASS', 'B-ASS', '#0ea5e9', timelineB, true)
    ]
  })
}

const handleResize = () => {
  radarChart?.resize()
  lineChart?.resize()
}

watch(() => [props.profile, props.scoreComparison, props.counterfactualReport], () => {
  renderRadar()
  renderLine()
}, { deep: true })

onMounted(() => {
  renderRadar()
  renderLine()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  radarChart?.dispose()
  lineChart?.dispose()
  radarChart = null
  lineChart = null
})
</script>

<style scoped>
.dashboard-card {
  background:
    radial-gradient(circle at top right, rgba(190, 24, 93, 0.07), transparent 30%),
    linear-gradient(180deg, #ffffff 0%, #fffaf5 100%);
  border: 1px solid #f1d7c7;
  border-radius: 24px;
  padding: 22px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.06);
}

.header-row {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.eyebrow {
  margin: 0 0 6px 0;
  color: #c2410c;
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.title {
  margin: 0;
  color: #0f172a;
  font-size: 22px;
  font-weight: 800;
}

.score-pills {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.pill {
  padding: 6px 10px;
  background: #fff1e8;
  color: #c2410c;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.pill.strong {
  background: #fee4e2;
  color: #b42318;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0;
}

.stat-item {
  padding: 14px 16px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px solid #f3dfd1;
  border-radius: 18px;
}

.label {
  display: block;
  color: #667085;
  font-size: 12px;
  margin-bottom: 8px;
}

.stat-item strong {
  color: #101828;
  font-size: 24px;
}

.chart-grid {
  display: grid;
  grid-template-columns: 1fr 1.25fr;
  gap: 16px;
}

.chart-shell {
  height: 320px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid #f2e5dd;
  border-radius: 18px;
}

@media (max-width: 960px) {
  .stats-grid,
  .chart-grid {
    grid-template-columns: 1fr;
  }
}
</style>
