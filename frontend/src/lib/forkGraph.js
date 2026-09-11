import { describeInteraction, humanizeAction, humanizeActor, summarizeSteps } from './humanizeSim'
import { chineseAgentLabel, resolveAgentPersona } from './agentPersona'

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

const ACTOR_LABEL = {
  threat_actor: '施害者智能体',
  user_twin: '受害人孪生',
  verifier: '核验智能体',
  A: '攻击路径 A',
  B: '防御路径 B',
}

export function inspectFork(analysis) {
  if (!analysis) {
    return {
      ran: false,
      skipped: true,
      stage: 'none',
      reason: '还没有分析材料。',
    }
  }
  const classified = asObject(analysis.fork_status)
  if (classified.ran === false || classified.stage === 'classify_only') {
    return {
      ran: false,
      skipped: true,
      stage: 'classify_only',
      reason: classified.reason || '对话层只做场景识别。',
    }
  }
  const components = asObject(analysis.runtimeComponents || analysis.runtime_components)
  const branchA = asArray(analysis.branch_a_log || analysis.legacy?.branchA)
  const branchB = asArray(analysis.branch_b_log || analysis.legacy?.branchB)
  const fork = asObject(analysis.fork_comparison || analysis.forkComparison)
  const traces = asArray(asObject(analysis.fraud_interaction).interaction_trace)
  const skipLike = (step) => {
    const action = String(step?.action || step?.action_type || '')
    const stage = String(step?.world_state?.stage || '')
    return /skip/i.test(action) || stage === 'skipped'
  }
  if (components.fork === 'skipped' || (branchA.length > 0 && branchA.every(skipLike))) {
    return {
      ran: false,
      skipped: true,
      stage: 'scenario',
      reason: '本次场景分析没有对照路径日志。',
    }
  }
  const ran = components.fork === 'complete' || components.fork === 'degraded' || branchA.length > 0
  if (!ran) {
    return {
      ran: false,
      skipped: true,
      stage: 'scenario',
      reason: '本次没有生成对照路径。',
    }
  }
  return {
    ran: true,
    skipped: false,
    stage: 'scenario',
    reason: '',
    branchA,
    branchB,
    traces,
    fork,
  }
}

