import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { classifyScenario } from '../api/classify'
import { SCENARIOS } from '../scenarios/config'
import MultimodalComposer from '../components/MultimodalComposer'
import Icon from '../components/Icon'
import JumpLinkCard from '../components/chat/JumpLinkCard'
import FeatureIntroCards from '../components/chat/FeatureIntroCards'
import ThoughtPath from '../components/chat/ThoughtPath'
import ExpandableFrame from '../components/ExpandableFrame'
import AgentTracePanel from '../components/chat/AgentTracePanel'
import MiroAvatar from '../components/chat/MiroAvatar'
import { avatarKeyForSession } from '../lib/miroAvatar'
import { createSession, deleteSession, getSession, listSessions, saveSession } from '../lib/chatHistory'
import { buildFollowupReply, isFollowupTurn } from '../lib/chatFollowup'
import { isInternalSkipCopy } from '../lib/hideInternalSkipCopy'
import {
  clearPending,
  extractMaterial,
  getMemoryFiles,
  savePending,
  setMemoryFiles,
  shouldResumeTurn,
  resolveResumeMaterial,
  buildScenarioPrefill,
  appendVictimTurn,
} from '../lib/chatMaterial'

const GREETING_PATTERN = /^(你好|您好|嗨|哈喽|hello|hi|在吗|你是谁|介绍一下)([\s!！,.，。？?]*)$/i

const GREETING_REPLY = {
  style: 'greeting',
  lead: '你好，我是 MiroCogSec，面向认知安全的分析系统。',
  paragraphs: [
    '我可以帮你看三类问题：即时通讯里的诈骗话术，公共舆情里的情绪与极化，以及一件事是怎么一层层传开的。',
    '你可以直接打招呼，也可以把对话、截图文字或事件描述发给我。我会先把判断讲清楚，再请你进入场景分析或对照/关系图。',
  ],
  sections: [],
  closing: '有什么我可以帮你的吗？',
  show_feature_cards: true,
  suggested_followups: ['帮我看一段可疑聊天', '这像舆情还是传播？', '先看看你的三个能力'],
}

const EXAMPLES = [
  { label: '打个招呼', text: '你好' },
  { label: '分析一段聊天', text: '骗子：我是银行客服，你的信用卡异常。\n受害人：是真的吗？\n骗子：先转到安全账户。' },
  { label: '舆情材料', text: '这条视频在多个平台被转发，评论区开始对立，有人说是谣言，有人要求官方回应。' },
]

