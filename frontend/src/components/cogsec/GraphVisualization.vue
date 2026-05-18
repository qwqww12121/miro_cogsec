<template>
  <section class="viz-card">
    <div class="card-header">
      <div>
        <p class="eyebrow">威胁图谱</p>
        <h3 class="title">认知风险关系图</h3>
      </div>
      <div class="meta-badge">
        <span>{{ graphData?.nodes?.length || 0 }} 节点</span>
        <span>{{ graphData?.links?.length || 0 }} 连接</span>
      </div>
    </div>

    <div v-if="!graphData?.nodes?.length" class="empty-state">
      暂无图谱数据
    </div>
    <div v-else ref="chartRef" class="chart-shell"></div>

    <div class="legend-row">
      <span class="legend-item"><i class="dot red"></i>高风险</span>
      <span class="legend-item"><i class="dot amber"></i>中风险</span>
      <span class="legend-item"><i class="dot green"></i>低风险</span>
    </div>
  </section>
</template>

<script setup>
import * as echarts from 'echarts'
import { onMounted, onUnmounted, ref, watch } from 'vue'

const props = defineProps({
  graphData: {
    type: Object,
    default: () => ({ nodes: [], links: [], categories: [] })
  }
})

const chartRef = ref(null)
let chartInstance = null

const riskColor = (value = 0) => {
  if (value >= 7.5) return '#b42318'
  if (value >= 4.5) return '#f79009'
  return '#12715b'
}

const renderChart = () => {
  if (!chartRef.value || !props.graphData?.nodes?.length) return

  if (!chartInstance) {
    chartInstance = echarts.init(chartRef.value)
  }

  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: '#111827',
      borderWidth: 0,
      textStyle: { color: '#f9fafb' },
      formatter: (params) => {
        if (params.dataType === 'node') {
          const description = params.data.description || '暂无说明'
          return `
            <div style="max-width:260px;">
              <div style="font-weight:700;margin-bottom:6px;">${params.data.name}</div>
              <div style="font-size:12px;color:#cbd5e1;">风险值 ${Number(params.data.risk || 0).toFixed(1)}</div>
              <div style="margin-top:8px;line-height:1.6;">${description}</div>
            </div>
          `
        }
        return `${params.data.source} → ${params.data.target}<br/>${params.data.label || ''}`
      }
    },
    animationDuration: 900,
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        force: {
          repulsion: 420,
          gravity: 0.08,
          edgeLength: [90, 180]
        },
        categories: props.graphData.categories || [],
        label: {
          show: true,
          color: '#0f172a',
          fontSize: 11,
          fontWeight: 600
        },
        edgeLabel: {
          show: true,
          formatter: (params) => params.data.label || '',
          fontSize: 10,
          color: '#64748b'
        },
        lineStyle: {
          color: '#cbd5e1',
          width: 1.5,
          curveness: 0.18
        },
        emphasis: {
          focus: 'adjacency',
          scale: 1.15
        },
        data: (props.graphData.nodes || []).map((node) => ({
          ...node,
          itemStyle: {
            color: riskColor(node.risk),
            shadowBlur: 18,
            shadowColor: `${riskColor(node.risk)}55`
          }
        })),
        links: props.graphData.links || []
      }
    ]
  }

  chartInstance.setOption(option)
}

const handleResize = () => {
  chartInstance?.resize()
}

watch(() => props.graphData, renderChart, { deep: true })

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
.viz-card {
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.08), transparent 32%),
    linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
  border: 1px solid #dbe4ee;
  border-radius: 24px;
  padding: 22px;
  box-shadow: 0 18px 45px rgba(15, 23, 42, 0.06);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  margin-bottom: 18px;
}

.eyebrow {
  margin: 0 0 6px 0;
  color: #0f766e;
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

.meta-badge {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.meta-badge span {
  background: #e2f3ef;
  color: #0f766e;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.chart-shell {
  height: 420px;
}

.empty-state {
  height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #64748b;
  font-weight: 600;
}

.legend-row {
  margin-top: 12px;
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.dot.red { background: #b42318; }
.dot.amber { background: #f79009; }
.dot.green { background: #12715b; }
</style>
