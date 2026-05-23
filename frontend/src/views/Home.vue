<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand">
        <span class="brand-main">COGSEC</span>
        <span class="brand-sub">COGNITIVE DEFENSE SYSTEM</span>
      </div>
      <div class="nav-links">
        <button v-if="mode === 'result'" @click="resetToInput" class="back-btn">
          ← 新建分析
        </button>
        <a href="https://github.com/qwqww12121/miro_cogsec" target="_blank" class="github-link">
          GitHub <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <!-- 输入模式 -->
    <div v-if="mode === 'input'" class="main-content">
      <!-- Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">认知安全分析</span>
            <span class="version-text">/ CogSec-MiroFish v3.0</span>
          </div>

          <h1 class="main-title">
            识别认知操控<br>
            <span class="gradient-text">阻断诈骗路径</span>
          </h1>

          <div class="hero-desc">
            <p>
              粘贴一段可疑对话，<span class="highlight-bold">CogSec</span> 主链将在毫秒级内完成 T0 快速响应、隐私脱敏、18维认知画像提取，并基于 Fork A/B 双分支推演计算<span class="highlight-orange">最终风险得分</span>与个性化干预处方。
            </p>
            <p class="slogan-text">
              先分析，再行动 — 让 AI 守住认知防线<span class="blinking-cursor">_</span>
            </p>
          </div>

          <div class="hero-pills">
            <span class="hero-pill">T0 FastResponder</span>
            <span class="hero-pill">Privacy Sanitizer</span>
            <span class="hero-pill">Cognitive Profiler</span>
            <span class="hero-pill">Threat RAG</span>
            <span class="hero-pill">Fork A/B</span>
            <span class="hero-pill">RiskScorer</span>
          </div>

          <div class="decoration-square"></div>
        </div>

        <div class="hero-right">
          <div class="hero-kpi-card">
            <div class="kpi-row">
              <span class="kpi-label">T0 目标延迟</span>
              <span class="kpi-value">&lt;500ms</span>
            </div>
            <div class="kpi-row">
              <span class="kpi-label">画像维度</span>
              <span class="kpi-value">18 维</span>
            </div>
            <div class="kpi-row">
              <span class="kpi-label">分支仿真</span>
              <span class="kpi-value">Fork A / B</span>
            </div>
            <div class="kpi-row">
              <span class="kpi-label">风险阈值</span>
              <span class="kpi-value">极危 ≥ 75</span>
            </div>
          </div>

          <button class="scroll-down-btn" @click="scrollToConsole">↓</button>
        </div>
      </section>

      <!-- 分析控制台 -->
      <section class="dashboard-section" ref="consoleRef">
        <!-- 左栏：Pipeline 步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> CogSec 主链
          </div>

          <h2 class="section-title">分析就绪</h2>
          <p class="section-desc">粘贴可疑对话或描述诈骗场景，主链将自动完成以下推演序列</p>

          <div class="steps-container">
            <div class="steps-header">
              <span class="diamond-icon">◇</span> 推演流水线
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">T0</span>
                <div class="step-info">
                  <div class="step-title">快速响应</div>
                  <div class="step-desc">关键词匹配 & 场景识别 & 初步风险标记，目标延迟 &lt;500ms</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">P1</span>
                <div class="step-info">
                  <div class="step-title">隐私脱敏</div>
                  <div class="step-desc">Presidio 识别 & 局部替换敏感实体，确保分析数据最小化</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">P2</span>
                <div class="step-info">
                  <div class="step-title">认知画像提取</div>
                  <div class="step-desc">18维特征向量 — 状态层、易感层、保护层三组指标</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">P3</span>
                <div class="step-info">
                  <div class="step-title">威胁知识检索</div>
                  <div class="step-desc">ChromaDB RAG 检索相似欺诈案例，提供参考证据链</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">P4</span>
                <div class="step-info">
                  <div class="step-title">Fork A/B 推演</div>
                  <div class="step-desc">分支A: 顺从路径 / 分支B: 干预核实路径，计算轨迹差值</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">P5</span>
                <div class="step-info">
                  <div class="step-title">风险评分 & 处方</div>
                  <div class="step-desc">5因子复合公式计算 FinalRisk，生成个性化干预建议</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：输入控制台 -->
        <div class="right-panel">
          <div class="console-box">
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 场景输入</span>
                <span class="console-meta">支持: 对话文本 / 短信描述 / 事件经过</span>
              </div>

              <div class="input-wrapper">
                <textarea
                  v-model="scenarioText"
                  class="code-input"
                  placeholder="// 粘贴可疑对话内容或描述诈骗场景&#10;// 例: 对方自称公安局，要求配合资金核查，需转账至安全账户..."
                  rows="12"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">引擎: CogSec-MiroFish v3.0</div>
              </div>
            </div>

            <div v-if="error" class="error-banner">
              分析失败: {{ error }}
            </div>

            <div class="console-section btn-section">
              <button
                class="start-engine-btn"
                @click="runAnalysis"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">开始认知安全分析</span>
                <span v-else class="loading-text">
                  <span class="loading-dot">●</span> {{ loadingStep }}
                </span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>

    <!-- 结果模式 -->
    <div v-else-if="mode === 'result'" class="result-content">
      <div class="result-hero">
        <div class="result-hero-left">
          <p class="eyebrow">CogSec / COGNITIVE-DEFENSE-X</p>
          <h2 class="result-title">{{ analysis.profile?.scenario_type || '未知场景' }} 主判别工作台</h2>
          <p class="result-summary">最终风险来自 WorldState + Fork 双分支轨迹差值，而非单段文本直接判分。</p>
        </div>
        <div class="result-metrics">
          <div class="result-metric" :class="riskLevelClass">
            <span>最终风险</span>
            <strong>{{ Number(breakdown?.final_risk || 0).toFixed(1) }}</strong>
          </div>
          <div class="result-metric">
            <span>触发节点</span>
            <strong>{{ analysis.fork_comparison?.fork_point_type || 'N/A' }}</strong>
          </div>
          <div class="result-metric">
            <span>T0 延迟</span>
            <strong>{{ Number(analysis.t0_fast_response?.latency_ms || 0).toFixed(1) }}ms</strong>
          </div>
          <div class="result-metric">
            <span>端到端延迟</span>
            <strong>{{ Number(analysis.metrics?.end_to_end_ms || 0).toFixed(0) }}ms</strong>
          </div>
        </div>
      </div>

      <div class="guardrail-strip">
        <div class="guard-item">
          <span>隐私保护</span>
          <strong>{{ analysis.sanitization?.storage_policy || 'session_only' }}</strong>
        </div>
        <div class="guard-item">
          <span>T0 &lt; 500ms</span>
          <strong>{{ analysis.metrics?.t0_target_met ? '达标' : '超时' }}</strong>
        </div>
        <div class="guard-item">
          <span>运行 &lt; 30s</span>
          <strong>{{ analysis.metrics?.end_to_end_target_met ? '达标' : '超时' }}</strong>
        </div>
        <div class="guard-item">
          <span>异常数</span>
          <strong>{{ (analysis.anomalies || []).length }}</strong>
        </div>
      </div>

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
        v-else-if="activeScreen === 'prescription'"
        :prescriptions="analysis.intervention_prescriptions || []"
        :report="analysis.counterfactual_report || {}"
        :implementation-status="analysis.implementation_status || {}"
      />
      <T0FastResponderScreen
        v-else-if="activeScreen === 't0'"
        :data="analysis.t0_fast_response"
      />
      <PrivacySanitizerScreen
        v-else-if="activeScreen === 'privacy'"
        :data="analysis.sanitization"
      />
      <CognitiveProfileScreen
        v-else-if="activeScreen === 'cognitive'"
        :profile="analysis.profile"
        :strategies="analysis.strategies || []"
      />
      <RiskScorerScreen
        v-else-if="activeScreen === 'scorer'"
        :profile="analysis.profile"
        :score-comparison="analysis.counterfactual_report?.score_comparison"
        :counterfactual-report="analysis.counterfactual_report"
      />
      <CounterfactualReporterScreen
        v-else
        :report="analysis.counterfactual_report || {}"
        :branch-a="analysis.branch_a_log || []"
        :branch-b="analysis.branch_b_log || []"
        :graph-data="analysis.risk_graph_bundle"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { analyzeCogSec } from '../api/cogsec'
