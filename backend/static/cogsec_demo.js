(function () {
  const FEATURE_GROUPS = {
    情境状态: ['time_pressure', 'financial_pressure', 'info_asymmetry', 'emotional_volatility', 'cognitive_load', 'authority_intensity'],
    脆弱偏好: ['authority_compliance', 'social_proof_sensitivity', 'scarcity_sensitivity', 'loss_aversion_threshold', 'gambler_fallacy', 'trust_threshold'],
    保护习惯: ['decision_delay', 'verification_habit', 'help_seeking', 'link_check_ability', 'transaction_review', 'prior_experience']
  }

  const FEATURE_LABELS = {
    time_pressure: '时间压力',
    financial_pressure: '资金压力',
    info_asymmetry: '信息不对称',
    emotional_volatility: '情绪波动',
    cognitive_load: '认知负荷',
    authority_intensity: '权威强度',
    authority_compliance: '权威服从',
    social_proof_sensitivity: '从众敏感',
    scarcity_sensitivity: '稀缺敏感',
    loss_aversion_threshold: '损失厌恶',
    gambler_fallacy: '赌徒谬误',
    trust_threshold: '默认信任',
    decision_delay: '延迟决策',
    verification_habit: '二次核验',
    help_seeking: '求助倾向',
    link_check_ability: '链接核验',
    transaction_review: '交易复核',
    prior_experience: '先验经验'
  }

  const scenarioInput = document.getElementById('scenario-input')
  const scenarioType = document.getElementById('scenario-type')
  const analyzeBtn = document.getElementById('analyze-btn')
  const fillSampleBtn = document.getElementById('fill-sample-btn')
  const statusBox = document.getElementById('status-box')
  const resultShell = document.getElementById('result-shell')
  const metricsGrid = document.getElementById('metrics-grid')
  const profileGroups = document.getElementById('profile-groups')
  const scoreSummary = document.getElementById('score-summary')
  const trendChart = document.getElementById('trend-chart')
  const timelineGrid = document.getElementById('timeline-grid')
  const graphStage = document.getElementById('graph-stage')
  const recommendList = document.getElementById('recommend-list')
  const rawJson = document.getElementById('raw-json')

  const defaultScenario = window.__COGSEC_DEFAULT_SCENARIO__ || ''
  const staticMode = Boolean(window.__COGSEC_STATIC_MODE__)
  const staticAnalysis = window.__COGSEC_STATIC_ANALYSIS__ || null
  let currentAnalysis = null

  function setStatus(text, type) {
    statusBox.textContent = text
    statusBox.className = `status-box ${type}`
  }

  function number(value, digits = 1) {
    return Number(value || 0).toFixed(digits)
  }

  function escapeHtml(value) {
    return String(value ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;')
  }

  function renderMetrics(analysis) {
    const report = analysis.counterfactual_report || {}
    const profile = analysis.profile || {}
    let modeSub = '标准路径'
    if (analysis.meta?.mode === 'minimal_demo') {
      modeSub = '最小 Flask Demo 路径'
    } else if (analysis.meta?.mode === 'static_demo') {
      modeSub = '纯静态前端示例'
    }
    const metrics = [
      {
        label: '诈骗类别',
        value: profile.scenario_type || '未知',
        sub: modeSub
      },
      {
        label: '综合脆弱度',
        value: number(profile.overall_vulnerability_score),
        sub: `保护均值 ${number(profile.protection_score)} / 10`
      },
      {
        label: '风险等级',
        value: report.risk_level || 'LOW',
        sub: report.critical_bifurcation_reason || '暂无关键分叉说明'
      },
      {
        label: '案例条数',
        value: String(analysis.meta?.loaded_case_count || 0),
        sub: (analysis.strategies || []).map(item => item.tactic_name).join(' / ')
      }
    ]

    metricsGrid.innerHTML = metrics.map(item => `
      <article class="metric-card">
        <div class="label">${escapeHtml(item.label)}</div>
        <div class="value">${escapeHtml(item.value)}</div>
        <div class="sub">${escapeHtml(item.sub)}</div>
      </article>
    `).join('')
  }

  function renderProfile(profile) {
    profileGroups.innerHTML = Object.entries(FEATURE_GROUPS).map(([groupName, keys]) => {
      const rows = keys.map(key => {
        const value = Number(profile[key] || 0)
        const reason = profile.reasoning?.[key] || ''
        const protection = groupName === '保护习惯'
        return `
          <div class="feature-row ${protection ? 'protection' : ''}">
            <div class="feature-head">
              <span>${escapeHtml(FEATURE_LABELS[key] || key)}</span>
              <span>${number(value)}</span>
            </div>
            <div class="feature-bar"><span style="width:${Math.max(0, Math.min(100, value * 10))}%"></span></div>
            <div class="step-meta">${escapeHtml(reason || '未给出明确依据')}</div>
          </div>
        `
      }).join('')

      return `
        <section class="feature-group">
          <h3>${escapeHtml(groupName)}</h3>
          ${rows}
        </section>
      `
    }).join('')
  }

  function renderScores(scoreComparison) {
    const finalA = scoreComparison?.branch_a_final || {}
    const finalB = scoreComparison?.branch_b_final || {}
    const keys = ['CHS', 'ASS', 'SSS', 'EES']

    scoreSummary.innerHTML = keys.map(key => `
      <div class="score-row">
        <strong>${escapeHtml(key)}</strong>
        <div class="score-bars">
          <div class="score-bar danger"><span style="width:${Math.max(0, Math.min(100, Number(finalA[key] || 0)))}%"></span></div>
          <div class="score-bar safe"><span style="width:${Math.max(0, Math.min(100, Number(finalB[key] || 0)))}%"></span></div>
        </div>
        <span>A ${number(finalA[key])} / B ${number(finalB[key])}</span>
      </div>
    `).join('')
  }

  function polyline(points, color, dash) {
    return `<polyline fill="none" stroke="${color}" stroke-width="3" ${dash ? 'stroke-dasharray="7 5"' : ''} points="${points.map(p => `${p.x},${p.y}`).join(' ')}"></polyline>`
  }

  function pointLabel(point, color) {
    return `
      <circle cx="${point.x}" cy="${point.y}" r="4.5" fill="${color}"></circle>
      <text x="${point.x}" y="${point.y - 10}" text-anchor="middle" font-size="11" fill="${color}">${escapeHtml(point.value)}</text>
    `
  }

  function buildPoints(series, key, width, height, left, top) {
    const maxX = Math.max(1, series.length - 1)
    return series.map((item, index) => ({
      x: left + (width * index / maxX),
      y: top + height - (Math.max(0, Math.min(100, Number(item[key] || 0))) / 100) * height,
      value: number(item[key])
    }))
  }

  function renderTrend(scoreComparison) {
    const timelineA = scoreComparison?.timeline_a || []
    const timelineB = scoreComparison?.timeline_b || []
    const width = 760
    const height = 280
    const left = 54
    const top = 20
    const chartWidth = width - 88
    const chartHeight = height - 60

    const gridLines = [0, 25, 50, 75, 100].map(value => {
      const y = top + chartHeight - (value / 100) * chartHeight
      return `
        <line x1="${left}" y1="${y}" x2="${left + chartWidth}" y2="${y}" stroke="#d9e2e7" stroke-width="1"></line>
        <text x="${left - 12}" y="${y + 4}" text-anchor="end" font-size="11" fill="#6b7280">${value}</text>
      `
    }).join('')

    const xLabels = timelineA.map((item, index) => {
      const x = left + (chartWidth * index / Math.max(1, timelineA.length - 1))
      return `<text x="${x}" y="${height - 10}" text-anchor="middle" font-size="11" fill="#6b7280">t${item.t}</text>`
    }).join('')

    const aAss = buildPoints(timelineA, 'ASS', chartWidth, chartHeight, left, top)
    const aChs = buildPoints(timelineA, 'CHS', chartWidth, chartHeight, left, top)
    const bAss = buildPoints(timelineB, 'ASS', chartWidth, chartHeight, left, top)
    const bChs = buildPoints(timelineB, 'CHS', chartWidth, chartHeight, left, top)

    trendChart.innerHTML = `
      <rect x="0" y="0" width="${width}" height="${height}" rx="20" fill="transparent"></rect>
      ${gridLines}
      ${polyline(aAss, '#d92d20', false)}
      ${polyline(aChs, '#ef7d32', true)}
      ${polyline(bAss, '#0f766e', false)}
      ${polyline(bChs, '#2563eb', true)}
      ${aAss.map(p => pointLabel(p, '#d92d20')).join('')}
      ${bAss.map(p => pointLabel(p, '#0f766e')).join('')}
      ${xLabels}
      <g>
        <rect x="${left}" y="8" width="14" height="4" rx="2" fill="#d92d20"></rect>
        <text x="${left + 20}" y="12" font-size="11" fill="#374151">A-ASS</text>
        <rect x="${left + 86}" y="8" width="14" height="4" rx="2" fill="#ef7d32"></rect>
        <text x="${left + 106}" y="12" font-size="11" fill="#374151">A-CHS</text>
        <rect x="${left + 172}" y="8" width="14" height="4" rx="2" fill="#0f766e"></rect>
        <text x="${left + 192}" y="12" font-size="11" fill="#374151">B-ASS</text>
        <rect x="${left + 258}" y="8" width="14" height="4" rx="2" fill="#2563eb"></rect>
        <text x="${left + 278}" y="12" font-size="11" fill="#374151">B-CHS</text>
      </g>
    `
  }

  function renderTimeline(branchA, branchB, report) {
    const criticalStep = Number(report?.critical_bifurcation_step || -1)

    function renderColumn(title, cls, branch, finalSummary) {
      return `
        <div class="timeline-column ${cls}">
          <h3>${escapeHtml(title)}</h3>
          <p class="step-text">${escapeHtml(finalSummary)}</p>
          ${branch.map(item => `
            <article class="step-card ${Number(item.step) === criticalStep ? 'critical' : ''}">
              <div class="step-index">${escapeHtml(item.step)}</div>
              <h4 class="step-title">${escapeHtml(item.agent_action)}</h4>
              <p class="step-text">${escapeHtml(item.victim_response)}</p>
              <p class="step-meta">原则：${escapeHtml((item.triggered_principles || []).join(' / '))}</p>
              <p class="step-meta">分数变化：CHS ${number(item.score_delta?.CHS, 2)}，ASS ${number(item.score_delta?.ASS, 2)}，EES ${number(item.score_delta?.EES, 2)}</p>
            </article>
          `).join('')}
        </div>
      `
    }

    timelineGrid.innerHTML = [
      renderColumn('危险分支 A', 'danger', branchA, report?.summary_branch_a || ''),
      renderColumn('防御分支 B', 'safe', branchB, report?.summary_branch_b || '')
    ].join('')
  }

  function computeGraphLayout(graph) {
    const width = graphStage.clientWidth || 720
    const height = graphStage.clientHeight || 560
    const positions = {}
    const nodes = graph.nodes || []

    const scenario = nodes.find(n => n.category === 'scenario')
    if (scenario) {
      positions[scenario.id] = { x: width * 0.5, y: 84 }
    }

    const buckets = {
      state: nodes.filter(n => n.category === 'state'),
      vulnerability: nodes.filter(n => n.category === 'vulnerability'),
      protection: nodes.filter(n => n.category === 'protection'),
      strategy: nodes.filter(n => n.category === 'strategy')
    }

    function place(list, x, top, gap) {
      list.forEach((node, index) => {
        positions[node.id] = { x, y: top + index * gap }
      })
    }

    place(buckets.state, width * 0.22, 170, 82)
    place(buckets.vulnerability, width * 0.78, 170, 82)
    place(buckets.protection, width * 0.24, 420, 72)
    place(buckets.strategy, width * 0.76, 420, 72)

    return positions
  }

  function categoryName(raw) {
    const mapping = {
      scenario: '情景',
      state: '状态',
      vulnerability: '脆弱',
      protection: '保护',
      strategy: '策略'
    }
    return mapping[raw] || raw
  }

  function renderGraph(graph) {
    const positions = computeGraphLayout(graph)
    const links = graph.links || []
    const nodes = graph.nodes || []

    const svg = `
      <svg class="graph-svg" viewBox="0 0 ${graphStage.clientWidth || 720} ${graphStage.clientHeight || 560}" preserveAspectRatio="none">
        ${links.map(link => {
          const s = positions[link.source]
          const t = positions[link.target]
          if (!s || !t) return ''
          return `
            <line x1="${s.x}" y1="${s.y}" x2="${t.x}" y2="${t.y}" stroke="#c6d2d7" stroke-width="2"></line>
            <text x="${(s.x + t.x) / 2}" y="${(s.y + t.y) / 2 - 6}" text-anchor="middle" font-size="11" fill="#64748b">${escapeHtml(link.label || '')}</text>
          `
        }).join('')}
      </svg>
    `

    const nodeCards = nodes.map(node => {
      const pos = positions[node.id]
      if (!pos) return ''
      return `
        <article class="graph-node ${escapeHtml(node.category)}" style="left:${pos.x}px; top:${pos.y}px;">
          <span class="node-name">${escapeHtml(node.name)}</span>
          <span class="node-meta">${escapeHtml(categoryName(node.category))} · 风险 ${number(node.risk || 0)}</span>
        </article>
      `
    }).join('')

    graphStage.innerHTML = svg + nodeCards
  }

  function renderRecommendations(report) {
    const items = report?.recommendations || []
    recommendList.innerHTML = items.map(item => `
      <article class="recommend-card">
        <span class="priority">P${escapeHtml(item.priority)}</span>
        <h3>${escapeHtml(item.action)}</h3>
        <p>${escapeHtml(item.reason)}</p>
      </article>
    `).join('')
  }

  function renderAnalysis(analysis) {
    currentAnalysis = analysis
    resultShell.classList.remove('hidden')
    renderMetrics(analysis)
    renderProfile(analysis.profile || {})
    renderScores(analysis.counterfactual_report?.score_comparison)
    renderTrend(analysis.counterfactual_report?.score_comparison)
    renderTimeline(analysis.branch_a_log || [], analysis.branch_b_log || [], analysis.counterfactual_report || {})
    renderGraph(analysis.graph || { nodes: [], links: [] })
    renderRecommendations(analysis.counterfactual_report || {})
    rawJson.textContent = JSON.stringify(analysis, null, 2)
  }

  async function analyze() {
    const scenario = (scenarioInput.value || '').trim()
    if (!scenario) {
      setStatus('请输入要分析的场景文本', 'error')
      return
    }

    if (staticMode && staticAnalysis) {
      renderAnalysis(staticAnalysis)
      setStatus('静态前端示例已加载，当前未调用后端接口', 'success')
      return
    }

    setStatus('正在调用 Flask API 并生成可视化...', 'loading')

    try {
      const response = await fetch('/api/cogsec/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          scenario,
          scenario_type: scenarioType.value || null
        })
      })
      const payload = await response.json()
      if (!response.ok || !payload.success) {
        throw new Error(payload.error || '分析失败')
      }
      renderAnalysis(payload.data)
      setStatus('分析完成，页面已更新为最新可视化结果', 'success')
    } catch (error) {
      console.error(error)
      setStatus(error.message || '分析失败', 'error')
    }
  }

  fillSampleBtn.addEventListener('click', function () {
    scenarioInput.value = defaultScenario
    scenarioType.value = ''
  })

  analyzeBtn.addEventListener('click', analyze)

  window.addEventListener('resize', function () {
    if (currentAnalysis) {
      renderTrend(currentAnalysis.counterfactual_report?.score_comparison)
      renderGraph(currentAnalysis.graph || { nodes: [], links: [] })
    }
  })

  scenarioInput.value = scenarioInput.value || defaultScenario
  if (staticMode && staticAnalysis) {
    renderAnalysis(staticAnalysis)
    setStatus('静态前端示例已加载，当前未调用后端接口', 'success')
  } else {
    analyze()
  }
})()
