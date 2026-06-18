import { Link } from 'react-router-dom'
import { SCENARIO_LIST } from '../scenarios/config'
import ScenarioCard from '../components/ScenarioCard'
import IntelligentClassifier from '../components/IntelligentClassifier'
import Icon from '../components/Icon'

export default function Home() {
  return (
    <div className="max-w-7xl mx-auto px-6 pt-10 pb-14">
      <section className="text-center mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-50 text-brand text-xs font-medium mb-4">
          <span className="w-1.5 h-1.5 rounded-full bg-brand" />
          CogSec · 认知安全
        </div>
        <h1 className="text-3xl md:text-4xl font-bold text-ink-900 tracking-tight">
          CogSec 认知安全分析系统
        </h1>
        <p className="mt-3 text-sm md:text-base text-ink-500 max-w-2xl mx-auto leading-relaxed">
          基于认知科学与图谱推理，针对即时通讯诈骗、公共舆情与事件传播三类场景，
          输出可解释、可干预、可对比的安全分析报告。
        </p>
        <div className="mt-5 flex items-center justify-center gap-2">
          <Link to="/benchmark" className="btn-ghost">
            <Icon name="chart" className="w-4 h-4 mr-1.5" />
            查看 Benchmark 对比
          </Link>
        </div>
      </section>

      <section className="card p-6 md:p-8">
        <div className="grid grid-cols-1 lg:grid-cols-[1.15fr_auto_1fr] gap-6 lg:gap-10">
          <div className="min-w-0">
            <IntelligentClassifier />
          </div>

          <div className="hidden lg:flex justify-center">
            <div className="w-px bg-border" />
          </div>
          <div className="lg:hidden border-t border-border" />

          <div className="min-w-0">
            <div className="mb-5">
              <h2 className="text-lg font-semibold text-ink-900">手动选择</h2>
              <p className="text-xs text-ink-500 mt-1">直接进入指定场景</p>
            </div>
            <div className="flex flex-col gap-3">
              {SCENARIO_LIST.map((s) => (
                <ScenarioCard key={s.key} scenario={s} compact />
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="mt-10 grid grid-cols-1 md:grid-cols-3 gap-5">
        <FeatureItem
          icon="shield"
          title="可解释认知画像"
          text="基于 18 维认知特征生成脆弱度评分与归因依据。"
        />
        <FeatureItem
          icon="wave"
          title="反事实路径推演"
          text="模拟 A/B 分支与最佳干预窗口，定位关键转折点。"
        />
        <FeatureItem
          icon="check"
          title="基线方法对比"
          text="多项关键指标（FPA / ATA / CPA 等）量化评估。"
        />
      </section>
    </div>
  )
}

function FeatureItem({ icon, title, text }) {
  return (
    <div className="card p-5">
      <div className="w-9 h-9 rounded-md bg-slate-100 text-ink-500 flex items-center justify-center mb-3">
        <Icon name={icon} className="w-4 h-4" />
      </div>
      <div className="text-sm font-semibold text-ink-900 mb-1">{title}</div>
      <div className="text-xs text-ink-500 leading-relaxed">{text}</div>
    </div>
  )
}
