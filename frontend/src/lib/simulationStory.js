import { inspectFork, inspectPropagation } from './forkGraph'
import { summarizeSteps } from './humanizeSim'
import { buildCounterfactualExplain, collectPrescriptions } from './counterfactualExplain'

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function unique(list) {
  return [...new Set(list.filter(Boolean))]
}

function joinNames(list) {
  const names = unique(list).slice(0, 4)
  if (!names.length) return ''
  if (names.length === 1) return names[0]
  return `${names.slice(0, -1).join('、')}和${names[names.length - 1]}`
}

const HOP_CAPTIONS = ['源头', '第一跳', '扩散', '更远接收']

function hopNames(nodes) {
  const buckets = [[], [], [], []]
  asArray(nodes).forEach((node) => {
    const hop = Number(node?.hop)
    if (!Number.isFinite(hop)) return
    buckets[Math.min(3, Math.max(0, hop))].push(node.label)
  })
  return buckets.map((list) => unique(list))
}

function stripForkStepPhrase(text) {
  return String(text || '')
    .replace(/在第\s*\d+\s*步/g, '')
    .replace(/第\s*\d+\s*步/g, '')
    .replace(/[，,]\s*[，,]/g, '，')
    .replace(/\s+/g, ' ')
    .trim()
}

function interventionHop(analysis) {
  const effective = asObject(analysis?.effectiveIntervention)
  const proxy = asObject(analysis?.proxySelection)
  const stage = String(effective.target_stage || proxy.target_stage || '').toLowerCase()
  const tick = Number(effective.intervention_tick ?? proxy.intervention_tick)
  if (stage.includes('peak') || stage.includes('accel')) return 2
  if (stage.includes('early')) return 1
  if (Number.isFinite(tick) && tick > 0) {
    if (tick <= 1) return 0
    if (tick === 2) return 1
    return 2
  }
  return 1
}

function resolveInterveneAt(analysis, featureKey, graph) {
  const hops = hopNames(graph?.nodes)
  const effective = asObject(analysis?.effectiveIntervention)
  const proxy = asObject(analysis?.proxySelection)
  const action = stripForkStepPhrase(
    effective.message
    || proxy.message
    || effective.best_intervention_action
    || proxy.best_intervention_action
    || '',
  )
  if (featureKey === 'counterfactual') {
    const window = asObject(
      analysis?.fork_comparison?.best_intervention_window
      || analysis?.counterfactual_report?.best_intervention_window,
    )
    const step = Number(window.open_step)
    return {
      clock: 'fork_step',
      hop: null,
      hop_name: '分叉后尽早核验',
      nodes: '',
      action: action || '停下来核验、求助或拒绝',
      fork_open_step: Number.isFinite(step) ? step : null,
    }
  }
  const hop = interventionHop(analysis)
  const names = hops[hop]?.length ? hops[hop] : (hops[1].length ? hops[1] : hops[0])
  return {
    clock: 'propagation_hop',
    hop,
    hop_name: HOP_CAPTIONS[hop] || '第一跳',
    nodes: joinNames(names),
    action: action || (hop <= 1 ? '注入核实信息和官方澄清' : '降权、通报并切断继续扩散'),
    tick: Number(effective.intervention_tick ?? proxy.intervention_tick) || null,
    stage: String(effective.target_stage || proxy.target_stage || 'early'),
  }
}

function edgeSentences(graph, limit = 4) {
  const nodes = asArray(graph?.nodes)
  const labelById = new Map(nodes.map((node) => [String(node.id), node.label]))
  return asArray(graph?.edges)
    .map((edge) => {
      const from = labelById.get(String(edge.source)) || ''
      const to = labelById.get(String(edge.target)) || ''
      const verb = String(edge.relation || '').trim()
      if (!from || !to || !verb) return ''
      if (/信息流|关系|影响/.test(verb)) return `${from}把内容传给${to}`
      return `${from}向${to}${verb}`
    })
    .filter(Boolean)
    .slice(0, limit)
}

function forkText(analysis) {
  const fork = inspectFork(analysis)
  const report = asObject(analysis?.counterfactual_report || analysis?.fork_comparison)
  return {
    ran: fork.ran,
    attack: String(report.summary_branch_a || summarizeSteps(fork.branchA) || '').trim(),
    defense: String(report.summary_branch_b || summarizeSteps(fork.branchB) || '').trim(),
  }
}

