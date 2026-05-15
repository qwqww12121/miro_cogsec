<template>
  <div class="home-container">
    <!-- 顶部导航栏 -->
    <nav class="navbar">
      <div class="nav-brand">
        <span class="brand-main">MIROFISH</span>
        <span class="brand-sub">COGSEC WORKSPACE</span>
      </div>
      <div class="nav-links">
        <a href="https://github.com/666ghj/MiroFish" target="_blank" class="github-link">
          访问我们的Github主页 <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <div class="main-content">
      <!-- 上半部分：Hero 区域 -->
      <section class="hero-section">
        <div class="hero-left">
          <div class="tag-row">
            <span class="orange-tag">认知安全风险推演</span>
            <span class="version-text">/ CogSec-MiroFish v3.0</span>
          </div>
          
          <h1 class="main-title">
            上传现实线索<br>
            <span class="gradient-text">先预演，再决策</span>
          </h1>
          
          <div class="hero-desc">
            <p>
              即使只有一段文字，<span class="highlight-bold">MiroFish</span> 也能基于其中的现实种子，全自动生成与之对应的至多<span class="highlight-orange">百万级Agent</span>构成的平行世界。通过上帝视角注入变量，在复杂的群体交互中寻找动态环境下的<span class="highlight-code">“局部最优解”</span>
            </p>
            <p class="slogan-text">
              让未来在 Agent 群中预演，让决策在百战后胜出<span class="blinking-cursor">_</span>
            </p>
          </div>

          <div class="hero-pills">
            <span class="hero-pill">T0 FastResponder</span>
            <span class="hero-pill">Privacy Sanitizer</span>
            <span class="hero-pill">ThreatKnowledgeRAG</span>
          </div>
           
          <div class="decoration-square"></div>
        </div>
        
        <div class="hero-right">
          <!-- Logo 区域 -->
          <div class="logo-container">
            <img src="../assets/logo/MiroFish_logo_left.jpeg" alt="MiroFish Logo" class="hero-logo" />
          </div>

          <div class="hero-kpi-card">
            <div class="kpi-row">
              <span class="kpi-label">LLM Runtime</span>
              <span class="kpi-value">Local Gemma</span>
            </div>
            <div class="kpi-row">
              <span class="kpi-label">Security Modules</span>
              <span class="kpi-value">6 Active</span>
            </div>
            <div class="kpi-row">
              <span class="kpi-label">Target Latency</span>
              <span class="kpi-value">&lt;500ms (T0)</span>
            </div>
          </div>
          
          <button class="scroll-down-btn" @click="scrollToBottom">
            ↓
          </button>
        </div>
      </section>

      <!-- 下半部分：双栏布局 -->
      <section class="dashboard-section">
        <!-- 左栏：状态与步骤 -->
        <div class="left-panel">
          <div class="panel-header">
            <span class="status-dot">■</span> 系统状态
          </div>
          
          <h2 class="section-title">准备就绪</h2>
          <p class="section-desc">
            预测引擎待命中，可上传多份非结构化数据以初始化模拟序列
          </p>
          
          <!-- 数据指标卡片 -->
          <div class="metrics-row">
            <div class="metric-card">
              <div class="metric-value">低成本</div>
              <div class="metric-label">常规模拟平均5$/次</div>
            </div>
            <div class="metric-card">
              <div class="metric-value">高可用</div>
              <div class="metric-label">最多百万级Agent模拟</div>
            </div>
          </div>

          <!-- 项目模拟步骤介绍 (新增区域) -->
          <div class="steps-container">
            <div class="steps-header">
               <span class="diamond-icon">◇</span> 工作流序列
            </div>
            <div class="workflow-list">
              <div class="workflow-item">
                <span class="step-num">01</span>
                <div class="step-info">
                  <div class="step-title">图谱构建</div>
                  <div class="step-desc">现实种子提取 & 个体与群体记忆注入 & GraphRAG构建</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">02</span>
                <div class="step-info">
                  <div class="step-title">环境搭建</div>
                  <div class="step-desc">实体关系抽取 & 人设生成 & 环境配置Agent注入仿真参数</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">03</span>
                <div class="step-info">
                  <div class="step-title">开始模拟</div>
                  <div class="step-desc">双平台并行模拟 & 自动解析预测需求 & 动态更新时序记忆</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">04</span>
                <div class="step-info">
                  <div class="step-title">报告生成</div>
                  <div class="step-desc">ReportAgent拥有丰富的工具集与模拟后环境进行深度交互</div>
                </div>
              </div>
              <div class="workflow-item">
                <span class="step-num">05</span>
                <div class="step-info">
                  <div class="step-title">深度互动</div>
                  <div class="step-desc">与模拟世界中的任意一位进行对话 & 与ReportAgent进行对话</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右栏：交互控制台 -->
        <div class="right-panel">
          <div class="console-box">
            <!-- 上传区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">01 / 现实种子</span>
                <span class="console-meta">支持格式: PDF, MD, TXT</span>
              </div>
              
              <div 
                class="upload-zone"
                :class="{ 'drag-over': isDragOver, 'has-files': files.length > 0 }"
                @dragover.prevent="handleDragOver"
                @dragleave.prevent="handleDragLeave"
                @drop.prevent="handleDrop"
                @click="triggerFileInput"
              >
                <input
                  ref="fileInput"
                  type="file"
                  multiple
                  accept=".pdf,.md,.txt"
                  @change="handleFileSelect"
                  style="display: none"
                  :disabled="loading"
                />
                
                <div v-if="files.length === 0" class="upload-placeholder">
                  <div class="upload-icon">↑</div>
                  <div class="upload-title">拖拽文件上传</div>
                  <div class="upload-hint">或点击浏览文件系统</div>
                </div>
                
                <div v-else class="file-list">
                  <div v-for="(file, index) in files" :key="index" class="file-item">
                    <span class="file-icon">📄</span>
                    <span class="file-name">{{ file.name }}</span>
                    <button @click.stop="removeFile(index)" class="remove-btn">×</button>
                  </div>
                </div>
              </div>
            </div>

            <!-- 分割线 -->
            <div class="console-divider">
              <span>输入参数</span>
            </div>

            <!-- 输入区域 -->
            <div class="console-section">
              <div class="console-header">
                <span class="console-label">>_ 02 / 模拟提示词</span>
              </div>
              <div class="input-wrapper">
                <textarea
                  v-model="formData.simulationRequirement"
                  class="code-input"
                  placeholder="// 用自然语言输入模拟或预测需求（例.武大若发布撤销肖某处分的公告，会引发什么舆情走向）"
                  rows="6"
                  :disabled="loading"
                ></textarea>
                <div class="model-badge">引擎: MiroFish-V1.0</div>
              </div>
            </div>

            <!-- 启动按钮 -->
            <div class="console-section btn-section">
              <button 
                class="start-engine-btn"
                @click="startSimulation"
                :disabled="!canSubmit || loading"
              >
                <span v-if="!loading">启动引擎</span>
                <span v-else>初始化中...</span>
                <span class="btn-arrow">→</span>
              </button>
            </div>
          </div>
        </div>
      </section>

      <!-- 历史项目数据库 -->
      <HistoryDatabase />
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import HistoryDatabase from '../components/HistoryDatabase.vue'