export function graphFromFork(analysis) {
  const fork = inspectFork(analysis)
  if (!fork.ran) return null
  const attackLabel = summarizeSteps(fork.branchA) || '继续按对方节奏走'
  const defenseLabel = summarizeSteps(fork.branchB) || '核验、求助、拒绝'
  const attackBehaviors = stepsToBehaviors(fork.branchA, '施害者', '受害人')
  const defenseBehaviors = stepsToBehaviors(fork.branchB, '受害人', '施害者')
  const talkBehaviors = (fork.traces || []).map((item) => ({
    time: item.round != null ? `第 ${item.round} 轮` : '',
    actor: ACTOR_LABEL[item.actor_id] || item.actor_id || '角色',
    target: ACTOR_LABEL[item.target_actor_id] || item.target_actor_id || '对方',
    action: '发言',
    content: humanizeAction(item.action) || item.action || '',
  })).filter((item) => item.content)
  const attackerTalk = talkBehaviors.filter((item) => /施害|threat/.test(`${item.actor}${item.target}`))
  const victimTalk = talkBehaviors.filter((item) => /受害|核验|twin|verifier/.test(`${item.actor}${item.target}`))
  const nodes = [
    {
      id: 'fork',
      label: '① 分叉点',
      desc: '对照从这里分成两条路',
      detail: '不是传播网络里的人。它标记：接下来分别模拟「继续被诱导」和「及时止损」。',
      place: '对照路径 · 分叉',
      who: '这不是某个人。汉语名称「分叉点」对应对照开始的位置：接下来分别模拟两种选择。',
      kind: 'input',
      source: '对照路径',
      lane: 'shared',
      group: 'fork',
      order: 1,
      x: 450,
      y: 72,
      behaviors: [
        { time: '分叉', action: '开始对照', content: '分别模拟「继续被诱导」和「及时止损」', target: '' },
        attackBehaviors[0],
        defenseBehaviors[0],
      ].filter(Boolean),
    },
    {
      id: 'attacker',
      label: '② 施害者',
      desc: attackBehaviors[0]?.content || '攻击侧继续施压',
      detail: '对方会改口、要验证码、催转账。这条列只描述攻击侧在做什么。',
      place: '对照路径 · 继续被诱导',
      who: '汉语名称「施害者」对应继续施压的对方，代表诈骗里的攻击这一侧。',
      kind: 'risk',
      source: '对照路径 · 继续被诱导',
      lane: 'attack',
      group: 'attack',
      order: 2,
      x: 200,
      y: 200,
      behaviors: mergeBehaviors(attackBehaviors, attackerTalk),
    },
    {
      id: 'victim',
      label: '② 受害人',
      desc: defenseBehaviors[0]?.content || '防御侧开始核验',
      detail: '及时止损这一侧：停下来、核实来电身份、不发验证码。',
      place: '对照路径 · 及时止损',
      who: '汉语名称「受害人」对应被诱导的当事人，代表需要保护的这一侧。',
      kind: 'profile',
      source: '对照路径 · 及时止损',
      lane: 'defense',
      group: 'defense',
      order: 2,
      x: 700,
      y: 200,
      behaviors: mergeBehaviors(defenseBehaviors, victimTalk),
    },
    {
      id: 'pathA',
      label: '③ 攻击路径',
      desc: attackLabel,
      detail: '如果继续被诱导，风险会沿这条路累积。',
      place: '对照路径 · 继续被诱导',
      who: '这不是某个人。汉语名称「攻击路径」对应「继续被诱导」这一整条路上的行为。',
      kind: 'risk',
      source: '对照路径 · 继续被诱导',
      lane: 'attack',
      group: 'attack',
      order: 3,
      x: 200,
      y: 340,
      behaviors: attackBehaviors,
    },
    {
      id: 'pathB',
      label: '③ 防御路径',
      desc: defenseLabel,
      detail: '如果及时止损，局面沿这条路转向安全。',
      place: '对照路径 · 及时止损',
      who: '这不是某个人。汉语名称「防御路径」对应「及时止损」这一整条路上的行为。',
      kind: 'action',
      source: '对照路径 · 及时止损',
      lane: 'defense',
      group: 'defense',
      order: 3,
      x: 700,
      y: 340,
      behaviors: defenseBehaviors,
    },
    {
      id: 'turn',
      label: '④ 转折点',
      desc: '两条路在这里比出差异',
      detail: '干预越早，不可逆操作越少。这是对照结果，不是又分出一条新路。',
      place: '对照路径 · 比较',
      who: '这不是某个人。汉语名称「转折点」对应两条路比完之后的差异。',
      kind: 'result',
      source: '对照路径',
      lane: 'shared',
      group: 'turn',
      order: 4,
      x: 450,
      y: 470,
      behaviors: [
        attackBehaviors[attackBehaviors.length - 1],
        defenseBehaviors[defenseBehaviors.length - 1],
        {
          time: '比较',
          action: '对照结果',
          content: '左列风险累积，右列风险下降。干预越早，不可逆操作越少。',
          target: '',
        },
      ].filter(Boolean),
    },
  ]
  const edges = [
    { source: 'fork', target: 'attacker', relation: '左：继续被诱导' },
    { source: 'fork', target: 'victim', relation: '右：及时止损' },
    { source: 'attacker', target: 'pathA', relation: '接着施压' },
    { source: 'victim', target: 'pathB', relation: '接着核验' },
    { source: 'pathA', target: 'turn', relation: '风险累积' },
    { source: 'pathB', target: 'turn', relation: '风险下降' },
  ]
  const labelById = Object.fromEntries(nodes.map((node) => [node.id, node.label]))
  nodes.forEach((node) => {
    node.relations = edges.flatMap((edge) => {
      if (edge.source === node.id) return [{ direction: 'to', relation: edge.relation, other: labelById[edge.target] }]
      if (edge.target === node.id) return [{ direction: 'from', relation: edge.relation, other: labelById[edge.source] }]
      return []
    })
  })
  return { nodes, edges, directed: true, source: 'fork', layout: 'sequential' }
}

function stepsToBehaviors(steps, actor, target) {
  return asArray(steps).map((step, index) => ({
    time: `第 ${index + 1} 步`,
    actor,
    target,
    action: humanizeAction(step.action_type || '行动'),
    content: humanizeAction(step.action) || String(step.action || ''),
  })).filter((item) => item.action || item.content)
}

function mergeBehaviors(...lists) {
  const seen = new Set()
  const merged = []
  lists.flat().forEach((item) => {
    if (!item) return
    const key = `${item.time || ''}|${item.action || ''}|${item.target || ''}|${item.content || ''}`
    if (seen.has(key)) return
    seen.add(key)
    merged.push(item)
  })
  return merged.slice(0, 8)
}

