<template>
  <div class="main-view">
    <!-- Header -->
    <header class="app-header">
      <div class="header-left">
        <div class="brand" @click="router.push('/')">
          <span class="brand-main">MIROFISH</span>
          <span class="brand-sub">COGSEC MAINLINE</span>
        </div>
      </div>
      
      <div class="header-center">
        <div class="view-switcher">
          <button 
            v-for="mode in viewModes" 
            :key="mode"
            class="switch-btn"
            :class="{ active: viewMode === mode }"
            @click="viewMode = mode"
          >
            {{ viewModeLabels[mode] }}
          </button>
        </div>
      </div>

      <div class="header-right">
        <div class="workflow-step">
          <span class="step-num">Step 4/5</span>
          <span class="step-name">报告生成</span>
        </div>
        <div class="step-divider"></div>
        <span class="runtime-pill">LOCAL GEMMA</span>
        <span class="status-indicator" :class="statusClass">
          <span class="dot"></span>
          {{ statusText }}
        </span>
      </div>
    </header>

    <!-- Main Content Area -->
    <main class="content-area">
      <!-- Left Panel: Graph -->
      <div class="panel-wrapper left" :style="leftPanelStyle">
        <GraphPanel 
          :graphData="graphData"
          :loading="graphLoading"
          :currentPhase="4"
          :isSimulating="false"
          @refresh="refreshGraph"
          @toggle-maximize="toggleMaximize('graph')"
        />
      </div>

      <!-- Right Panel: Step4 报告生成 -->
      <div class="panel-wrapper right" :style="rightPanelStyle">
        <Step4Report
          v-if="viewMode !== 'cogsec'"
          :reportId="currentReportId"
          :simulationId="simulationId"
          :systemLogs="systemLogs"
          @add-log="addLog"
          @update-status="updateStatus"
        />
        <CogSecWorkbench
          v-else
          :reportId="currentReportId"
        />
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import GraphPanel from '../components/GraphPanel.vue'
import Step4Report from '../components/Step4Report.vue'
import CogSecWorkbench from '../components/cogsec/CogSecWorkbench.vue'
import { getProject, getGraphData } from '../api/graph'
import { getSimulation } from '../api/simulation'
import { getReport } from '../api/report'

const route = useRoute()
const router = useRouter()

// Props
const props = defineProps({
  reportId: String
})

// Layout State - 默认切换到工作台视角
const viewMode = ref('cogsec')
const viewModes = ['graph', 'split', 'workbench', 'cogsec']
const viewModeLabels = {
  graph: '图谱',
  split: '双栏',
  workbench: '工作台',
  cogsec: '认知主链'
}

// Data State
const currentReportId = ref(route.params.reportId)
const simulationId = ref(null)
const projectData = ref(null)
const graphData = ref(null)
const graphLoading = ref(false)
const systemLogs = ref([])
const currentStatus = ref('processing') // processing | completed | error