import CognitiveProfileScreen from '../components/cogsec/screens/CognitiveProfileScreen.vue'
import CounterfactualEvolutionScreen from '../components/cogsec/screens/CounterfactualEvolutionScreen.vue'
import CounterfactualReporterScreen from '../components/cogsec/screens/CounterfactualReporterScreen.vue'
import DigitalTwinScreen from '../components/cogsec/screens/DigitalTwinScreen.vue'
import InterventionPrescriptionScreen from '../components/cogsec/screens/InterventionPrescriptionScreen.vue'
import PrivacySanitizerScreen from '../components/cogsec/screens/PrivacySanitizerScreen.vue'
import RiskCurveScreen from '../components/cogsec/screens/RiskCurveScreen.vue'
import RiskGraphScreen from '../components/cogsec/screens/RiskGraphScreen.vue'
import RiskScorerScreen from '../components/cogsec/screens/RiskScorerScreen.vue'
import T0FastResponderScreen from '../components/cogsec/screens/T0FastResponderScreen.vue'

const scenarioText = ref('')
const loading = ref(false)
const error = ref('')
const mode = ref('input')
const analysis = ref(null)
const activeScreen = ref('twin')
const loadingStep = ref('T0 快速响应中...')
const consoleRef = ref(null)

const screens = [
  { key: 'twin', label: '1. 数字孪生' },
  { key: 'graph', label: '2. 风险图谱' },
  { key: 'fork', label: '3. 双分支推演' },
  { key: 'curve', label: '4. 风险曲线' },
  { key: 'prescription', label: '5. 干预处方' },
  { key: 't0', label: '6. T0响应' },
  { key: 'privacy', label: '7. 隐私脱敏' },
  { key: 'cognitive', label: '8. 认知画像' },
  { key: 'scorer', label: '9. 风险评分' },
  { key: 'cf', label: '10. 对照报告' }
]