const router = useRouter()

// 表单数据
const formData = ref({
  simulationRequirement: ''
})

// 文件列表
const files = ref([])

// 状态
const loading = ref(false)
const error = ref('')
const isDragOver = ref(false)

// 文件输入引用
const fileInput = ref(null)

// 计算属性:是否可以提交
const canSubmit = computed(() => {
  return formData.value.simulationRequirement.trim() !== '' && files.value.length > 0
})

// 触发文件选择
const triggerFileInput = () => {
  if (!loading.value) {
    fileInput.value?.click()
  }
}

// 处理文件选择
const handleFileSelect = (event) => {
  const selectedFiles = Array.from(event.target.files)
  addFiles(selectedFiles)
}

// 处理拖拽相关
const handleDragOver = (e) => {
  if (!loading.value) {
    isDragOver.value = true
  }
}

const handleDragLeave = (e) => {
  isDragOver.value = false
}

const handleDrop = (e) => {
  isDragOver.value = false
  if (loading.value) return
  
  const droppedFiles = Array.from(e.dataTransfer.files)
  addFiles(droppedFiles)
}

// 添加文件
const addFiles = (newFiles) => {
  const validFiles = newFiles.filter(file => {
    const ext = file.name.split('.').pop().toLowerCase()
    return ['pdf', 'md', 'txt'].includes(ext)
  })
  files.value.push(...validFiles)
}