// --- Computed Layout Styles ---
const leftPanelStyle = computed(() => {
  if (viewMode.value === 'graph') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'workbench' || viewMode.value === 'cogsec') return { width: '0%', opacity: 0, transform: 'translateX(-20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

const rightPanelStyle = computed(() => {
  if (viewMode.value === 'workbench' || viewMode.value === 'cogsec') return { width: '100%', opacity: 1, transform: 'translateX(0)' }
  if (viewMode.value === 'graph') return { width: '0%', opacity: 0, transform: 'translateX(20px)' }
  return { width: '50%', opacity: 1, transform: 'translateX(0)' }
})

// --- Status Computed ---
const statusClass = computed(() => {
  return currentStatus.value
})

const statusText = computed(() => {
  if (currentStatus.value === 'error') return 'Error'
  if (currentStatus.value === 'completed') return 'Completed'
  return 'Generating'
})

// --- Helpers ---
const addLog = (msg) => {
  const time = new Date().toLocaleTimeString('en-US', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' }) + '.' + new Date().getMilliseconds().toString().padStart(3, '0')
  systemLogs.value.push({ time, msg })
  if (systemLogs.value.length > 200) {
    systemLogs.value.shift()
  }
}

const updateStatus = (status) => {
  currentStatus.value = status
}

// --- Layout Methods ---
const toggleMaximize = (target) => {
  if (viewMode.value === target) {
    viewMode.value = 'split'
  } else {
    viewMode.value = target
  }
}

// --- Data Logic ---
const loadReportData = async () => {
  try {
    addLog(`加载报告数据: ${currentReportId.value}`)
    
    // 获取 report 信息以获取 simulation_id
    const reportRes = await getReport(currentReportId.value)
    if (reportRes.success && reportRes.data) {
      const reportData = reportRes.data
      simulationId.value = reportData.simulation_id
      
      if (simulationId.value) {
        // 获取 simulation 信息
        const simRes = await getSimulation(simulationId.value)
        if (simRes.success && simRes.data) {
          const simData = simRes.data
          
          // 获取 project 信息
          if (simData.project_id) {
            const projRes = await getProject(simData.project_id)
            if (projRes.success && projRes.data) {
              projectData.value = projRes.data
              addLog(`项目加载成功: ${projRes.data.project_id}`)
              
              // 获取 graph 数据
              if (projRes.data.graph_id) {
                await loadGraph(projRes.data.graph_id)
              }
            }
          }
        }
      }
    } else {
      addLog(`获取报告信息失败: ${reportRes.error || '未知错误'}`)
    }
  } catch (err) {
    addLog(`加载异常: ${err.message}`)
  }
}

const loadGraph = async (graphId) => {
  graphLoading.value = true
  
  try {
    const res = await getGraphData(graphId)
    if (res.success) {
      graphData.value = res.data
      addLog('图谱数据加载成功')
    }
  } catch (err) {
    addLog(`图谱加载失败: ${err.message}`)
  } finally {
    graphLoading.value = false
  }
}

const refreshGraph = () => {
  if (projectData.value?.graph_id) {
    loadGraph(projectData.value.graph_id)
  }
}

// Watch route params
watch(() => route.params.reportId, (newId) => {
  if (newId && newId !== currentReportId.value) {
    currentReportId.value = newId
    loadReportData()
  }
}, { immediate: true })

onMounted(() => {
  addLog('ReportView 初始化')
  loadReportData()
})
</script>

<style scoped>
.main-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.08), transparent 35%),
    linear-gradient(180deg, #f4f7fb 0%, #ffffff 48%, #f8fafc 100%);
  overflow: hidden;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.main-view::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(circle at 90% 10%, rgba(245, 158, 11, 0.12), transparent 26%),
    radial-gradient(circle at 8% 88%, rgba(14, 165, 233, 0.09), transparent 24%);
}

/* Header */
.app-header {
  height: 72px;
  border-bottom: 1px solid #dce3ec;
  border-top: 3px solid #0f766e;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: rgba(255, 255, 255, 0.86);
  backdrop-filter: blur(10px);
  z-index: 100;
  position: relative;
  box-shadow: 0 10px 24px rgba(15, 23, 42, 0.06);
  border-radius: 0 0 18px 18px;
}

.header-center {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
}

.brand {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 800;
  font-size: 17px;
  letter-spacing: 1px;
  cursor: pointer;
  color: #0f172a;
  display: flex;
  flex-direction: column;
  line-height: 1.05;
}

.brand-main {
  font-size: 16px;
}

.brand-sub {
  margin-top: 2px;
  font-size: 10px;
  letter-spacing: 0.12em;
  color: #0f766e;
  font-weight: 700;
}

.view-switcher {
  display: flex;
  background: #eef3f8;
  padding: 4px;
  border-radius: 999px;
  gap: 4px;
  border: 1px solid #d7e2ee;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.06);
}

.switch-btn {
  border: none;
  background: transparent;
  padding: 6px 15px;
  font-size: 12px;
  font-weight: 700;
  color: #667085;
  border-radius: 999px;
  cursor: pointer;
  transition: all 0.2s;
}

.switch-btn.active {
  background: linear-gradient(135deg, #0f766e 0%, #06b6d4 100%);
  color: #f8fafc;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.1);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.runtime-pill {
  font-size: 11px;
  font-weight: 700;
  color: #0f766e;
  background: #e8f7f4;
  border: 1px solid #b6ddd7;
  border-radius: 999px;
  padding: 5px 10px;
  font-family: 'JetBrains Mono', monospace;
  letter-spacing: 0.05em;
}

.workflow-step {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.step-num {
  font-family: 'JetBrains Mono', monospace;
  font-weight: 700;
  color: #999;
}

.step-name {
  font-weight: 700;
  color: #0f172a;
}

.step-divider {
  width: 1px;
  height: 14px;
  background-color: #dce3ec;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #475467;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 999px;
  background: #f7fafc;
  border: 1px solid #dce5ef;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #CCC;
}

.status-indicator.processing .dot { background: #FF9800; animation: pulse 1s infinite; }
.status-indicator.completed .dot { background: #4CAF50; }
.status-indicator.error .dot { background: #F44336; }

@keyframes pulse {
  50% {
    opacity: 0.5;
    box-shadow: 0 0 0 5px rgba(255, 152, 0, 0.15);
  }
}

/* Content */
.content-area {
  flex: 1;
  display: flex;
  position: relative;
  overflow: hidden;
  padding: 14px;
  gap: 14px;
}

.panel-wrapper {
  height: 100%;
  overflow: hidden;
  transition: width 0.4s cubic-bezier(0.25, 0.8, 0.25, 1), opacity 0.3s ease, transform 0.3s ease;
  will-change: width, opacity, transform;
}

.panel-wrapper.left {
  border: 1px solid #dce3ec;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
}

.panel-wrapper.right {
  border: 1px solid #dce3ec;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 10px 26px rgba(15, 23, 42, 0.06);
}
</style>
