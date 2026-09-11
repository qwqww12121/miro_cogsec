// 单条裁判对比卡片：头部（输入 + 判决标签）可点击展开，
// 展开后左=我方系统(miro_cogsec)、右=baseline(llm_only)，底部为裁判理由。
// 注意：A/B 槽位已在页面层按系统名归位，这里只接收 ours / baseline，不再处理 A/B。

import { useState } from 'react'
import ReportText from './ReportText'
import ScoreBars from './ScoreBars'

const SCEN_LABEL = {
  fraud_im: '诈骗即时通讯',
  public_opinion: '舆情分析',
  event_propagation: '事件传播分析',
}

// 裁判理由是大模型原文，用 "Answer A/B" / "答案A/B" / "Ans A/B" / 裸 "A/B" 指代两份答卷。
// 页面其他地方已统一成"我方系统 / baseline"，这里按本条 A/B→系统归属逐条替换
// （9 条槽位翻转，不能全局统一替换）。先处理带前缀的形式，再处理裸 A/B，避免误伤。
function rewriteRationale(text, oursSlot) {
  const mapA = oursSlot === 'a' ? '我方系统' : 'baseline'
  const mapB = oursSlot === 'a' ? 'baseline' : '我方系统'
  let t = String(text || '')
  t = t.replace(/(?:answer|ans|答案)\s*([AB])/gi, (_m, letter) =>
    letter.toUpperCase() === 'A' ? mapA : mapB
  )
  t = t.replace(/(?<![A-Za-z])([AB])(?![A-Za-z])/g, (_m, letter) =>
    letter === 'A' ? mapA : mapB
  )
  return t
}

export default function JudgeCard({ record }) {
  const [open, setOpen] = useState(false)
  const {
    id,
    scenarioType,
    inputText,
    ours,
    baseline,
    oursWon,
    oursSlot,
    rationale,
  } = record

  const scenLabel = SCEN_LABEL[scenarioType] || scenarioType

  return (
    <div className="card overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full text-left p-4 flex items-start gap-3 hover:bg-slate-50/60 transition-colors"
      >
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="tag bg-slate-100 text-ink-500">{scenLabel}</span>
            <span
              className={`tag ${oursWon ? 'bg-leaf-50 text-leaf-600' : 'bg-sand-50 text-sand-600'}`}
            >
              {oursWon ? '我方系统胜' : 'Baseline 胜'}
            </span>
            <span className="text-[11px] text-ink-300 ml-auto shrink-0 font-mono">{id}</span>
          </div>
          <div className="text-[13px] text-ink-900">{inputText}</div>
        </div>
        <span
          className={`text-ink-300 text-[11px] mt-1 transition-transform duration-200 ${
            open ? 'rotate-90' : ''
          }`}
        >
          ▶
        </span>
      </button>

      {open && (
        <div className="border-t border-border p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* 我方系统 */}
            <div className="rounded-lg border border-brand-100 bg-brand-50/40 p-3">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full bg-brand" />
                <span className="text-xs font-semibold text-brand-600">我方系统 · MiroCog-Guard</span>
                {oursWon && <span className="tag bg-leaf-50 text-leaf-600 ml-auto">胜</span>}
              </div>
              <ReportText text={ours.text} />
              <div className="mt-3 pt-3 border-t border-brand-100">
                <ScoreBars scores={ours.scores} color="#4a90d9" />
              </div>
            </div>

            {/* Baseline */}
            <div className="rounded-lg border border-border bg-slate-50 p-3">
              <div className="flex items-center gap-2 mb-2">
                <span className="w-2 h-2 rounded-full bg-ink-300" />
                <span className="text-xs font-semibold text-ink-500">对照基线 · 通用大模型直答</span>
                {!oursWon && <span className="tag bg-sand-50 text-sand-600 ml-auto">胜</span>}
              </div>
              <ReportText text={baseline.text} />
              <div className="mt-3 pt-3 border-t border-border">
                <ScoreBars scores={baseline.scores} color="#cbd5e1" />
              </div>
            </div>
          </div>

          {/* 裁判理由 */}
          <div className="rounded-lg bg-slate-50 border border-border p-3">
            <div className="text-[11px] font-medium text-ink-500 mb-1">
              裁判判决理由
            </div>
            <div className="text-[13px] text-ink-900 leading-relaxed">
              {rewriteRationale(rationale, oursSlot)}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