function hopGuideFromExplain(explain) {
  if (!explain?.steps?.length) return null
  return {
    title: explain.isPropagation ? '六步推演怎么对齐这张星图' : '六步推演对应对照星图的哪一段',
    lead: explain.bridge,
    prefer: explain.recommended.prefer,
    minImpact: explain.recommended.minImpactWhy,
    maxGain: explain.recommended.maxGainWhy,
    rows: explain.steps.map((item) => ({
      step: item.step,
      where: item.people ? `${item.hopName} · ${item.people}` : item.hopName,
      ifIntervene: item.ifInterveneHere,
    })),
  }
}

function clipEvent(text, limit = 72) {
  const raw = String(text || '').replace(/\s+/g, ' ').trim()
  if (!raw) return ''
  return raw.length > limit ? `${raw.slice(0, limit)}…` : raw
}

function prescriptionStory(analysis) {
  const items = collectPrescriptions(analysis).slice(0, 4).map((item) => {
    const actions = asArray(item?.recommended_actions).map((entry) => String(entry || '').trim()).filter(Boolean)
    return {
      title: String(item?.title || item?.action || '').trim() || '干预动作',
      rationale: String(item?.rationale || '').trim(),
      actions,
      expected: String(item?.expected_effect || '').trim(),
    }
  })
  if (!items.length) return null
  return {
    title: '干预处方',
    lead: '下面是这次材料可执行的动作，不是「已存档」提示。',
    items,
  }
}

export function buildStorySnapshot(analysis, featureKey, graph, inputText = '') {
  const nodes = asArray(graph?.nodes)
  const labelById = new Map(nodes.map((node) => [String(node.id), node.label]))
  const fork = forkText(analysis)
  const interventions = asArray(analysis?.intervention_prescriptions)
    .map((item) => stripForkStepPhrase(item?.title || item?.action || item?.label || (typeof item === 'string' ? item : '')))
    .filter(Boolean)
  const inspected = inspectPropagation(analysis)
  const interveneAt = resolveInterveneAt(analysis, featureKey, graph)
  return {
    scenario: analysis?.scenario || analysis?.scenario_type || '',
    feature_key: featureKey,
    input_text: String(inputText || '').slice(0, 2800),
    agent_count: analysis?.agentCount || inspected.graph?.agent_count || nodes.length,
    sim_note: inspected.ran ? inspected.reason : (fork.ran ? '本次有对照路径日志。' : ''),
    attack_summary: fork.attack,
    defense_summary: fork.defense,
    interventions,
    intervene_at: interveneAt,
    hop_guide: hopGuideFromExplain(buildCounterfactualExplain(analysis, inputText)),
    nodes: nodes.slice(0, 22).map((node) => ({
      label: node.label,
      hop: node.hop,
      role: node.role || node.type || '',
      place: node.place || node.source || '',
      action: node.behaviors?.[0]?.action || '',
      content: node.behaviors?.[0]?.content || '',
    })),
    edges: asArray(graph?.edges).slice(0, 22).map((edge) => ({
      from: labelById.get(String(edge.source)) || edge.source,
      to: labelById.get(String(edge.target)) || edge.target,
      relation: edge.relation || '',
    })),
  }
}

export function buildSimulationStory(analysis, featureKey, graph, inputText = '') {
  if (featureKey === 'propagation_graph') return buildPropagationStory(analysis, graph, inputText)
  if (featureKey === 'risk_profile') return buildProfileStory(analysis, inputText)
  return buildFraudStory(analysis, graph, inputText)
}