export function buildAgentTrace(analysis) {
  const existing = asArray(analysis?.agent_trace)
  if (existing.length) {
    return existing
      .filter((event) => !event?.skipped)
      .map((event) => ({
        ...event,
        actor: humanizeActor(event.actor),
        target: event.target === '世界状态' ? '推演中的局面' : humanizeActor(event.target),
        action: humanizeAction(event.action),
        content: humanizeAction(event.content) || event.content,
      }))
  }
  const fork = inspectFork(analysis)
  const events = []
  ;(fork.branchA || []).forEach((step, index) => {
    events.push({
      time: `A-${index + 1}`,
      actor: '攻击路径',
      target: '推演中的局面',
      action: humanizeAction(step.action_type || '推进'),
      content: humanizeAction(step.action) || step.action || '',
      amplify: step.irreversible ? '不可逆' : '',
    })
  })
  ;(fork.branchB || []).forEach((step, index) => {
    events.push({
      time: `B-${index + 1}`,
      actor: '防御路径',
      target: '推演中的局面',
      action: humanizeAction(step.action_type || '干预'),
      content: humanizeAction(step.action) || step.action || '',
      amplify: '',
    })
  })
  ;(fork.traces || []).forEach((item) => {
    events.push({
      time: `R${item.round ?? ''}`,
      actor: ACTOR_LABEL[item.actor_id] || item.actor_id || '角色',
      target: ACTOR_LABEL[item.target_actor_id] || item.target_actor_id || '对方',
      action: '发言',
      content: humanizeAction(item.action) || item.action || '',
      amplify: '',
    })
  })
  return events
}

export function inspectPropagation(analysis) {
  const extension = asObject(analysis?.scenario_extension)
  const payload = asObject(analysis?.graphPayload || analysis?.graph_payload)
  const graph = asObject(
    analysis?.propagationGraph
    || analysis?.propagation_graph
    || extension.propagation_graph
    || ((payload.source === 'lightweight_propagation' || payload.engine === 'social_state' || payload.source === 'oasis')
      ? payload
      : {}),
  )
  const nodes = asArray(graph.nodes)
  const edges = asArray(graph.edges || graph.links)
  if (nodes.length < 2) {
    return {
      ran: false,
      reason: '本次没有生成传播关系图。',
    }
  }
  const oasis = graph.source === 'oasis' || graph.engine === 'oasis'
  return {
    ran: true,
    oasis,
    source: oasis ? 'oasis' : 'lightweight_propagation',
    reason: oasis
      ? `节点来自本次传播仿真（约 ${graph.agent_count || nodes.length} 个代理）。`
      : `节点来自传播仿真（约 ${graph.agent_count || nodes.length} 个代理）。`,
    graph,
    nodes,
    edges,
  }
}

export const LAYER_X = [110, 320, 540, 760]
const HOP_CAPTION = ['源头', '第一跳', '扩散', '更远接收']

export function nodeStepGroup(node) {
  if (node?.group) return node.group
  if (Number.isFinite(Number(node?.hop))) return `hop-${Number(node.hop)}`
  const id = String(node?.id || '')
  if (id === 'fork') return 'fork'
  if (id === 'turn' || id === 'gap') return 'turn'
  if (node?.lane === 'attack' || ['attacker', 'pathA', 'attack', 'strategy'].includes(id)) return 'attack'
  if (node?.lane === 'defense' || ['victim', 'pathB', 'defense', 'intervention'].includes(id)) return 'defense'
  if (['input', 'signals', 'cognition'].includes(id)) return id
  if (['risk', 'action'].includes(id)) return 'output'
  return ''
}

const HOP_DETAIL = [
  '话题从这里发出。不是对照路径里的分叉点，而是传播网的起点。',
  '最先接到内容、最容易放大的人，例如意见领袖或媒体。',
  '同群、师生、好友之间继续扩散。',
  '旁观、官方或更外围的人，信息到这里已经过了几跳。',
]

function roleHopHint(node) {
  const text = `${node.label || ''} ${node.desc || ''} ${node.role || ''} ${node.type || ''} ${node.id || ''}`.toLowerCase()
  if (/(source|origin|seed|spreader|源头)/.test(text)) return 0
  if (/(kol|media|amplif|记者|媒体|意见领袖)/.test(text)) return 1
  if (/(official|observer|旁观|官方|处置)/.test(text)) return 3
  return null
}

