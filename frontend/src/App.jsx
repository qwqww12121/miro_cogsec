import { Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import Home from './pages/Home'
import FraudImPage from './pages/scenarios/FraudImPage'
import PublicOpinionPage from './pages/scenarios/PublicOpinionPage'
import EventPropagationPage from './pages/scenarios/EventPropagationPage'
import BenchmarkPage from './pages/BenchmarkPage'

export default function App() {
  return (
    <div className="min-h-screen flex flex-col">
      <Navbar />
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/scenario/fraud-im" element={<FraudImPage />} />
          <Route path="/scenario/public-opinion" element={<PublicOpinionPage />} />
          <Route path="/scenario/event-propagation" element={<EventPropagationPage />} />
          <Route path="/benchmark" element={<BenchmarkPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
      <footer className="border-t border-border bg-white">
        <div className="max-w-7xl mx-auto px-6 py-4 text-xs text-ink-500 flex justify-between">
          <div>© CogSec · 认知安全分析系统</div>
          <div>v0.7 · Vite + React</div>
        </div>
      </footer>
    </div>
  )
}
