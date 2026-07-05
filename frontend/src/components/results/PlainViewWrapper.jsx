import { useState, useEffect, useRef } from 'react'
import { plainifyResult, extractPlainifyInput } from '../../api/plainify'
import { getRiskBand } from '../../scenarios/glossary'
import Spinner from '../Spinner'
import Icon from '../Icon'

/**
 * 包裹任意分析结果组件，在顶部加"专业视图 / 通俗视图"切换 Tab。
 *
 * 用法：
 *   <PlainViewWrapper data={data}>
 *     <FraudImResult data={data} loading={loading} error={error} />
 *   </PlainViewWrapper>
 *
 * - data=null 时直接透传 children（结果组件自行处理 loading/empty/error）
 * - data 有值时显示 Tab，通俗视图结果缓存，来回切换不重复请求
 * - data 变化（新一次分析完成）时自动重置缓存并切回专业视图
 */
export default function PlainViewWrapper({ data, scenarioType, children }) {
  const [viewMode, setViewMode] = useState('expert')
  const [plainData, setPlainData] = useState(null)
  const [plainLoading, setPlainLoading] = useState(false)
  const [plainError, setPlainError] = useState(null)
  // 用于取消过期的异步请求（防止 data 换了但旧请求后返回覆盖新状态）
  const fetchIdRef = useRef(0)

  useEffect(() => {
    fetchIdRef.current += 1  // 作废任何正在进行的旧请求
    setPlainData(null)
    setPlainError(null)
    setViewMode('expert')
  }, [data])

  const handleSwitchToPlain = async () => {
    setViewMode('plain')
    if (plainData) return   // 已有缓存，直接展示
    if (plainLoading) return // 正在加载中，不重复请求

    const myId = ++fetchIdRef.current
    setPlainLoading(true)
    setPlainError(null)
    try {
      const input = extractPlainifyInput(data, scenarioType)
      const result = await plainifyResult(input)
      if (fetchIdRef.current === myId) setPlainData(result)
    } catch (err) {
      if (fetchIdRef.current === myId) {
        setPlainError('通俗解读生成失败，请重试')
      }
    } finally {
      if (fetchIdRef.current === myId) setPlainLoading(false)
    }
  }

  // 没有分析结果时，透传给子组件（子组件自己渲染 loading/empty/error）
  if (!data) return children

  const band = getRiskBand(data?.profile?.overall_vulnerability_score)

  return (
    <>
      <ViewToggle
        viewMode={viewMode}
        onExpert={() => setViewMode('expert')}
        onPlain={handleSwitchToPlain}
      />
      {viewMode === 'expert' ? (
        children
      ) : (
        <PlainContent
          data={plainData}
          loading={plainLoading}
          error={plainError}
          band={band}
          onRetry={handleSwitchToPlain}
        />
      )}
    </>
  )
}

// ---------- 子组件 ----------

function ViewToggle({ viewMode, onExpert, onPlain }) {
  return (
    <div className="bg-slate-100 rounded-xl p-1 flex gap-1">
      <button
        type="button"
        onClick={onExpert}
        className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-medium transition-all ${
          viewMode === 'expert'
            ? 'bg-white shadow-card text-ink-900'
            : 'text-ink-500 hover:text-ink-700'
        }`}
      >
        专业视图
      </button>
      <button
        type="button"
        onClick={onPlain}
        className={`flex-1 py-1.5 px-3 rounded-lg text-xs font-medium transition-all ${
          viewMode === 'plain'
            ? 'bg-white shadow-card text-ink-900'
            : 'text-ink-500 hover:text-ink-700'
        }`}
      >
        通俗视图
      </button>
    </div>
  )
}

function PlainContent({ data, loading, error, band, onRetry }) {
  if (loading) {
    return (
      <div className="card p-10 flex flex-col items-center gap-3 text-center">
        <Spinner className="w-5 h-5 text-brand" />
        <div className="text-sm text-ink-500">正在生成通俗解读…</div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="card p-5">
        <div className="rounded-lg bg-rose-50 border border-rose-100 px-4 py-3 flex items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-rose-600 text-sm">
            <Icon name="alert" className="w-4 h-4 flex-none" />
            <span>{error}</span>
          </div>
          <button
            type="button"
            className="text-xs text-rose-600 underline flex-none"
            onClick={onRetry}
          >
            重试
          </button>
        </div>
      </div>
    )
  }

  if (!data) return null

  const riskStyle = (() => {
    if (!band) return { wrap: 'border-slate-200 bg-slate-50', text: 'text-ink-700', icon: 'info' }
    if (band.level === 'high')   return { wrap: 'border-rose-200 bg-rose-50',  text: 'text-rose-700',  icon: 'alert' }
    if (band.level === 'medium') return { wrap: 'border-amber-200 bg-amber-50', text: 'text-amber-700', icon: 'alert' }
    return                              { wrap: 'border-leaf-100 bg-leaf-50',   text: 'text-leaf-700',  icon: 'check' }
  })()

  return (
    <div className="space-y-4">
      {/* 大白话摘要 */}
      <div className="card p-5">
        <div className="flex items-center gap-2 mb-3">
          <Icon name="spark" className="w-4 h-4 text-brand" />
          <span className="text-sm font-semibold text-ink-900">简单说就是…</span>
          {band && <span className={`tag ml-auto ${band.badge}`}>{band.label}</span>}
        </div>
        <p className="text-sm text-ink-900 leading-loose">{data.plain_summary}</p>
      </div>

      {/* 行动建议 */}
      <div className={`rounded-xl border-2 p-5 ${riskStyle.wrap}`}>
        <div className={`flex items-center gap-1.5 mb-2 text-xs font-semibold ${riskStyle.text}`}>
          <Icon name={riskStyle.icon} className="w-3.5 h-3.5" />
          最重要的一件事
        </div>
        <p className={`text-sm font-medium leading-relaxed ${riskStyle.text}`}>
          {data.action_advice}
        </p>
      </div>
    </div>
  )
}