const loadingSteps = [
  'T0 快速响应中...',
  '隐私脱敏处理中...',
  '提取认知画像 (18维)...',
  '威胁知识库检索中...',
  'Fork A/B 双分支推演...',
  '风险评分 & 生成干预处方...'
]

const canSubmit = computed(() => scenarioText.value.trim().length >= 10)
const breakdown = computed(() => analysis.value?.metrics?.risk_breakdown || {})
const riskLevelClass = computed(() => {
  const score = breakdown.value?.final_risk || 0
  if (score >= 75) return 'risk-critical'
  if (score >= 50) return 'risk-high'
  if (score >= 25) return 'risk-medium'
  return 'risk-low'
})

const scrollToConsole = () => {
  consoleRef.value?.scrollIntoView({ behavior: 'smooth' })
}

let stepTimer = null

const runAnalysis = async () => {
  if (!canSubmit.value || loading.value) return
  loading.value = true
  error.value = ''

  let stepIdx = 0
  loadingStep.value = loadingSteps[0]
  stepTimer = setInterval(() => {
    stepIdx++
    if (stepIdx >= loadingSteps.length) {
      clearInterval(stepTimer)
      return
    }
    loadingStep.value = loadingSteps[stepIdx]
  }, 2000)

  try {
    const res = await analyzeCogSec({ scenario: scenarioText.value })
    if (res.success) {
      analysis.value = res.data
      mode.value = 'result'
      activeScreen.value = 'twin'
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } else {
      error.value = res.error || '分析失败，请检查后端服务是否已启动'
    }
  } catch (err) {
    error.value = err.message || '网络错误，请确认后端服务已启动（npm run backend）'
  } finally {
    clearInterval(stepTimer)
    loading.value = false
    loadingStep.value = loadingSteps[0]
  }
}

