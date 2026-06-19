import { useState } from 'react'
import Section from './Section'
import { answerFollowup } from '../api/cogsec'

export default function AssistantMessageBlock({ data }) {
  const [followupText, setFollowupText] = useState(null)
  const [followupLoading, setFollowupLoading] = useState(false)
  const [activeFollowup, setActiveFollowup] = useState(null)

  if (!data?.assistant_message) return null

  const handleFollowup = async (question) => {
    const state = data?.conversation_state
    if (!state || followupLoading) return
    setActiveFollowup(question)
    setFollowupLoading(true)
    setFollowupText(null)
    try {
      const resp = await answerFollowup(state, question, state.tone)
      setFollowupText(resp?.assistant_message || null)
    } catch {
      setFollowupText('追问失败，请重新发起完整分析。')
    } finally {
      setFollowupLoading(false)
    }
  }

  return (
    <Section title="系统结论">
      <div className="text-sm text-ink-900 leading-relaxed whitespace-pre-wrap">
        {data.assistant_message}
      </div>

      {data.suggested_followups?.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-2">
          {data.suggested_followups.slice(0, 4).map((item) => (
            <button
              key={item}
              type="button"
              className={`btn-ghost text-xs ${activeFollowup === item && followupLoading ? 'opacity-60 cursor-wait' : ''}`}
              onClick={() => handleFollowup(item)}
              disabled={followupLoading}
            >
              {item}
            </button>
          ))}
        </div>
      )}

      {followupLoading && (
        <div className="mt-3 text-xs text-ink-500 flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-brand animate-pulse" />
          正在回答「{activeFollowup}」…
        </div>
      )}

      {followupText && !followupLoading && (
        <div className="mt-3 pt-3 border-t border-border">
          <div className="text-[11px] text-ink-500 mb-1">追问：{activeFollowup}</div>
          <div className="text-sm text-ink-900 leading-relaxed whitespace-pre-wrap">
            {followupText}
          </div>
        </div>
      )}
    </Section>
  )
}
