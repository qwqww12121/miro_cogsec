import { avatarKeyForSession, pickAvatarKey } from './miroAvatar'

const STORAGE_KEY = 'mirofish.cogsec.chat.sessions.v1'
const MEMORY_KEY = 'mirofish.cogsec.chat.sessions.memory.v1'

function uid() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`
}

function readStore(store) {
  try {
    const raw = store.getItem(STORAGE_KEY) || store.getItem(MEMORY_KEY)
    const parsed = raw ? JSON.parse(raw) : []
    return Array.isArray(parsed) ? parsed : []
  } catch {
    return []
  }
}

function compactMessages(messages) {
  return (messages || []).map((message) => {
    if (!message || message.role !== 'assistant') return message
    return {
      ...message,
      thinking: (message.thinking || []).map((step) => ({
        id: step.id,
        title: step.title,
        summary: step.summary,
        details: (step.details || []).slice(0, 8),
        graph: step.graph
          ? { nodes: (step.graph.nodes || []).slice(0, 8), edges: (step.graph.edges || []).slice(0, 10) }
          : undefined,
      })),
      result: compactResult(message.result),
    }
  })
}

function compactResult(result) {
  if (!result || typeof result !== 'object') return result
  return {
    scenario_type: result.scenario_type,
    recognition_status: result.recognition_status,
    recognition_mode: result.recognition_mode,
    confidence: result.confidence,
    reason: result.reason,
    extracted_summary: result.extracted_summary,
    extracted_fields: result.extracted_fields,
    chat_reply: result.chat_reply,
    attribution: result.attribution,
    thinking: result.thinking,
    agent_trace: (result.agent_trace || []).slice(0, 40),
    fork_status: result.fork_status,
    graph_payload: result.graph_payload,
  }
}

function writeSessions(sessions) {
  const payload = JSON.stringify(sessions.slice(0, 20).map((session) => ({
    ...session,
    messages: compactMessages(session.messages),
  })))
  try {
    localStorage.setItem(STORAGE_KEY, payload)
  } catch {
    try {
      sessionStorage.setItem(MEMORY_KEY, payload)
    } catch {
      // quota exhausted; in-memory React state still holds the current turn
    }
  }
}

function readSessions() {
  const fromLocal = readStore(localStorage)
  if (fromLocal.length) return fromLocal
  return readStore(sessionStorage)
}

export function createSession() {
  const session = {
    id: uid(),
    title: '新对话',
    updatedAt: Date.now(),
    messages: [],
    avatarKey: pickAvatarKey(),
  }
  writeSessions([session, ...readSessions()])
  return session
}

export function listSessions() {
  return readSessions().sort((a, b) => b.updatedAt - a.updatedAt)
}

export function getSession(id) {
  return readSessions().find((item) => item.id === id) || null
}

export function saveSession(session) {
  const titleFromUser = session.messages.find((item) => item.role === 'user')?.content || '新对话'
  const next = {
    ...session,
    avatarKey: session.avatarKey === 'male' || session.avatarKey === 'female' ? session.avatarKey : avatarKeyForSession(session),
    title: String(titleFromUser).replace(/\s+/g, ' ').slice(0, 22) || '新对话',
    updatedAt: Date.now(),
  }
  const others = readSessions().filter((item) => item.id !== next.id)
  writeSessions([next, ...others])
  return next
}

export function deleteSession(id) {
  writeSessions(readSessions().filter((item) => item.id !== id))
}