// 移除文件
const removeFile = (index) => {
  files.value.splice(index, 1)
}

// 滚动到底部
const scrollToBottom = () => {
  window.scrollTo({
    top: document.body.scrollHeight,
    behavior: 'smooth'
  })
}

// 开始模拟 - 立即跳转，API调用在Process页面进行
const startSimulation = () => {
  if (!canSubmit.value || loading.value) return
  
  // 存储待上传的数据
  import('../store/pendingUpload.js').then(({ setPendingUpload }) => {
    setPendingUpload(files.value, formData.value.simulationRequirement)
    
    // 立即跳转到Process页面（使用特殊标识表示新建项目）
    router.push({
      name: 'Process',
      params: { projectId: 'new' }
    })
  })
}
</script>

<style scoped>
/* 页面局部变量 */
:root {
  --black: #0f172a;
  --white: #ffffff;
  --orange: #f97316;
  --gray-light: #f4f7fb;
  --gray-text: #475467;
  --border: #dce3ec;
  --font-mono: 'JetBrains Mono', monospace;
  --font-sans: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  --font-cn: 'Noto Sans SC', system-ui, sans-serif;
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

/* 顶部导航 */
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
  letter-spacing: 1px;
  font-size: 1.2rem;
}

.brand-sub {
  margin-top: 3px;
  font-family: var(--font-mono);
  font-size: 10px;
  letter-spacing: 0.12em;
  color: #cbd5e1;
  font-weight: 600;
}

.nav-links {
  display: flex;
  align-items: center;
}

.github-link {
  color: var(--white);
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 8px;
  transition: opacity 0.2s;
}

.github-link:hover {
  opacity: 1;
  color: #fdba74;
}

.arrow {
  font-family: sans-serif;
}

/* 主要内容区 */
.main-content {
  max-width: 1400px;
  margin: 0 auto;
  padding: 52px 40px 70px;
}

/* Hero 区域 */
.hero-section {
  display: flex;
  justify-content: space-between;
  margin-bottom: 48px;
  position: relative;
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
  letter-spacing: 0.5px;
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
  font-weight: 400;
  text-align: left;
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

.highlight-code {
  background: rgba(15, 118, 110, 0.08);
  padding: 2px 6px;
  border-radius: 2px;
  font-family: var(--font-mono);
  font-size: 0.9em;
  color: var(--black);
  font-weight: 600;
}

.slogan-text {
  font-size: 1.2rem;
  font-weight: 520;
  color: var(--black);
  letter-spacing: 1px;
  border-left: 3px solid #0f766e;
  padding-left: 15px;
  margin-top: 20px;
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
}

.hero-right {
  flex: 0.8;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  align-items: flex-end;
}

.logo-container {
  width: 100%;
  display: flex;
  justify-content: flex-end;
  padding-right: 40px;
}

.hero-logo {
  max-width: 500px; /* 调整logo大小 */
  width: 100%;
  border-radius: 20px;
  box-shadow: 0 20px 40px rgba(15, 23, 42, 0.14);
}

.hero-kpi-card {
  width: min(100%, 360px);
  border: 1px solid #d9e7f2;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.9);
  box-shadow: 0 14px 26px rgba(15, 23, 42, 0.08);
  padding: 14px 16px;
  margin: 20px 0;
}

.kpi-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
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
}

.scroll-down-btn:hover {
  border-color: #0f766e;
  background: #e7f6f4;
}

/* Dashboard 双栏布局 */
.dashboard-section {
  display: flex;
  gap: 60px;
  border-top: 1px solid transparent;
  padding-top: 0;
  align-items: flex-start;
  margin-top: 18px;
}

.dashboard-section .left-panel,
.dashboard-section .right-panel {
  display: flex;
  flex-direction: column;
}

/* 左侧面板 */
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
  font-size: 0.8rem;
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

.metrics-row {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
}

.metric-card {
  border: 1px solid var(--border);
  background: #ffffff;
  border-radius: 14px;
  padding: 20px 30px;
  min-width: 150px;
}

