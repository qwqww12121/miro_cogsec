<template>
  <section class="timeline-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">Branch Timeline</p>
        <h3 class="title">双分支演化时间线</h3>
      </div>
      <div class="critical-pill">
        分叉步数 {{ criticalStep || 0 }}
      </div>
    </div>

    <p class="reason-text">{{ criticalReason || '暂无关键分叉说明。' }}</p>

    <div v-if="!branchA.length && !branchB.length" class="empty-state">
      暂无时间线数据
    </div>
    <div v-else ref="chartRef" class="chart-shell"></div>
  </section>
</template>

<script setup>
import * as echarts from 'echarts'
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  branchA: {
    type: Array,
    default: () => []
  },
  branchB: {
    type: Array,
    default: () => []
  },
  criticalStep: {
    type: Number,
    default: 0
  },
  criticalReason: {
    type: String,
    default: ''
  }
})

const chartRef = ref(null)
let chartInstance = null

const stepMax = computed(() => Math.max(props.branchA.length, props.branchB.length, 1))

const renderChart = () => {
  if (!chartRef.value || (!props.branchA.length && !props.branchB.length)) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const toLineData = (branchIndex, items) => items.map((item) => [item.step, branchIndex, item])
  const steps = Array.from({ length: stepMax.value }, (_, index) => index + 1)

  const option = {
    grid: {
      left: 56,
      right: 28,
      top: 36,
      bottom: 28
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: '#111827',
      borderWidth: 0,
      textStyle: { color: '#f8fafc' },
      formatter: (params) => {
        const payload = params.data?.[2] || params.data
        if (!payload || !payload.agent_action) return ''
        return `
          <div style="max-width:260px;">
            <div style="font-weight:700;margin-bottom:8px;">第 ${payload.step} 步</div>
            <div style="color:#cbd5e1;margin-bottom:6px;">${payload.agent_action}</div>
            <div style="line-height:1.6;">${payload.victim_response || ''}</div>
          </div>
        `
      }
    },
    xAxis: {
      type: 'value',
      min: 1,
      max: stepMax.value,
      interval: 1,
      axisLabel: {
        formatter: (value) => `S${value}`
      },
      splitLine: {
        lineStyle: { color: '#e2e8f0', type: 'dashed' }
      }
    },
    yAxis: {
      type: 'category',
      data: ['危险分支 A', '防御分支 B'],
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#334155',
        fontWeight: 700
      }
    },
    series: [
      {
        type: 'line',
        data: steps.map((step) => [step, 0]),
        lineStyle: { color: '#d92d20', width: 3 },
        symbol: 'none',
        z: 1
      },
      {
        type: 'line',
        data: steps.map((step) => [step, 1]),
        lineStyle: { color: '#027a48', width: 3 },
        symbol: 'none',
        z: 1
      },
      {
        type: 'effectScatter',
        data: toLineData(0, props.branchA),
        symbolSize: 16,
        itemStyle: { color: '#d92d20' },
        rippleEffect: { scale: 3.5, brushType: 'stroke' },
        z: 3
      },
      {
        type: 'effectScatter',
        data: toLineData(1, props.branchB),
        symbolSize: 16,
        itemStyle: { color: '#039855' },
        rippleEffect: { scale: 3.5, brushType: 'stroke' },
        z: 3
      }
    ],
    graphic: props.criticalStep
      ? [
          {
            type: 'line',
            left: `${(props.criticalStep / stepMax.value) * 100}%`,
            top: 24,
            bottom: 24,
            shape: { x1: 0, y1: 0, x2: 0, y2: 260 },
            style: { stroke: '#0f172a', lineDash: [5, 5], lineWidth: 1.5 }
          }
        ]
      : []
  }

  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => [props.branchA, props.branchB, props.criticalStep, props.criticalReason], renderChart, { deep: true })

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
.timeline-card {
  background: linear-gradient(180deg, #fffdf8 0%, #ffffff 100%);
  border: 1px solid #f2dfb6;
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
  color: #b54708;
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

.critical-pill {
  background: #fff1d6;
  color: #b54708;
  padding: 7px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 800;
}

.reason-text {
  margin: 14px 0 16px 0;
  color: #475467;
  line-height: 1.7;
}

.chart-shell {
  height: 300px;
}

.empty-state {
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-weight: 600;
}
</style>