export default function ChatPage() {
  const location = useLocation()
  const navigate = useNavigate()
  const [sessions, setSessions] = useState(() => listSessions())
  const [sessionId, setSessionId] = useState(() => sessions[0]?.id || '')
  const [messages, setMessages] = useState(() => sessions[0]?.messages || [])
  const [input, setInput] = useState('')
  const [attachments, setAttachments] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [copiedId, setCopiedId] = useState('')
  const bottomRef = useRef(null)
  const abortRef = useRef(null)
  const requestIdRef = useRef(0)
  const userStoppedRef = useRef(false)
  const initialHandledRef = useRef(false)

  const currentSession = useMemo(
    () => sessions.find((item) => item.id === sessionId) || null,
    [sessions, sessionId],
  )
  const avatarKey = avatarKeyForSession(currentSession)

  const persist = (nextMessages, id = sessionId) => {
    let activeId = id
    if (!activeId) {
      const session = createSession()
      activeId = session.id
    }
    const existing = listSessions().find((item) => item.id === activeId) || { id: activeId, title: '新对话', messages: [] }
    const saved = saveSession({ ...existing, messages: nextMessages })
    setSessions(listSessions())
    setSessionId(saved.id)
    setMessages(saved.messages)
  }

  const startNewSession = () => {
    userStoppedRef.current = false
    abortRef.current?.abort()
    clearPending()
    const session = createSession()
    setSessions(listSessions())
    setSessionId(session.id)
    setMessages([])
    setError('')
    setLoading(false)
  }

  const openSession = (id) => {
    userStoppedRef.current = false
    abortRef.current?.abort()
    const session = listSessions().find((item) => item.id === id)
    if (!session) return
    setSessionId(session.id)
    setMessages(session.messages || [])
    setError('')
    setLoading(false)
  }

  const removeSession = (id) => {
    deleteSession(id)
    const remaining = listSessions()
    setSessions(remaining)
    if (id === sessionId) {
      if (remaining[0]) openSession(remaining[0].id)
      else startNewSession()
    }
  }

  const sendMessage = async (rawText, rawFiles = [], baseMessages = null, activeSessionId = sessionId) => {
    try {
    const history = Array.isArray(baseMessages) ? baseMessages : messages
    const resume = shouldResumeTurn(rawText, history)
    const incomingFiles = Array.isArray(rawFiles) ? rawFiles : []
    const material = resume
      ? resolveResumeMaterial(history)
      : await extractMaterial(rawText, incomingFiles)

    if (!material.extractedText && !material.displayText && material.files.length === 0 && (material.fileNames || []).length === 0) {
      return
    }

    userStoppedRef.current = false
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    const requestId = ++requestIdRef.current
    const startedAt = Date.now()

    const storedText = (material.extractedText || '').slice(0, 100000)
    const userMessage = {
      id: `${Date.now()}-user`,
      role: 'user',
      content: resume ? String(rawText || '').trim() : material.displayText,
      fileNames: resume ? [] : material.fileNames,
      extractedText: storedText,
    }
    const nextMessages = [...history, userMessage]
    setMemoryFiles(material.files)
    savePending({
      sessionId: activeSessionId,
      displayText: material.displayText,
      extractedText: storedText,
      fileNames: material.fileNames,
      userMessageId: userMessage.id,
    })
    setMessages(nextMessages)
    setInput('')
    setAttachments([])
    setError('')
    setLoading(true)

    try {
      const lastAssistant = [...history].reverse().find((item) => item.role === 'assistant' && item.result)
      const rawTrim = String(rawText || '').trim()
      const followupHit = !resume && lastAssistant?.result && (isFollowupTurn(rawTrim, lastAssistant.result) || /^(继续|接着)([。.!！？?\s]*)$/.test(rawTrim))
      let assistant
      if (!resume && GREETING_PATTERN.test(rawTrim)) {
        assistant = {
          id: `${Date.now()}-assistant`,
          role: 'assistant',
          reply: GREETING_REPLY,
          featureCards: true,
          thoughtDurationMs: Date.now() - startedAt,
        }
        clearPending()
      } else if (followupHit) {
        assistant = {
          id: `${Date.now()}-assistant`,
          role: 'assistant',
          reply: buildFollowupReply(String(rawText || '').trim(), lastAssistant.result),
          result: lastAssistant.result,
          thinking: lastAssistant.thinking,
          inputText: appendVictimTurn(lastAssistant.inputText || lastAssistant.navigationState?.prefillText || material.extractedText, rawTrim),
          navigationState: {
            ...lastAssistant.navigationState,
            sessionId: activeSessionId,
            prefillText: appendVictimTurn(lastAssistant.navigationState?.prefillText || lastAssistant.inputText, rawTrim),
            autoAnalyze: true,
          },
          scenario: lastAssistant.scenario,
          thoughtDurationMs: Date.now() - startedAt,
        }
      } else {
        const result = await classifyScenario(
          (material.extractedText || material.displayText || '').slice(0, 20000),
          { attachments: getMemoryFiles(), signal: controller.signal },
        )
        if (requestId !== requestIdRef.current) return
        assistant = buildAssistantMessage(material.extractedText || material.displayText, result, activeSessionId, Date.now() - startedAt)
        clearPending()
      }
      if (requestId !== requestIdRef.current) return
      persist([...nextMessages, assistant], activeSessionId)
    } catch (err) {
      if (requestId !== requestIdRef.current) return
      const canceled = err?.name === 'CanceledError' || err?.code === 'ERR_CANCELED'
      if (canceled) {
        if (userStoppedRef.current) {
          persist([...nextMessages, {
            id: `${Date.now()}-assistant-stop`,
            role: 'assistant',
            reply: {
              style: 'stopped',
              lead: '这一轮已经停下来了。',
              paragraphs: ['输入还留着。直接说「继续」，我会按刚才那份材料接着分析，不用重新上传。'],
              sections: [],
              closing: '也可以改一句话后再发。',
            },
            thoughtDurationMs: Date.now() - startedAt,
          }], activeSessionId)
        }
        return
      }
      const message = err?.message || '暂时无法完成识别，请稍后再试。'
      setError(message)
      persist([...nextMessages, {
        id: `${Date.now()}-assistant-error`,
        role: 'assistant',
        reply: {
          style: 'error',
          lead: '我收到了你的输入，但这次没有完成分析。材料还在缓存里。',
          paragraphs: [message, '直接回复「继续」，我会用刚才那份文本或附件重试。'],
          sections: [],
          closing: '也可以换一段材料重新发给我。',
        },
        tone: 'error',
        thoughtDurationMs: Date.now() - startedAt,
      }], activeSessionId)
    } finally {
      if (requestId === requestIdRef.current) setLoading(false)
    }
    } catch (err) {
      setError(err?.message || '发送失败')
      setLoading(false)
    }
  }

  const stopThinking = () => {
    userStoppedRef.current = true
    abortRef.current?.abort()
    setLoading(false)
  }

  const editFrom = (message) => {
    const index = messages.findIndex((item) => item.id === message.id)
    if (index < 0) return
    setInput(message.content || '')
    persist(messages.slice(0, index))
  }

  const regenerateLast = () => {
    const lastUser = [...messages].reverse().find((item) => item.role === 'user')
    if (!lastUser || loading) return
    const index = messages.findIndex((item) => item.id === lastUser.id)
    sendMessage(lastUser.extractedText || lastUser.content, getMemoryFiles(), messages.slice(0, index))
  }

  const copyReply = async (message) => {
    const reply = message.reply || {}
    const text = [
      reply.lead,
      ...(reply.paragraphs || []),
      ...(reply.sections || []).flatMap((section) => [section.heading, section.body, ...(section.items || [])]),
      reply.closing,
    ].filter(Boolean).join('\n\n')
    try {
      await navigator.clipboard.writeText(text)
      setCopiedId(message.id)
      setTimeout(() => setCopiedId(''), 1200)
    } catch {
      setError('复制失败，请手动选择文字。')
    }
  }

  useEffect(() => {
    if (initialHandledRef.current) return
    initialHandledRef.current = true
    const restoreId = location.state?.sessionId
    const initialText = location.state?.initialText || ''
    const initialFiles = location.state?.initialAttachments || []
    if (restoreId) {
      const session = getSession(restoreId)
      if (session) {
        setSessionId(session.id)
        setMessages(session.messages || [])
        setSessions(listSessions())
        return
      }
    }
    if (initialText || initialFiles.length) {
      const fingerprint = `${initialText}|${initialFiles.map((file) => file?.name || '').join(',')}`
      const processed = sessionStorage.getItem('mirofish.chat.processed-initial')
      const latest = listSessions()[0]
      if (processed === fingerprint && latest?.messages?.length) {
        setSessionId(latest.id)
        setMessages(latest.messages)
        setSessions(listSessions())
        return
      }
      sessionStorage.setItem('mirofish.chat.processed-initial', fingerprint)
      const session = createSession()
      setSessions(listSessions())
      setSessionId(session.id)
      setMessages([])
      sendMessage(initialText, initialFiles, [], session.id)
      return
    }
    if (!sessionId) startNewSession()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = (text = input) => {
    if (loading) return
    sendMessage(text, attachments)
  }

  const onSubmit = (event) => {
    event.preventDefault()
    handleSend(input)
  }

  return (
    <div className="h-full min-h-0 flex bg-[#eef3f9]">
      <aside className={`${sidebarOpen ? 'w-[280px]' : 'w-0'} shrink-0 border-r border-border bg-white/90 overflow-hidden transition-all duration-200`}>
        <div className="h-full flex flex-col">
          <div className="px-3 py-3 flex items-center gap-2">
            <button type="button" className="btn-primary w-full" onClick={startNewSession}>
              <Icon name="plus" className="w-4 h-4 mr-1.5" />
              新对话
            </button>
          </div>
          <div className="px-3 text-[11px] text-ink-500 mb-1">对话历史</div>
          <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-1">
            {sessions.map((session) => (
              <div key={session.id} className={`group flex items-center rounded-xl ${session.id === sessionId ? 'bg-brand-50' : 'hover:bg-slate-50'}`}>
                <button type="button" onClick={() => openSession(session.id)} className="flex-1 text-left px-3 py-2 min-w-0">
                  <div className="text-sm text-ink-900 truncate">{session.title}</div>
                  <div className="text-[10px] text-ink-300">{new Date(session.updatedAt).toLocaleString()}</div>
                </button>
                <button type="button" className="opacity-0 group-hover:opacity-100 px-2 text-ink-300 hover:text-rose-500" onClick={() => removeSession(session.id)} aria-label="删除对话">×</button>
              </div>
            ))}
            {sessions.length === 0 && <div className="px-3 py-6 text-xs text-ink-300">还没有历史对话。</div>}
          </div>
        </div>
      </aside>

      <section className="flex-1 min-w-0 flex flex-col">
        <header className="h-14 px-4 flex items-center justify-between border-b border-border bg-white/80 backdrop-blur">
          <div className="flex items-center gap-3">
            <button type="button" className="btn-ghost px-2" onClick={() => setSidebarOpen((value) => !value)} aria-label="历史记录">≡</button>
            <MiroAvatar avatarKey={avatarKey} />
            <div>
              <div className="text-sm font-semibold text-ink-900">MiroCogSec</div>
              <div className="text-[11px] text-ink-500">{currentSession?.title || '认知安全对话'}</div>
            </div>
          </div>
          <Link to="/" className="btn-ghost text-xs">返回首页</Link>
        </header>

        <div className="flex-1 overflow-y-auto">
          <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
            {messages.length === 0 && !loading && (
              <WelcomeBlock
                avatarKey={avatarKey}
                onFeature={(feature) => navigate('/simulation-map', { state: { featureKey: feature.key, sessionId } })}
                onExample={(text) => sendMessage(text, [], messages)}
              />
            )}
            {messages.map((message, index) => (
              <ChatMessage
                key={message.id}
                message={message}
                navigate={navigate}
                sessionId={sessionId}
                avatarKey={avatarKey}
                copied={copiedId === message.id}
                onCopy={() => copyReply(message)}
                onEdit={message.role === 'user' ? () => editFrom(message) : undefined}
                onRegenerate={index === messages.length - 1 && message.role === 'assistant' ? regenerateLast : undefined}
                onSuggest={(text) => sendMessage(text)}
                conversationPrefill={buildScenarioPrefill(messages.slice(0, index + 1))}
              />
            ))}
            {loading && (
              <div className="flex gap-3">
                <MiroAvatar avatarKey={avatarKey} />
                <div className="min-w-0 flex-1">
                  <ThoughtPath running />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

        <form onSubmit={onSubmit} className="border-t border-border bg-white/90 px-4 py-3">
          <div className="max-w-3xl mx-auto">
            <MultimodalComposer
              value={input}
              onChange={(event) => setInput(event.target.value)}
              files={attachments}
              onFilesChange={setAttachments}
              onRemoveFile={(index) => setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))}
              loading={loading}
              rows={2}
              accent="brand"
              placeholder="输入你好，或粘贴一段对话、舆情、事件材料…"
              onSend={handleSend}
            />
            <div className="mt-2 flex items-center justify-between gap-3">
              <span className="text-[11px] text-ink-300">回车发送，Shift+回车换行。分析中断后回复「继续」，会按上一份材料重试。</span>
              <div className="flex items-center gap-2 shrink-0">
                {loading && (
                  <button type="button" className="btn-ghost" onClick={stopThinking}>停止</button>
                )}
                <button type="button" className="btn-primary" disabled={loading || (!input.trim() && attachments.length === 0)} onClick={() => handleSend(input)}>
                  <Icon name="spark" className="w-4 h-4 mr-1.5" />
                  发送
                </button>
              </div>
            </div>
            {error && <div className="mt-2 text-xs text-amber-700">{error}</div>}
          </div>
        </form>
      </section>
    </div>
  )
}

function WelcomeBlock({ onFeature, onExample, avatarKey }) {
  return (
    <div className="pt-8">
      <MiroAvatar avatarKey={avatarKey} size="lg" className="mb-4" />
      <h1 className="text-2xl font-semibold text-ink-900">你好，我是 MiroCogSec</h1>
      <p className="mt-3 text-sm text-ink-500 leading-7 max-w-2xl">
        面向认知安全的分析助手。把可疑对话、舆情或传播材料发给我，我会先讲清楚判断，再带你进入场景分析和对照路径或传播关系图。
      </p>
      <p className="mt-4 text-sm text-ink-900">有什么我可以帮你的吗？</p>
      <div className="mt-4 flex flex-wrap gap-2">
        {EXAMPLES.map((item) => (
          <button key={item.label} type="button" className="px-3 py-1.5 rounded-full border border-border bg-white text-xs text-ink-500 hover:border-brand hover:text-brand" onClick={() => onExample(item.text)}>
            {item.label}
          </button>
        ))}
      </div>
      <FeatureIntroCards onFeature={onFeature} />
    </div>
  )
}

function ChatMessage({ message, navigate, sessionId, avatarKey, copied, onCopy, onEdit, onRegenerate, onSuggest, conversationPrefill }) {
  const isUser = message.role === 'user'
  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%]">
          <div className="rounded-3xl rounded-tr-md bg-brand text-white px-4 py-3 text-sm leading-7">
            {message.content}
            {message.fileNames?.length > 0 && <div className="mt-1 text-xs text-white/80">附件：{message.fileNames.join('、')}</div>}
          </div>
          {onEdit && (
            <div className="mt-1 flex justify-end">
              <button type="button" className="text-[11px] text-ink-300 hover:text-brand" onClick={onEdit}>修改这句</button>
            </div>
          )}
        </div>
      </div>
    )
  }

  const reply = resolveAssistantReply(message)
  const scenario = message.scenario || SCENARIOS[message.result?.scenario_type]
  const prefillText = conversationPrefill || message.navigationState?.prefillText || message.inputText || ''
  const navigationState = {
    ...(message.navigationState || {}),
    sessionId,
    prefillText,
    autoAnalyze: true,
  }
  return (
    <div className="flex gap-3">
      <MiroAvatar avatarKey={avatarKey} />
      <div className="min-w-0 flex-1">
        <ThoughtPath steps={message.thinking || []} durationMs={message.thoughtDurationMs} />
        {(message.result?.agent_trace || []).length > 0 && (
          <div className="mb-4">
            <ExpandableFrame title="谁在何时对谁做了什么" hint="逐步说明，点击后可完整翻阅">
              <AgentTracePanel events={message.result.agent_trace} scenario={message.result?.scenario_type || ''} />
            </ExpandableFrame>
          </div>
        )}
        <div className={`text-sm leading-7 text-ink-900 ${message.tone === 'error' ? 'text-rose-700' : ''}`}>
          {reply.lead && <p className="text-[15px] font-medium text-ink-900">{reply.lead}</p>}
          {(reply.paragraphs || []).filter((paragraph) => !isInternalSkipCopy(paragraph)).map((paragraph) => (
            <p key={paragraph} className="mt-3 text-ink-500">{paragraph}</p>
          ))}
          {(reply.sections || []).map((section) => (
            <div key={section.heading || section.title} className={`mt-5 rounded-2xl border px-4 py-3 ${section.emphasis ? 'border-brand-100 bg-brand-50/40' : 'border-transparent bg-transparent'}`}>
              <div className="flex items-center gap-2">
                <div className="text-sm font-semibold text-ink-900">{section.heading || section.title}</div>
                {section.emphasis && <span className="text-[10px] px-2 py-0.5 rounded-full bg-brand text-white">主视角</span>}
              </div>
              {section.body && <p className="mt-1.5 text-ink-500">{section.body}</p>}
              {section.items?.length > 0 && (
                <ol className="mt-2 space-y-1.5 list-decimal pl-5 text-ink-900">
                  {section.items.filter((item) => item && !isInternalSkipCopy(item)).map((item) => <li key={item}>{item}</li>)}
                </ol>
              )}
            </div>
          ))}
          {reply.closing && <p className="mt-4 text-ink-900">{reply.closing}</p>}
        </div>
        {message.featureCards || reply.show_feature_cards ? (
          <FeatureIntroCards onFeature={(feature) => navigate('/simulation-map', { state: { featureKey: feature.key, sessionId } })} />
        ) : null}
        {scenario && message.result?.recognition_status === 'recognized' && (
          <div className="mt-4 space-y-2">
            <JumpLinkCard
              icon={scenario.icon}
              title={`进入${scenario.name}场景分析`}
              description="打开完整的风险画像、证据、策略与干预结果。"
              tone={scenario.theme}
              to={scenario.path}
              state={navigationState}
            />
            <JumpLinkCard
              icon="network"
              title={inferFeatureKey(message.result) === 'propagation_graph' ? '打开传播关系图' : '打开个体对照路径图'}
              description={inferFeatureKey(message.result) === 'propagation_graph'
                ? `查看源头到扩散的跳数关系（约 ${message.result?.agentCount || '50'} 个代理）`
                : '查看继续被诱导 / 及时止损的对照路径'}
              tone="sand"
              to="/simulation-map"
              state={{
                analysis: message.result,
                inputText: message.inputText,
                featureKey: inferFeatureKey(message.result),
                sessionId,
              }}
            />
          </div>
        )}
        {(reply.suggested_followups || []).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {reply.suggested_followups.map((item) => (
              <button key={item} type="button" className="px-3 py-1.5 rounded-full border border-border bg-white text-xs text-ink-500 hover:border-brand hover:text-brand" onClick={() => onSuggest(item)}>
                {item}
              </button>
            ))}
          </div>
        )}
        <div className="mt-2 flex gap-3 text-[11px] text-ink-300">
          <button type="button" onClick={onCopy}>{copied ? '已复制' : '复制回复'}</button>
          {onRegenerate && <button type="button" onClick={onRegenerate}>重新生成</button>}
        </div>
      </div>
    </div>
  )
}

