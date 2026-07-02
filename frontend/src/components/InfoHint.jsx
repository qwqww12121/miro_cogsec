import Icon from './Icon'

/**
 * 小信息图标 + 悬浮/聚焦提示。
 * - 鼠标悬停（group-hover）显示说明
 * - 键盘聚焦 / 移动端点击（tabIndex=0 + group-focus-within）也能显示
 * - 不占用主要版面：图标很小，提示浮层 absolute 定位
 */
export default function InfoHint({ text, className = '' }) {
  if (!text) return null
  return (
    <span
      className={`relative inline-flex group/hint align-middle ${className}`}
      tabIndex={0}
    >
      <Icon name="info" className="w-3.5 h-3.5 text-ink-300 cursor-help group-hover/hint:text-ink-500 group-focus-within/hint:text-ink-500" />
      <span
        role="tooltip"
        className="pointer-events-none absolute left-1/2 top-full z-30 mt-1.5 w-52 -translate-x-1/2 translate-y-0.5 rounded-md bg-ink-900 px-2.5 py-1.5 text-[11px] leading-relaxed text-white opacity-0 shadow-card transition-all duration-150 group-hover/hint:translate-y-0 group-hover/hint:opacity-100 group-focus-within/hint:translate-y-0 group-focus-within/hint:opacity-100"
      >
        {text}
      </span>
    </span>
  )
}
