import { Link } from 'react-router-dom'

export default function Breadcrumbs({ items = [] }) {
  return (
    <nav className="text-xs text-ink-500 flex items-center gap-1.5">
      {items.map((item, idx) => {
        const last = idx === items.length - 1
        return (
          <span key={idx} className="flex items-center gap-1.5">
            {item.to && !last ? (
              <Link to={item.to} className="hover:text-brand">{item.label}</Link>
            ) : (
              <span className={last ? 'text-ink-900 font-medium' : ''}>{item.label}</span>
            )}
            {!last && <span className="text-ink-300">/</span>}
          </span>
        )
      })}
    </nav>
  )
}