function layoutPropagationLayers(nodes, edges) {
  const ids = nodes.map((node) => node.id)
  const idSet = new Set(ids)
  const incoming = new Map(ids.map((id) => [id, 0]))
  const outgoing = new Map(ids.map((id) => [id, []]))
  edges.forEach((edge) => {
    if (!idSet.has(edge.source) || !idSet.has(edge.target) || edge.source === edge.target) return
    incoming.set(edge.target, (incoming.get(edge.target) || 0) + 1)
    outgoing.get(edge.source)?.push(edge.target)
  })
  let roots = ids.filter((id) => (incoming.get(id) || 0) === 0)
  if (!roots.length) {
    roots = [...ids].sort((a, b) => (outgoing.get(b)?.length || 0) - (outgoing.get(a)?.length || 0)).slice(0, 1)
  }
  const hop = new Map()
  const queue = [...roots]
  roots.forEach((id) => hop.set(id, 0))
  while (queue.length) {
    const current = queue.shift()
    const depth = hop.get(current) || 0
    ;(outgoing.get(current) || []).forEach((next) => {
      if (hop.has(next)) return
      hop.set(next, depth + 1)
      queue.push(next)
    })
  }
  const layers = [[], [], [], []]
  nodes.forEach((node) => {
    if (hop.has(node.id)) {
      layers[Math.min(hop.get(node.id) || 0, 3)].push(node)
      return
    }
    const hinted = roleHopHint(node)
    layers[hinted != null ? hinted : 2].push(node)
  })
  rebalancePropagationLayers(layers, (id) => outgoing.get(id)?.length || 0)

  const yTop = 78
  const yBottom = 470
  const placed = []
  layers.forEach((siblings, layer) => {
    const count = siblings.length
    siblings.forEach((node, index) => {
      let x = LAYER_X[layer]
      let y = count === 1 ? (yTop + yBottom) / 2 : yTop + (index / Math.max(1, count - 1)) * (yBottom - yTop)
      if (count > 6) {
        const cols = count > 12 ? 3 : 2
        const col = index % cols
        const row = Math.floor(index / cols)
        const rows = Math.ceil(count / cols)
        x = LAYER_X[layer] + (col - (cols - 1) / 2) * 46
        y = rows === 1 ? (yTop + yBottom) / 2 : yTop + (row / Math.max(1, rows - 1)) * (yBottom - yTop)
      }
      placed.push({
        ...node,
        hop: layer,
        group: `hop-${layer}`,
        place: `传播仿真 · ${HOP_CAPTION[layer]}`,
        x,
        y,
        source: `传播仿真 · ${HOP_CAPTION[layer]}`,
        detail: node.detail || HOP_DETAIL[layer],
      })
    })
  })
  return placed
}

function rebalancePropagationLayers(layers, outCount) {
  const total = layers.reduce((sum, list) => sum + list.length, 0)
  if (total < 8) return
  const rest = Math.max(1, total - layers[0].length)
  const target = Math.max(4, Math.ceil(rest / 3))
  for (let i = 1; i < 3; i += 1) {
    layers[i].sort((a, b) => outCount(b.id) - outCount(a.id))
    while (layers[i].length > target) {
      layers[i + 1].unshift(layers[i].pop())
    }
    if (layers[i + 1].length === 0 && layers[i].length > 3) {
      const move = Math.floor(layers[i].length / 2)
      layers[i + 1].push(...layers[i].splice(layers[i].length - move, move))
    }
  }
}

export function graphFromPropagation(analysis) {
  const inspected = inspectPropagation(analysis)
  if (!inspected.ran) return null
  const simActions = collectPropagationActions(analysis)
  const rawNodes = inspected.nodes.slice(0, 28).map((node, index) => {
    const persona = resolveAgentPersona(node)
    return {
      id: String(node.id ?? node.node_id ?? node.name ?? index),
      label: persona.label || chineseAgentLabel(node.label ?? node.name ?? node.id ?? `节点 ${index + 1}`),
      desc: '',
      role: node.role || node.type || persona.role || '',
      type: node.type || node.role || '',
      kind: node.kind || (index % 3 === 0 ? 'evidence' : 'profile'),
      behaviorHint: String(node.behavior_hint || node.behaviorHint || ''),
      who: persona.who,
      stance: node.stance || '',
      influence: node.influence,
      activity: node.activity,
      behaviors: asArray(node.behaviors),
    }
  })
  const idSet = new Set(rawNodes.map((node) => node.id))
  const nodeById = new Map(rawNodes.map((node) => [node.id, node]))
  const edges = inspected.edges.slice(0, 60)
    .map((edge) => {
      const sourceId = String(edge.source ?? edge.from ?? '')
      const targetId = String(edge.target ?? edge.to ?? '')
      const source = nodeById.get(sourceId)
      const target = nodeById.get(targetId)
      const { verb } = describeInteraction(source || sourceId, target || targetId, edge.relation ?? edge.label ?? edge.type)
      return {
        source: sourceId,
        target: targetId,
        relation: verb,
      }
    })
    .filter((edge) => idSet.has(edge.source) && idSet.has(edge.target) && edge.source !== edge.target)
  const labelById = new Map(rawNodes.map((node) => [node.id, node.label]))
  const withActions = rawNodes.map((node) => {
    const fromSim = behaviorsFromActions(node.id, simActions, nodeById, labelById)
    const fromEdges = (fromSim.length || asArray(node.behaviors).length)
      ? []
      : behaviorsFromEdges(node.id, edges, nodeById, labelById)
    const behaviors = rewriteBehaviors(mergeBehaviors(node.behaviors, fromSim, fromEdges), node, nodeById)
    const relations = relationsFromEdges(node.id, edges, nodeById, labelById)
    return {
      ...node,
      behaviors,
      relations,
      desc: '',
      who: node.who,
    }
  })
  const nodes = layoutPropagationLayers(withActions, edges)
  return { nodes, edges, directed: true, source: inspected.source, layout: 'layered' }
}

