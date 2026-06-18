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
          <a
            href="https://github.com/qwqww12121/miro_cogsec"
            target="_blank"
            rel="noopener noreferrer"
            className="ml-2 px-3 py-1.5 rounded-md text-sm text-ink-500 hover:bg-slate-50 flex items-center gap-1.5"
          >
            <svg viewBox="0 0 16 16" className="w-4 h-4 fill-current" aria-hidden="true">
              <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z" />
            </svg>
            GitHub
          </a>
        </nav>
      </div>
    </header>
  )
}