function buildPropagationStory(analysis, graph, inputText = '') {
  const hops = hopNames(graph?.nodes)
  const sources = joinNames(hops[0]) || '源头账号'
  const firstHop = joinNames(hops[1]) || '意见领袖或媒体'
  const spread = joinNames(hops[2]) || '同群和普通受众'
  const farther = joinNames(hops[3]) || '官方或外围观察者'
  const links = edgeSentences(graph, 6)
  const inspected = inspectPropagation(analysis)
  const count = graph?.nodes?.length || inspected.nodes?.length || 0
  const scene = /event/i.test(String(analysis?.scenario || analysis?.scenario_type || '')) ? '事件' : '舆论'
  const eventBit = clipEvent(inputText)
  const eventLead = eventBit
    ? `这次${scene}针对的是：${eventBit}`
    : `这次${scene}模拟从「${sources}」发出。`
  const peopleBody = [
    eventLead,
    `第一跳主要是「${firstHop}」接到后转发、报道或讨论；随后「${spread}」继续扩散，更外围出现「${farther}」。`,
    links.length ? `仿真里能核对的往来包括：${links.join('；')}。` : '点开图上的人，可以核对他是转发、澄清、通报还是只是接到内容。',
  ].join('\n\n')
  const explain = buildCounterfactualExplain(analysis, inputText)
  const at = resolveInterveneAt(analysis, 'propagation_graph', graph)
  const where = at.nodes ? `「${at.hop_name}」的「${at.nodes}」` : `「${at.hop_name}」`
  const interveneHow = at.action || '注入核实信息和官方澄清'
  return {
    sceneLabel: `${scene}传播`,
    people: {
      title: '这次事件里谁把内容传给了谁',
      body: peopleBody,
    },
    futures: {
      title: '这件事接下来可能怎么走',
      lead: count ? `图上约 ${count} 个角色。下面两条从同一起点出发，是预测而不是已经发生的事。` : '下面两条从同一起点出发，是预测而不是已经发生的事。',
      items: [
        {
          label: '预测一',
          title: '继续扩散',
          body: explain.continueStory,
        },
        {
          label: '预测二',
          title: '澄清或处置介入',
          body: `若在${where}介入，${interveneHow}。${explain.recommended.minImpactWhy} ${explain.recommended.prefer}`,
        },
      ],
    },
    hopGuide: hopGuideFromExplain(explain),
    prescriptions: prescriptionStory(analysis),
  }
}

function buildFraudStory(analysis, graph, inputText = '') {
  const fork = forkText(analysis)
  const peopleNodes = asArray(graph?.nodes).filter((node) => /施害|受害|家人|核验|警方|银行/.test(`${node.label}${node.who || ''}`))
  const names = joinNames(peopleNodes.map((node) => node.label)) || '施害者和受害人'
  const eventBit = clipEvent(inputText)
  const peopleBody = [
    eventBit ? `这段对话的核心是：${eventBit}` : `对照从分叉点分成两侧，人物主线是${names}。`,
    fork.ran
      ? `施害者沿「继续被诱导」催促、改口或要验证码；受害人若转向「及时止损」，会停下来核验、求助或拒绝。这不是说当事人已经选了哪一边。`
      : `先分清谁在施压、谁可能被诱导、身边谁能帮忙核验。`,
  ].join('\n\n')
  const explain = buildCounterfactualExplain(analysis, inputText)
  return {
    sceneLabel: '诈骗对照',
    people: {
      title: '这次对话里谁在对谁做什么',
      body: peopleBody,
    },
    futures: {
      title: '两条路分别会走到哪',
      lead: '预测一、预测二从同一个分叉点出发，比较后续风险，不是两件已经发生的事。',
      items: [
        {
          label: '预测一',
          title: '继续被诱导',
          body: explain.continueStory,
        },
        {
          label: '预测二',
          title: '及时止损',
          body: `${explain.stoplossStory} ${explain.recommended.prefer}`,
        },
      ],
    },
    hopGuide: hopGuideFromExplain(explain),
    prescriptions: prescriptionStory(analysis),
  }
}

function buildProfileStory(analysis, inputText = '') {
  const message = String(analysis?.assistantMessage || analysis?.assistant_message || '').trim()
  const eventBit = clipEvent(inputText, 100)
  return {
    sceneLabel: '风险画像',
    people: {
      title: '材料里出现了哪些角色',
      body: [
        eventBit ? `这份材料说的是：${eventBit}` : '输入材料会被整理成场景线索。',
        message ? message.slice(0, 280) : '再解释情绪、保护习惯和权威服从等脆弱点，最后给出风险分数和下一步动作。',
      ].join('\n\n'),
    },
    futures: {
      title: '两种读法会导向什么',
      lead: '同一份材料，核对方式和不核对，后面的判断会分开。',
      items: [
        {
          label: '预测一',
          title: '只跟情绪走',
          body: '如果只抓住最刺激的一句，不核验证据和对方身份，风险会被放大或判错，干预也容易踩空。',
        },
        {
          label: '预测二',
          title: '按线索再给建议',
          body: analysis?.mostImportantAction
            ? `先核对能站住的证据，再执行：${analysis.mostImportantAction}`
            : '先核验证据、身份和时限，再给出核验、求助或暂停等建议，干预会更贴这次材料。',
        },
      ],
    },
    prescriptions: prescriptionStory(analysis),
  }
}
