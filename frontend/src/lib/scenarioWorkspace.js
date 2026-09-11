const PREFIX = 'mirofish.scenario.workspace.v1'

export function workspaceKey(scenarioType, sessionId) {
  return `${PREFIX}:${scenarioType}:${sessionId || 'local'}`
}

function parseStored(raw) {
  try {
    const parsed = raw ? JSON.parse(raw) : null
    if (!parsed || typeof parsed !== 'object') return null
    return parsed
  } catch {
    return null
  }
}

function readKey(key) {
  try {
    return parseStored(sessionStorage.getItem(key) || localStorage.getItem(key))
  } catch {
    return null
  }
}

function writeKey(key, payload) {
  try {
    sessionStorage.setItem(key, payload)
    return 'session'
  } catch {
    try {
      localStorage.setItem(key, payload)
      return 'local'
    } catch {
      return ''
    }
  }
}

export function loadWorkspace(scenarioType, sessionId) {
  const exactKey = workspaceKey(scenarioType, sessionId)
  const latestKey = workspaceKey(scenarioType, 'latest')
  const localKey = workspaceKey(scenarioType, 'local')
  return readKey(exactKey) || readKey(latestKey) || readKey(localKey)
}

export function saveWorkspace(scenarioType, sessionId, { form, data } = {}) {
  const prev = readKey(workspaceKey(scenarioType, sessionId)) || readKey(workspaceKey(scenarioType, 'latest')) || {}
  const nextData = data != null ? compactAnalysis(data) : (prev.data || null)
  const payload = JSON.stringify({
    form: compactForm(form || prev.form),
    data: nextData,
    savedAt: Date.now(),
  })
  writeKey(workspaceKey(scenarioType, sessionId), payload)
  writeKey(workspaceKey(scenarioType, 'latest'), payload)
}

function compactForm(form) {
  if (!form || typeof form !== 'object') return {}
  const next = { ...form }
  delete next.attachments
  return next
}

function compactAnalysis(data) {
  if (!data || typeof data !== 'object') return null
  return {
    scenario: data.scenario,
    assistantMessage: data.assistantMessage,
    plainView: data.plainView,
    profile: data.profile,
    persona_state_vector: data.persona_state_vector || data.personaStateVector,
    strategies: (data.strategies || []).slice(0, 8),
    intervention_prescriptions: (data.intervention_prescriptions || []).slice(0, 8),
    anomalies: data.anomalies,
    t0_fast_response: data.t0_fast_response,
    metrics: data.metrics,
    latencyProfile: data.latencyProfile,
    counterfactual_report: data.counterfactual_report,
    fork_comparison: data.fork_comparison,
    branch_a_log: (data.branch_a_log || []).slice(0, 12),
    branch_b_log: (data.branch_b_log || []).slice(0, 12),
    agent_trace: (data.agent_trace || []).slice(0, 40),
    grounding: data.grounding,
    effectiveIntervention: data.effectiveIntervention,
    conversationState: data.conversationState,
    oasisStatus: data.oasisStatus,
    mostImportantAction: data.mostImportantAction,
  }
}
