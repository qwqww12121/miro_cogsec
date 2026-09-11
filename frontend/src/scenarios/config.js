export const SCENARIOS = {
  fraud_im: {
    key: 'fraud_im',
    name: '诈骗即时通讯',
    short: 'Fraud · IM',
    description: '识别即时通讯中的诈骗话术、认知操纵与受害人脆弱度。',
    theme: 'brand',
    icon: 'shield',
    path: '/scenario/fraud-im',
  },
  public_opinion: {
    key: 'public_opinion',
    name: '舆情分析',
    short: 'Public Opinion',
    description: '量化话题情绪极化、关键意见领袖与异常账号集群。',
    theme: 'leaf',
    icon: 'wave',
    path: '/scenario/public-opinion',
  },
  event_propagation: {
    key: 'event_propagation',
    name: '事件传播分析',
    short: 'Event Propagation',
    description: '复现事件在社群网络中的逐层扩散与关键路径。',
    theme: 'sand',
    icon: 'network',
    path: '/scenario/event-propagation',
  },
}

export const SCENARIO_LIST = [
  SCENARIOS.fraud_im,
  SCENARIOS.public_opinion,
  SCENARIOS.event_propagation,
]

export function scenarioDisplayName(key) {
  const id = String(key || '').trim()
  if (!id || id === 'unknown') return ''
  return SCENARIOS[id]?.name || SCENARIOS[id.replace(/-/g, '_')]?.name || ''
}

export const THEME_CLASSES = {
  brand: {
    ring: 'ring-brand/20',
    accent: 'text-brand',
    bg: 'bg-brand-50',
    border: 'border-brand-100',
    chip: 'bg-brand-50 text-brand-600',
    bar: '#4a90d9',
  },
  leaf: {
    ring: 'ring-leaf/20',
    accent: 'text-leaf',
    bg: 'bg-leaf-50',
    border: 'border-leaf-100',
    chip: 'bg-leaf-50 text-leaf-600',
    bar: '#52a882',
  },
  sand: {
    ring: 'ring-sand/20',
    accent: 'text-sand',
    bg: 'bg-sand-50',
    border: 'border-sand-100',
    chip: 'bg-sand-50 text-sand-600',
    bar: '#e8b84b',
  },
}