const resetToInput = () => {
  mode.value = 'input'
  analysis.value = null
  error.value = ''
}
</script>

<style scoped>
:root {
  --black: #0f172a;
  --white: #ffffff;
  --orange: #f97316;
  --gray-light: #f4f7fb;
  --gray-text: #475467;
  --border: #dce3ec;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
}

.home-container {
  min-height: 100vh;
  background:
    radial-gradient(circle at 8% -10%, rgba(15, 118, 110, 0.1), transparent 40%),
    radial-gradient(circle at 95% 8%, rgba(249, 115, 22, 0.08), transparent 35%),
    var(--gray-light);
  font-family: var(--font-sans);
  color: var(--black);
  position: relative;
}

.home-container::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(120deg, rgba(15, 118, 110, 0.04) 0%, transparent 38%),
    linear-gradient(-120deg, rgba(249, 115, 22, 0.04) 0%, transparent 36%);
}

/* ── Navbar ── */
.navbar {
  position: sticky;
  top: 0;
  z-index: 20;
  height: 68px;
  background: rgba(15, 23, 42, 0.9);
  backdrop-filter: blur(10px);
  color: #f8fafc;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.12);
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.18);
}

.nav-brand {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  line-height: 1.1;
}

.brand-main {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 2px;
  font-size: 1.2rem;
  color: #5eead4;
}

.brand-sub {
  margin-top: 3px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.14em;
  color: #cbd5e1;
  font-weight: 600;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 20px;
}

.back-btn {
  background: rgba(94, 234, 212, 0.15);
  border: 1px solid rgba(94, 234, 212, 0.4);
  color: #5eead4;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  padding: 6px 14px;
  cursor: pointer;
  border-radius: 6px;
  transition: all 0.2s;
}

.back-btn:hover {
  background: rgba(94, 234, 212, 0.25);
}

.github-link {
  color: #cbd5e1;
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: color 0.2s;
}

.github-link:hover {
  color: #fdba74;
}

/* ── Main content ── */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 52px 40px 70px;
}

/* ── Hero ── */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 48px;
  background: rgba(255, 255, 255, 0.78);
  border: 1px solid var(--border);
  box-shadow: 0 22px 46px rgba(15, 23, 42, 0.08);
  border-radius: 24px;
  padding: 40px;
}

.hero-left {
  flex: 1;
  padding-right: 60px;
}

.tag-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin-bottom: 25px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
}

.orange-tag {
  background: var(--orange);
  color: var(--white);
  padding: 4px 10px;
  font-weight: 700;
  letter-spacing: 1px;
  font-size: 0.75rem;
  border-radius: 999px;
}

.version-text {
  color: #999;
  font-weight: 500;
}

.main-title {
  font-size: 4rem;
  line-height: 1.2;
  font-weight: 500;
  margin: 0 0 40px 0;
  letter-spacing: -2px;
  color: var(--black);
}

