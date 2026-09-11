/**
 * 可复用的旋转加载图标（animate-spin）。
 * 用于按钮 / 加载占位的"正在处理中"反馈。
 * 经典样式：淡色整圈轨道 + 一段高亮弧，平滑旋转。
 */
export default function Spinner({ className = 'w-4 h-4' }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24" fill="none">
      <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="3" className="opacity-25" />
      <path
        d="M21 12a9 9 0 0 0-9-9"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  )
}
