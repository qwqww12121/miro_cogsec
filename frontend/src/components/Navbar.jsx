import { NavLink, Link } from 'react-router-dom'

export default function Navbar() {
  return (
    <header className="sticky top-0 z-30 bg-white/85 backdrop-blur border-b border-border">
      <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-md bg-brand text-white flex items-center justify-center font-bold text-sm">
            C
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold text-ink-900">CogSec 认知安全分析系统</div>
            <div className="text-[11px] text-ink-500">Cognitive Security Analysis Platform</div>
          </div>
        </Link>
        <nav className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `px-3 py-1.5 rounded-md text-sm ${
                isActive ? 'bg-slate-100 text-ink-900 font-medium' : 'text-ink-500 hover:bg-slate-50'
              }`
            }
          >
            首页
          </NavLink>
          <NavLink
            to="/benchmark"
            className={({ isActive }) =>
              `px-3 py-1.5 rounded-md text-sm ${
                isActive ? 'bg-slate-100 text-ink-900 font-medium' : 'text-ink-500 hover:bg-slate-50'
              }`
            }
          >
            Benchmark 对比
          </NavLink>
          <NavLink
            to="/judge-compare"
            className={({ isActive }) =>
              `px-3 py-1.5 rounded-md text-sm ${
                isActive ? 'bg-slate-100 text-ink-900 font-medium' : 'text-ink-500 hover:bg-slate-50'
              }`
            }
          >
            裁判对比
          </NavLink>
        </nav>
      </div>
    </header>
  )
}
