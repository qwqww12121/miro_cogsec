import { useEffect, useRef, useState } from 'react'
import Icon from './Icon'
import { transcribeCogSec } from '../api/cogsec'

const ACCEPT = '.pdf,.txt,.md,.markdown,.json,.csv,audio/*'
const ACCENT_CLASSES = {
  brand: { ring: 'focus-within:ring-brand/20', button: 'bg-brand hover:bg-brand-600' },
  leaf: { ring: 'focus-within:ring-leaf/20', button: 'bg-leaf hover:bg-leaf-600' },
  sand: { ring: 'focus-within:ring-sand/20', button: 'bg-sand hover:bg-sand-600' },
}

function speechRecognitionConstructor() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

function appendTranscript(current, transcript) {
  const next = String(transcript || '').trim()
  if (!next) return current
  return current.trim() ? `${current.trim()}\n${next}` : next
}

/**
 * Chat-style multimodal composer.
 *
 * The interaction follows the same browser primitives used by open-source
 * chat UIs: hidden file input for the plus button, SpeechRecognition when the
 * browser exposes it, and MediaRecorder as an audio-blob fallback.  The
 * backend receives files/audio through the existing CogSec API adapter.
 */
export default function MultimodalComposer({
  value,
  onChange,
  files = [],
  onFilesChange,
  onRemoveFile,
  loading = false,
  placeholder = '输入材料，或使用附件和语音补充…',
  rows = 8,
  accent = 'brand',
  onSend,
}) {
  const accentClasses = ACCENT_CLASSES[accent] || ACCENT_CLASSES.brand
  const fileInputRef = useRef(null)
  const textareaRef = useRef(null)
  const recognitionRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const mediaStreamRef = useRef(null)
  const chunksRef = useRef([])
  const valueRef = useRef(value)
  const shouldRestartRecognitionRef = useRef(false)
  const [listening, setListening] = useState(false)
  const [interimText, setInterimText] = useState('')
  const [voiceError, setVoiceError] = useState('')

  useEffect(() => {
    valueRef.current = value
  }, [value])

  const emitValue = (next) => {
    valueRef.current = next
    onChange?.({ target: { value: next } })
  }

  const canSend = Boolean(String(value || '').trim() || files.length)
  const sendNow = () => {
    if (loading || !canSend) return
    if (onSend) {
      onSend(valueRef.current)
      return
    }
    textareaRef.current?.form?.requestSubmit()
  }

  const onKeyDown = (event) => {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    sendNow()
  }

  const startBrowserRecognition = () => {
    const Recognition = speechRecognitionConstructor()
    if (!Recognition) return false

    const recognition = new Recognition()
    recognition.lang = 'zh-CN'
    recognition.continuous = true
    recognition.interimResults = true
    recognition.onresult = (event) => {
      let finalText = ''
      let interim = ''
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const text = event.results[index][0]?.transcript || ''
        if (event.results[index].isFinal) finalText += text
        else interim += text
      }
      if (finalText.trim()) emitValue(appendTranscript(valueRef.current, finalText))
      setInterimText(interim)
    }
    recognition.onerror = (event) => {
      shouldRestartRecognitionRef.current = false
      // Chrome/Edge may expose SpeechRecognition but still reject the
      // vendor network service (for example when its speech endpoint is
      // unavailable).  Keep the mic button useful by falling back to a
      // local MediaRecorder blob, which is sent to our backend ASR adapter.
      if (event.error === 'network' || event.error === 'service-not-allowed') {
        recognitionRef.current = null
        setInterimText('')
        startMediaRecorder({
          notice: '浏览器语音服务不可用，已切换为录音上传；再次点击麦克风结束录音。',
        })
        return
      }
      setVoiceError(`浏览器语音识别失败：${event.error || 'unknown'}`)
      setListening(false)
    }
    recognition.onend = () => {
      if (shouldRestartRecognitionRef.current) {
        try {
          recognition.start()
          return
        } catch {
          // The browser may reject an immediate restart; stop gracefully.
        }
      }
      setListening(false)
      setInterimText('')
    }
    recognitionRef.current = recognition
    shouldRestartRecognitionRef.current = true
    recognition.start()
    setVoiceError('')
    setListening(true)
    return true
  }

  const startMediaRecorder = async ({ notice = '' } = {}) => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setVoiceError('当前浏览器不支持录音，请使用 Chrome/Edge 或直接上传音频文件。')
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : 'audio/webm'
      const recorder = new MediaRecorder(stream, { mimeType })
      chunksRef.current = []
      recorder.ondataavailable = (event) => {
        if (event.data?.size) chunksRef.current.push(event.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop())
        mediaStreamRef.current = null
        const blob = new Blob(chunksRef.current, { type: mimeType })
        const file = new File([blob], `recording-${Date.now()}.webm`, { type: mimeType })
        try {
          const result = await transcribeCogSec(file, 'zh')
          emitValue(appendTranscript(valueRef.current, result.text))
          setVoiceError('')
        } catch (error) {
          setVoiceError(error.message || '语音转写未完成：请配置 ASR 服务（MIRO_SPEECH_API_KEY），或安装本地 faster-whisper。')
        }
      }
      mediaStreamRef.current = stream
      mediaRecorderRef.current = recorder
      recorder.start()
      setVoiceError(notice)
      setListening(true)
    } catch (error) {
      setVoiceError(error.message || '无法访问麦克风，请检查浏览器权限。')
    }
  }

  const startVoice = () => {
    if (startBrowserRecognition()) return
    startMediaRecorder()
  }

  const stopVoice = () => {
    shouldRestartRecognitionRef.current = false
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      recognitionRef.current = null
    }
    const recorder = mediaRecorderRef.current
    if (recorder && recorder.state !== 'inactive') recorder.stop()
    mediaRecorderRef.current = null
    setListening(false)
    setInterimText('')
  }

  const toggleVoice = () => {
    if (listening) stopVoice()
    else startVoice()
  }

  const onFilePicked = (event) => {
    const selected = Array.from(event.target.files || [])
    if (selected.length) onFilesChange?.([...files, ...selected])
    event.target.value = ''
  }

  useEffect(() => () => stopVoice(), [])

  return (
    <div className={`rounded-2xl border bg-white shadow-sm focus-within:ring-2 ${accentClasses.ring}`}>
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(event) => {
          valueRef.current = event.target.value
          onChange?.(event)
        }}
        onKeyDown={onKeyDown}
        rows={rows}
        disabled={loading}
        placeholder={placeholder}
        className="w-full resize-y border-0 bg-transparent px-4 pt-3 text-sm leading-6 text-ink-900 placeholder:text-ink-300 focus:outline-none focus:ring-0"
      />

      {(files.length > 0 || interimText || voiceError) && (
        <div className="flex flex-wrap items-center gap-1.5 px-3 pb-2 text-[11px]">
          {files.map((file, index) => (
            <span key={`${file.name}-${index}`} className="inline-flex max-w-full items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-ink-600">
              <Icon name="paperclip" className="h-3 w-3 shrink-0" />
              <span className="max-w-[180px] truncate">{file.name}</span>
              <button type="button" className="text-ink-400 hover:text-ink-900" onClick={() => onRemoveFile?.(index)} aria-label={`移除 ${file.name}`}>×</button>
            </span>
          ))}
          {interimText && <span className="text-ink-400">正在识别：{interimText}</span>}
          {voiceError && <span className="text-red-500">{voiceError}</span>}
        </div>
      )}

      <div className="flex items-center justify-between gap-2 px-3 pb-3">
        <div className="flex items-center gap-1">
          <input ref={fileInputRef} type="file" multiple accept={ACCEPT} className="hidden" onChange={onFilePicked} />
          <button type="button" className="inline-flex h-9 w-9 items-center justify-center rounded-full text-ink-500 hover:bg-slate-100" onClick={() => fileInputRef.current?.click()} aria-label="添加文件" title="添加文件">
            <Icon name="plus" className="h-5 w-5" />
          </button>
          <button type="button" className={`inline-flex h-9 w-9 items-center justify-center rounded-full ${listening ? 'bg-red-50 text-red-600' : 'text-ink-500 hover:bg-slate-100'}`} onClick={toggleVoice} disabled={loading} aria-label={listening ? '停止语音输入' : '开始语音输入'} title={listening ? '停止语音输入' : '开始语音输入'}>
            <Icon name="mic" className="h-5 w-5" />
          </button>
          <span className="hidden text-[11px] text-ink-400 sm:inline">支持 PDF、TXT、MD、JSON、CSV；麦克风可直接转写</span>
        </div>
        <button type="button" className={`inline-flex h-9 min-w-9 items-center justify-center rounded-full px-3 text-white shadow-sm disabled:cursor-not-allowed disabled:opacity-50 ${accentClasses.button}`} disabled={loading || !canSend} onClick={sendNow} aria-label="发送并分析" title="发送并分析">
          {listening ? <span className="flex h-4 items-center gap-0.5" aria-hidden="true"><i className="h-2 w-0.5 animate-pulse rounded bg-white" /><i className="h-4 w-0.5 animate-pulse rounded bg-white [animation-delay:120ms]" /><i className="h-3 w-0.5 animate-pulse rounded bg-white [animation-delay:240ms]" /><i className="h-5 w-0.5 animate-pulse rounded bg-white [animation-delay:360ms]" /></span> : <Icon name="wave" className="h-5 w-5" />}
        </button>
      </div>
    </div>
  )
}