.metric-value {
  font-family: var(--font-mono);
  font-size: 1.8rem;
  font-weight: 520;
  margin-bottom: 5px;
}

.metric-label {
  font-size: 0.85rem;
  color: #999;
}

/* 项目模拟步骤介绍 */
.steps-container {
  border: 1px solid #e3ebf3;
  background: #fbfdff;
  border-radius: 14px;
  padding: 30px;
  position: relative;
}

.steps-header {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  color: #999;
  margin-bottom: 25px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.diamond-icon {
  font-size: 1.2rem;
  line-height: 1;
}

.workflow-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.workflow-item {
  display: flex;
  align-items: flex-start;
  gap: 20px;
}

.step-num {
  font-family: var(--font-mono);
  font-weight: 700;
  color: var(--black);
  opacity: 0.3;
}

.step-info {
  flex: 1;
}

.step-title {
  font-weight: 520;
  font-size: 1rem;
  margin-bottom: 4px;
}

.step-desc {
  font-size: 0.85rem;
  color: var(--gray-text);
}

/* 右侧交互控制台 */
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
  background: linear-gradient(135deg, rgba(249, 115, 22, 0.12), rgba(250, 204, 21, 0.08));
  transform: rotate(-10deg);
}

.console-box {
  border: 1px solid #dce5ef; /* 外部实线 */
  border-radius: 16px;
  background: #ffffff;
  padding: 8px; /* 内边距形成双重边框感 */
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

.upload-zone {
  border: 1px dashed #c3d2e4;
  height: 200px;
  overflow-y: auto;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #f7fafd;
}

.upload-zone.has-files {
  align-items: flex-start;
}

.upload-zone:hover {
  background: #eef5fb;
  border-color: #90a9c6;
}

.upload-placeholder {
  text-align: center;
}

.upload-icon {
  width: 40px;
  height: 40px;
  border: 1px solid #DDD;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 15px;
  color: #999;
}

.upload-title {
  font-weight: 500;
  font-size: 0.9rem;
  margin-bottom: 5px;
}

.upload-hint {
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: #999;
}

.file-list {
  width: 100%;
  padding: 15px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.file-item {
  display: flex;
  align-items: center;
  background: var(--white);
  padding: 8px 12px;
  border: 1px solid #EEE;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

.file-name {
  flex: 1;
  margin: 0 10px;
}

.remove-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
  color: #999;
}

.console-divider {
  display: flex;
  align-items: center;
  margin: 10px 0;
}

.console-divider::before,
.console-divider::after {
  content: '';
  flex: 1;
  height: 1px;
  background: #EEE;
}

.console-divider span {
  padding: 0 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #BBB;
  letter-spacing: 1px;
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
  line-height: 1.6;
  resize: vertical;
  outline: none;
  min-height: 150px;
}

.model-badge {
  position: absolute;
  bottom: 10px;
  right: 15px;
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #AAA;
}

.start-engine-btn {
  width: 100%;
  background: linear-gradient(135deg, #0f172a 0%, #0f766e 100%);
  color: var(--white);
  border: none;
  padding: 20px;
  font-family: var(--font-mono);
  font-weight: 700;
  font-size: 1.1rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  cursor: pointer;
  transition: all 0.3s ease;
  letter-spacing: 1px;
  position: relative;
  overflow: hidden;
}

/* 可点击状态（非禁用） */
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
  background: #E5E5E5;
  color: #999;
  cursor: not-allowed;
  transform: none;
  border: 1px solid #E5E5E5;
}

/* 引导动画：微妙的边框脉冲 */
@keyframes pulse-border {
  0% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0.2); }
  70% { box-shadow: 0 0 0 6px rgba(0, 0, 0, 0); }
  100% { box-shadow: 0 0 0 0 rgba(0, 0, 0, 0); }
}

/* 响应式适配 */
@media (max-width: 1024px) {
  .dashboard-section {
    flex-direction: column;
  }
  
  .hero-section {
    flex-direction: column;
  }
  
  .hero-left {
    padding-right: 0;
    margin-bottom: 40px;
  }

  .hero-kpi-card {
    margin-top: 6px;
    width: 100%;
  }
  
  .hero-logo {
    max-width: 200px;
    margin-bottom: 20px;
  }
}
</style>