.gradient-text {
  background: linear-gradient(90deg, #0f172a 0%, #0f766e 65%, #f97316 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  display: inline-block;
}

.hero-desc {
  font-size: 1.05rem;
  line-height: 1.8;
  color: var(--gray-text);
  max-width: 640px;
  margin-bottom: 50px;
}

.hero-desc p {
  margin-bottom: 1.5rem;
}

.hero-pills {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 22px;
}

.hero-pill {
  font-family: var(--font-mono);
  font-size: 11px;
  letter-spacing: 0.04em;
  color: #0f766e;
  border: 1px solid #b7d9d4;
  background: #f0fbf9;
  border-radius: 999px;
  padding: 7px 12px;
  font-weight: 700;
}

.highlight-bold {
  color: var(--black);
  font-weight: 700;
}

.highlight-orange {
  color: var(--orange);
  font-weight: 700;
  font-family: var(--font-mono);
}

.slogan-text {
  font-size: 1.1rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 0.5px;
  border-left: 3px solid #0f766e;
  padding-left: 15px;
}

.blinking-cursor {
  color: var(--orange);
  animation: blink 1s step-end infinite;
  font-weight: 700;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

.decoration-square {
  width: 16px;
  height: 16px;
  background: linear-gradient(135deg, #0f766e, var(--orange));
  border-radius: 4px;
  margin-top: 24px;
}

.hero-right {
  flex: 0.6;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
}

.hero-kpi-card {
  width: min(100%, 320px);
  border: 1px solid #d9e7f2;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.08);
  padding: 14px 16px;
}

.kpi-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px dashed #e2e8f0;
}

.kpi-row:last-child {
  border-bottom: none;
}

.kpi-label {
  font-size: 12px;
  color: #64748b;
  font-family: var(--font-mono);
}

.kpi-value {
  font-size: 13px;
  color: #0f172a;
  font-weight: 700;
  font-family: var(--font-mono);
}

.scroll-down-btn {
  width: 40px;
  height: 40px;
  border: 1px solid #ced9e5;
  background: #ffffff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #0f766e;
  font-size: 1.2rem;
  transition: all 0.2s;
  margin-top: 20px;
}

.scroll-down-btn:hover {
  border-color: #0f766e;
  background: #e7f6f4;
}

/* ── Dashboard ── */
.dashboard-section {
  display: flex;
  gap: 60px;
  align-items: stretch;
}

/* ── Left Panel ── */
.left-panel {
  flex: 0.8;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 26px;
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.06);
  position: relative;
  overflow: hidden;
}

.left-panel::before {
  content: '';
  position: absolute;
  right: -30px;
  top: -30px;
  width: 140px;
  height: 140px;
  border-radius: 28px;
  background: linear-gradient(135deg, rgba(15, 118, 110, 0.14), rgba(14, 165, 233, 0.08));
  transform: rotate(12deg);
}

.panel-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
}

.status-dot {
  color: var(--orange);
}

.section-title {
  font-size: 2rem;
  font-weight: 520;
  margin: 0 0 15px 0;
}

.section-desc {
  color: var(--gray-text);
  margin-bottom: 25px;
  line-height: 1.6;
}

.steps-container {
  border: 1px solid #e3ebf3;
  background: #fbfdff;
  border-radius: 14px;
  padding: 24px;
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.1rem;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 16px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 0.75rem;
  color: #0f766e;
  background: #f0fbf9;
  border: 1px solid #b7d9d4;
  padding: 3px 8px;
  border-radius: 6px;
  white-space: nowrap;
  margin-top: 2px;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 600;
  font-size: 0.95rem;
  margin-bottom: 3px;
}

.step-desc {
  font-size: 0.82rem;
  color: var(--gray-text);
  line-height: 1.5;
}

/* ── Right Panel ── */
.right-panel {
  flex: 1.2;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 20px;
  box-shadow: 0 16px 32px rgba(15, 23, 42, 0.06);
  position: relative;
  overflow: hidden;
}

.right-panel::before {
  content: '';
  position: absolute;
  left: -36px;
  bottom: -36px;
  width: 160px;
  height: 160px;
  border-radius: 36px;
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.1), rgba(250, 204, 21, 0.07));
  transform: rotate(-10deg);
}

.console-box {
  border: 1px solid #dce5ef;
  border-radius: 16px;
  background: #ffffff;
  padding: 8px;
}

.console-section {
  padding: 20px;
}

.console-section.btn-section {
  padding-top: 0;
}

.console-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 15px;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #666;
}

.console-label {
  color: #0f766e;
  font-weight: 700;
}

.input-wrapper {
  position: relative;
  border: 1px solid #d8e2ee;
  border-radius: 12px;
  background: #f9fcff;
}

.code-input {
  width: 100%;
  border: none;
  background: transparent;
  padding: 20px;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  line-height: 1.7;
  resize: vertical;
  outline: none;
  min-height: 220px;
  box-sizing: border-box;
  color: var(--black);
}

