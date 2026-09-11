const PENDING_KEY = 'mirofish.cogsec.chat.pending.v1'
const TEXT_FILE = /\.(md|markdown|txt|csv|json)$/i
const RESUME = /^(继续|接着|请继续|重试|再试一次|继续分析)([。.!！？?\s]*)$/

export function isResumeCommand(text) {
  return RESUME.test(String(text || '').trim())
}

let memoryFiles = []

export function setMemoryFiles(files) {
  memoryFiles = Array.isArray(files) ? files.filter(Boolean) : []
  return memoryFiles
}

export function getMemoryFiles() {
  return memoryFiles
}

export async function extractMaterial(text, files = []) {
  const chunks = []
  const leftover = []
  const fileNames = []
  const trimmed = String(text || '').trim()
  if (trimmed) chunks.push(trimmed)

  for (const file of files) {
    if (!file) continue
    const name = file.name || '附件'
    fileNames.push(name)
    if (TEXT_FILE.test(name) || String(file.type || '').startsWith('text/')) {
      try {
        const content = (await file.text()).trim()
        if (content) chunks.push(`【附件：${name}】\n${content}`)
      } catch {
        leftover.push(file)
      }
    } else {
      leftover.push(file)
    }
  }

  const extractedText = chunks.join('\n\n').trim()
  return {
    displayText: trimmed || (fileNames.length ? '请分析我上传的材料。' : ''),
    extractedText,
    files: leftover,
    fileNames,
  }
}

export function savePending(payload) {
  try {
    sessionStorage.setItem(PENDING_KEY, JSON.stringify({
      sessionId: payload.sessionId || '',
      displayText: payload.displayText || '',
      extractedText: payload.extractedText || '',
      fileNames: payload.fileNames || [],
      userMessageId: payload.userMessageId || '',
      updatedAt: Date.now(),
    }))
  } catch {
    // Ignore quota errors; in-memory files still cover the current tab.
  }
}

export function readPending() {
  try {
    const parsed = JSON.parse(sessionStorage.getItem(PENDING_KEY) || 'null')
    return parsed && typeof parsed === 'object' ? parsed : null
  } catch {
    return null
  }
}

export function clearPending() {
  try {
    sessionStorage.removeItem(PENDING_KEY)
  } catch {
    // ignore
  }
  memoryFiles = []
}

export function buildScenarioPrefill(messages = []) {
  const users = (messages || []).filter((item) => item.role === 'user')
  if (!users.length) return ''
  return users.map((item, index) => {
    const text = String(item.extractedText || item.content || '').trim()
    if (!text) return ''
    if (index === 0) return text
    if (/^(受害人|攻击者|骗子|施害者|对方)[:：]/.test(text)) return text
    return `受害人：${text}`
  }).filter(Boolean).join('\n')
}

export function appendVictimTurn(baseText, turn) {
  const base = String(baseText || '').trim()
  const next = String(turn || '').trim()
  if (!next) return base
  if (base.includes(next)) return base
  if (/^(受害人|攻击者|骗子|施害者|对方)[:：]/.test(next)) {
    return [base, next].filter(Boolean).join('\n')
  }
  return [base, `受害人：${next}`].filter(Boolean).join('\n')
}

export function shouldResumeTurn(text, messages = []) {
  if (!isResumeCommand(text)) return false
  const lastUser = [...messages].reverse().find((item) => item.role === 'user')
  if (!lastUser && !readPending()) return false
  const lastAssistant = [...messages].reverse().find((item) => item.role === 'assistant')
  if (!lastAssistant) return true
  if (lastAssistant.reply?.style === 'stopped' || lastAssistant.tone === 'error') return true
  if (!lastAssistant.result) return true
  return false
}

export function resolveResumeMaterial(messages = []) {
  const pending = readPending() || {}
  const lastUser = [...messages].reverse().find((item) => item.role === 'user') || {}
  return {
    displayText: pending.displayText || lastUser.content || '',
    extractedText: pending.extractedText || lastUser.extractedText || lastUser.content || '',
    files: getMemoryFiles(),
    fileNames: pending.fileNames || lastUser.fileNames || [],
  }
}