function collectPropagationActions(analysis) {
  const extension = asObject(analysis?.scenario_extension)
  const propagation = asObject(analysis?.propagation || extension.propagation_normalized || extension.propagation)
  const branchA = asObject(propagation.branch_a)
  const fromPath = asArray(propagation.propagation_path)
  const fromBranch = asArray(branchA.actions)
  const fromGraph = asArray(asObject(analysis?.propagationGraph || analysis?.propagation_graph).actions)
  return (fromPath.length ? fromPath : (fromBranch.length ? fromBranch : fromGraph)).slice(0, 400)
}

function behaviorsFromActions(nodeId, actions, nodeById, labelById) {
  const items = []
  asArray(actions).forEach((action) => {
    const sourceId = String(action.source_agent_id || action.source || '')
    const targetId = String(action.target_agent_id || action.target || '')
    const kind = String(action.action_type || action.type || action.kind || '')
    const tick = action.tick ?? action.step ?? ''
    const time = tick !== '' ? `第 ${tick} 步` : ''
    const source = nodeById.get(sourceId)
    const target = nodeById.get(targetId)
    const sourceLabel = source?.label || chineseAgentLabel(labelById.get(sourceId) || sourceId)
    const targetLabel = target?.label || chineseAgentLabel(labelById.get(targetId) || targetId)
    const { verb, toContent, fromContent } = describeInteraction(source || sourceLabel, target || targetLabel, '', kind)
    if (sourceId === nodeId) {
      items.push({
        time,
        action: verb,
        target: targetLabel,
        content: toContent,
      })
    } else if (targetId === nodeId) {
      items.push({
        time,
        action: verb,
        target: sourceLabel,
        content: fromContent,
      })
    }
  })
  return items.slice(0, 8)
}

function behaviorsFromEdges(nodeId, edges, nodeById, labelById) {
  return asArray(edges).flatMap((edge) => {
    const source = nodeById.get(edge.source)
    const target = nodeById.get(edge.target)
    const { verb, toContent, fromContent } = describeInteraction(source, target, edge.relation)
    if (edge.source === nodeId) {
      const other = target?.label || labelById.get(edge.target) || edge.target
      return [{ time: '', action: verb, target: other, content: toContent }]
    }
    if (edge.target === nodeId) {
      const other = source?.label || labelById.get(edge.source) || edge.source
      return [{ time: '', action: verb, target: other, content: fromContent }]
    }
    return []
  }).slice(0, 6)
}

function relationsFromEdges(nodeId, edges, nodeById, labelById) {
  return asArray(edges).flatMap((edge) => {
    const source = nodeById.get(edge.source)
    const target = nodeById.get(edge.target)
    const { verb } = describeInteraction(source, target, edge.relation)
    if (edge.source === nodeId) {
      return [{ direction: 'to', relation: verb, other: target?.label || labelById.get(edge.target) || edge.target }]
    }
    if (edge.target === nodeId) {
      return [{ direction: 'from', relation: verb, other: source?.label || labelById.get(edge.source) || edge.source }]
    }
    return []
  }).slice(0, 8)
}

function rewriteBehaviors(items, node, nodeById) {
  return asArray(items).map((item) => {
    const action = String(item?.action || '')
    if (action && !/信息流|影响|关系/.test(action)) return item
    const otherId = item.target
    const other = [...nodeById.values()].find((candidate) => candidate.label === otherId || candidate.id === otherId)
    const { verb, toContent, fromContent } = describeInteraction(node, other || otherId, action)
    const incoming = /接到|从/.test(String(item.content || ''))
    return {
      ...item,
      action: verb,
      content: incoming ? fromContent : toContent,
    }
  })
}