.code-input::placeholder {
  color: #aab4c0;
}

.model-badge {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #AAA;
}

.error-banner {
  margin: 0 20px 12px;
  padding: 12px 16px;
  background: #fff1f2;
  border: 1px solid #fecdd3;
  border-radius: 8px;
  color: #be123c;
  font-family: var(--font-mono);
  font-size: 0.82rem;
}

.start-engine-btn {
  width: 100%;
  background: linear-gradient(135deg, #0f172a 0%, #0f766e 100%);
  color: var(--white);
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
  border-radius: 10px;
}

.start-engine-btn:not(:disabled) {
  border: 1px solid #0f766e;
  animation: pulse-border 2s infinite;
}

.start-engine-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #0f766e 0%, var(--orange) 100%);
  border-color: var(--orange);
  transform: translateY(-2px);
}

.start-engine-btn:active:not(:disabled) {
  transform: translateY(0);
}

.start-engine-btn:disabled {
  background: #e5e5e5;
  color: #999;
  cursor: not-allowed;
}

.loading-text {
  display: flex;
  align-items: center;
  gap: 8px;
}

.loading-dot {
  color: #5eead4;
  animation: blink 0.8s step-end infinite;
}

.btn-arrow {
  font-size: 1.2rem;
}

@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(15, 118, 110, 0.3); }
  70% { box-shadow: 0 0 0 6px rgba(15, 118, 110, 0); }
  100% { box-shadow: 0 0 0 0 rgba(15, 118, 110, 0); }
}

/* ── Result Mode ── */
.result-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 32px 40px 70px;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.result-hero {
  background: rgba(15, 23, 42, 0.96);
  color: #f8fafc;
  border-radius: 20px;
  padding: 32px 36px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 32px;
}

.eyebrow {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  color: #5eead4;
  margin: 0 0 10px 0;
  font-weight: 700;
}

.result-title {
  font-size: 1.8rem;
  font-weight: 600;
  margin: 0 0 10px 0;
  letter-spacing: -0.5px;
}

.result-summary {
  font-size: 0.9rem;
  color: #94a3b8;
  margin: 0;
  line-height: 1.6;
  max-width: 500px;
}

.result-metrics {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.result-metric {
  background: rgba(255, 255, 255, 0.07);
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 12px;
  padding: 14px 18px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  min-width: 90px;
}

.result-metric span {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #94a3b8;
  letter-spacing: 0.08em;
}

.result-metric strong {
  font-family: var(--font-mono);
  font-size: 1.2rem;
  font-weight: 800;
  color: #f8fafc;
}

.result-metric.risk-critical strong { color: #f87171; }
.result-metric.risk-high strong { color: #fb923c; }
.result-metric.risk-medium strong { color: #fbbf24; }
.result-metric.risk-low strong { color: #34d399; }

.guardrail-strip {
  background: rgba(255, 255, 255, 0.85);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 16px 24px;
  display: flex;
  gap: 32px;
}

.guard-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.guard-item span {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: #64748b;
  letter-spacing: 0.06em;
}

.guard-item strong {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: #0f172a;
  font-weight: 700;
}

.screen-nav {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.screen-btn {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  padding: 10px 18px;
  border: 1px solid var(--border);
  background: #ffffff;
  color: #64748b;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.screen-btn:hover {
  border-color: #0f766e;
  color: #0f766e;
}

.screen-btn.active {
  background: #0f172a;
  color: #5eead4;
  border-color: #0f172a;
}

/* ── Responsive ── */
@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }

  .hero-section {
    flex-direction: column;
  }

  .hero-left {
    padding-right: 0;
    margin-bottom: 32px;
  }

  .hero-right {
    align-items: flex-start;
  }

  .result-hero {
    flex-direction: column;
  }

  .result-metrics {
    flex-wrap: wrap;
  }

  .guardrail-strip {
    flex-wrap: wrap;
    gap: 16px;
  }
}
</style>