function inferFeatureKey(result) {
  const scenario = result?.scenario_type || result?.scenario || ''
  if (scenario === 'event_propagation' || scenario === 'public_opinion') return 'propagation_graph'
  return 'counterfactual'
}

function resolveAssistantReply(message) {
  const primary = message?.reply || {}
  if (primary.lead || (primary.paragraphs || []).length || (primary.sections || []).length) return primary
  const nested = message?.result?.chat_reply || {}
  if (nested.lead || (nested.paragraphs || []).length || (nested.sections || []).length) return nested
  const summary = message?.result?.extracted_summary || ''
  const reason = message?.result?.reason || ''
  if (!summary && !reason) return primary
  return {
    style: message?.result?.scenario_type || '',
    lead: summary ? `先说结论：${summary}` : '我已经读完这段材料。',
    paragraphs: [reason, '完整证据放在场景分析页；诈骗看对照路径，舆情/事件看传播关系。'].filter(Boolean),
    sections: [],
    closing: '你可以继续用自然语言问我，或打开下面的分析入口。',
    suggested_followups: primary.suggested_followups || [],
  }
}

function buildAssistantMessage(text, result, sessionId, durationMs = 0) {
  const scenario = SCENARIOS[result?.scenario_type]
  return {
    id: `${Date.now()}-assistant`,
    role: 'assistant',
    reply: result?.chat_reply || {},
    thinking: result?.thinking || [],
    result,
    inputText: text,
    scenario,
    thoughtDurationMs: durationMs,
    navigationState: {
      prefillText: text,
      extractedFields: result?.extracted_fields || {},
      extractedSummary: result?.extracted_summary || '',
      sessionId,
    },
  }
}
