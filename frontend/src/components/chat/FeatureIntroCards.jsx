import { THEME_CLASSES } from '../../scenarios/config'
import Icon from '../Icon'

export const FEATURE_CARDS = [
  {
    key: 'risk_profile',
    icon: 'shield',
    title: '场景识别与风险画像',
    summary: '从一句话或一份材料里找出场景线索，再形成可解释的风险画像。',
    detail: '输入内容 → 场景判断 → 认知画像 → 风险分数与干预建议。适合回答「这是不是诈骗、风险从哪来」。',
    color: 'brand',
  },
  {
    key: 'counterfactual',
    icon: 'wave',
    title: '个体反事实对照',
    summary: '比较继续走和及时止损两条 6 步路径，并对齐后面星图该在哪一跳介入。',
    detail: '风险线索 → 两条分支 → 影响最小 vs ΔR 最大。适合回答「现在拦还是不拦、拦在哪」。',
    color: 'leaf',
  },
  {
    key: 'propagation_graph',
    icon: 'network',
    title: '传播关系图',
    summary: '从左到右看话题怎么传：源头、第一跳、扩散、更远接收。对照六步会压到这四列上。',
    detail: '舆情约 50、事件约 60 个代理。箭头指向谁，就是信息流向谁。适合回答「这件事是怎么传开的」。',
    color: 'sand',
  },
]

export default function FeatureIntroCards({ onFeature }) {
  return (
    <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-3">
      {FEATURE_CARDS.map((feature) => {
        const theme = THEME_CLASSES[feature.color]
        return (
          <button
            key={feature.key}
            type="button"
            onClick={() => onFeature(feature)}
            className={`group relative overflow-hidden text-left rounded-3xl border ${theme.border} bg-white p-4 transition-all duration-300 hover:-translate-y-1 hover:shadow-cardHover`}
          >
            <div className={`absolute -right-8 -top-10 w-28 h-28 rounded-full ${theme.bg} opacity-70 blur-xl transition-opacity group-hover:opacity-100`} />
            <div className={`relative w-10 h-10 rounded-2xl ${theme.bg} ${theme.accent} flex items-center justify-center`}>
              <Icon name={feature.icon} className="w-5 h-5" />
            </div>
            <div className="relative mt-3 text-sm font-semibold text-ink-900">{feature.title}</div>
            <div className="relative mt-1.5 text-xs text-ink-500 leading-relaxed">{feature.summary}</div>
            <div className="relative mt-0 max-h-0 overflow-hidden opacity-0 text-xs text-ink-900 leading-relaxed transition-all duration-300 group-hover:max-h-32 group-hover:mt-3 group-hover:opacity-100">
              {feature.detail}
            </div>
            <div className={`relative mt-3 flex items-center text-xs font-medium ${theme.accent}`}>
              查看结构图
              <Icon name="arrow-right" className="w-3.5 h-3.5 ml-1 transition-transform group-hover:translate-x-1" />
            </div>
          </button>
        )
      })}
    </div>
  )
}
