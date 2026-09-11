import { Routes, Route, Navigate, useLocation } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import FraudImPage from './pages/scenarios/FraudImPage'
import PublicOpinionPage from './pages/scenarios/PublicOpinionPage'
import EventPropagationPage from './pages/scenarios/EventPropagationPage'
import ChatPage from './pages/ChatPage'
import SimulationMapPage from './pages/SimulationMapPage'

export default function App() {
  const { pathname } = useLocation()
  const immersive = pathname === '/chat' || pathname === '/simulation-map'

  return (
    <div className={immersive ? 'h-screen flex flex-col overflow-hidden' : 'min-h-screen flex flex-col'}>
      {!immersive && <Navbar />}
      <main className="flex-1 min-h-0">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/chat" element={<ChatPage />} />
          <Route path="/simulation-map" element={<SimulationMapPage />} />
          <Route path="/scenario/fraud-im" element={<FraudImPage />} />
          <Route path="/scenario/public-opinion" element={<PublicOpinionPage />} />
          <Route path="/scenario/event-propagation" element={<EventPropagationPage />} />
          <Route path="/benchmark" element={<Navigate to="/" replace />} />
          <Route path="/judge-compare" element={<Navigate to="/" replace />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      {!immersive && (
        <footer className="border-t border-border bg-white">
          <div className="max-w-7xl mx-auto px-6 py-4 text-xs text-ink-500 flex justify-between">
            <div>© CogSec · 认知安全分析系统</div>
            <div>v0.2 · Vite + React</div>
          </div>
        </footer>
      )}
    </div>
  )
}
