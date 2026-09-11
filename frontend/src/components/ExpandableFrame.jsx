import { cloneElement, isValidElement, useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from './Icon'

const SIZE_CLASS = {
  md: 'w-full max-w-2xl max-h-[82vh]',
  lg: 'w-full max-w-4xl max-h-[86vh]',
  xl: 'w-full max-w-5xl max-h-[90vh]',
  graph: 'w-[min(98vw,1440px)] h-[92vh] max-h-[92vh]',
}

/**
 * Shared reading frame: hover slightly enlarges the card; click keeps a larger
 * scrollable modal so long graphs and conclusions can be reviewed.
 */
export default function ExpandableFrame({
  title,
  hint = '',
  children,
  trigger = 'card',
  size = 'lg',
  tone = 'light',
  className = '',
  previewClassName = '',
  modalClassName = '',
}) {
  const [open, setOpen] = useState(false)
  const labelId = useId()
  const dark = tone === 'dark'

  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') setOpen(false)
    }
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    window.addEventListener('keydown', onKey)
    return () => {
      document.body.style.overflow = previous
      window.removeEventListener('keydown', onKey)
    }
  }, [open])

  const openModal = (event) => {
    event?.stopPropagation?.()
    setOpen(true)
  }

  const isGraph = size === 'graph'
  const shell = dark
    ? 'overflow-hidden bg-slate-900 border border-slate-800 text-white'
    : 'overflow-hidden bg-white border border-border text-ink-900'
  const header = dark ? 'border-white/10' : 'border-border'
  const hintColor = dark ? 'text-white/50' : 'text-ink-500'
  const titleColor = dark ? 'text-white' : 'text-ink-900'

  return (
    <>
      <div
        className={`group relative rounded-xl shadow-card transition-transform duration-200 ease-out hover:z-20 hover:scale-[1.03] hover:shadow-xl ${shell} ${className}`}
        onClick={trigger === 'card' ? openModal : undefined}
      >
        <div
          className={`flex items-start justify-between gap-3 px-4 py-3 border-b ${header}`}
          onClick={trigger === 'chrome' ? openModal : undefined}
        >
          <div className="min-w-0">
            {title ? <div id={labelId} className={`text-sm font-semibold ${titleColor}`}>{title}</div> : null}
            {hint ? <p className={`mt-1 text-[11px] leading-relaxed ${hintColor}`}>{hint}</p> : null}
          </div>
          <button
            type="button"
            className={`shrink-0 inline-flex items-center gap-1 rounded-lg px-2 py-1 text-[11px] ${dark ? 'bg-white/10 text-white/80 hover:bg-white/16' : 'bg-slate-100 text-ink-600 hover:bg-slate-200'}`}
            onClick={openModal}
          >
            <Icon name="expand" className="w-3.5 h-3.5" />
            {isGraph ? '放大星图' : '放大查阅'}
          </button>
        </div>
        <div
          className={`expand-frame-preview ${previewClassName}`}
          onClick={(event) => event.stopPropagation()}
        >
          {children}
        </div>
        <div className={`pointer-events-none absolute inset-x-0 bottom-0 px-4 py-2 text-[10px] opacity-0 transition-opacity group-hover:opacity-100 ${dark ? 'bg-gradient-to-t from-slate-950/90 text-white/70' : 'bg-gradient-to-t from-white/95 text-ink-400'}`}>
          {isGraph ? '悬停放大 · 点击放大下面的星图' : '悬停放大 · 点击查阅更大卡片'}
        </div>
      </div>

      {open && createPortal(
        <div
          className="fixed inset-0 z-[80] bg-slate-950/55 backdrop-blur-[2px] flex items-center justify-center p-4 sm:p-6"
          onClick={() => setOpen(false)}
        >
          <div
            className={`${SIZE_CLASS[size] || SIZE_CLASS.lg} rounded-2xl shadow-2xl overflow-hidden flex flex-col ${dark ? 'bg-slate-900 border border-slate-700' : 'bg-white border border-border'}`}
            role="dialog"
            aria-modal="true"
            aria-labelledby={labelId}
            onClick={(event) => event.stopPropagation()}
          >
            <div className={`flex items-center justify-between gap-3 border-b shrink-0 ${header} ${isGraph ? 'px-4 py-2' : 'px-5 py-4'}`}>
              <div className="min-w-0">
                {title ? <div className={`${isGraph ? 'text-sm' : 'text-base'} font-semibold ${titleColor}`}>{title}</div> : null}
                {hint && !isGraph ? <p className={`mt-1 text-xs leading-relaxed ${hintColor}`}>{hint}</p> : null}
              </div>
              <button type="button" className="btn-ghost text-xs shrink-0" onClick={() => setOpen(false)}>
                关闭
              </button>
            </div>
            <div
              className={`expand-modal-body min-h-0 flex-1 ${isGraph ? 'relative overflow-hidden' : 'overflow-auto'} ${modalClassName}`}
            >
              {isValidElement(children) ? cloneElement(children) : children}
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  )
}
