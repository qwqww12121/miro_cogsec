import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import MultimodalComposer from './MultimodalComposer'
import Icon from './Icon'

/**
 * 首页入口只负责收集输入，然后进入完整的 MiroCogSec 对话页。
 * 分类、解释和跳转卡片都在 ChatPage 中完成，避免首页继续承担一块窄的结果面板。
 */
export default function IntelligentClassifier() {
  const navigate = useNavigate()
  const [text, setText] = useState('')
  const [attachments, setAttachments] = useState([])
  const [error, setError] = useState('')

  const openChat = (event) => {
    event.preventDefault()
    const trimmed = text.trim()
    if (!trimmed && attachments.length === 0) {
      setError('请填写内容，或添加文件/语音')
      return
    }
    setError('')
    navigate('/chat', {
      state: {
        initialText: trimmed,
        initialAttachments: attachments,
      },
    })
  }

  return (
    <div>
      <div className="mb-5">
        <h2 className="text-lg font-semibold text-ink-900">智能识别</h2>
        <p className="text-xs text-ink-500 mt-1">输入后会进入 MiroCogSec 对话页，像正常助手一样把判断讲清楚</p>
      </div>

      <form onSubmit={openChat}>
        <MultimodalComposer
          value={text}
          onChange={(event) => setText(event.target.value)}
          files={attachments}
          onFilesChange={setAttachments}
          onRemoveFile={(index) => setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))}
          rows={8}
          accent="brand"
          placeholder="例如：你好，或者粘贴对话记录、舆情文本、事件描述…"
        />

        {error && <div className="mt-2 text-xs text-rose-600">{error}</div>}
        <button
          type="submit"
          className="btn-primary mt-3"
          disabled={!text.trim() && attachments.length === 0}
        >
          <Icon name="spark" className="w-4 h-4 mr-1.5" />
          开始对话
        </button>
      </form>

      <div className="mt-3 text-[11px] text-ink-400 leading-relaxed">
        支持 PDF、TXT、MD、JSON、CSV 和语音输入；识别结果会在对话页中整理成清晰的步骤与建议。
      </div>
    </div>
  )
}
