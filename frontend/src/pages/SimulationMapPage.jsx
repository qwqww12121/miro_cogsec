import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import Icon from '../components/Icon'
import ExpandableFrame from '../components/ExpandableFrame'
import AgentTracePanel from '../components/chat/AgentTracePanel'
import ForceConstellation from '../components/chat/ForceConstellation'
import NodeInspectCard from '../components/chat/NodeInspectCard'
import SimulationStoryCards from '../components/chat/SimulationStoryCards'
import { describeInteraction } from '../lib/humanizeSim'
import { buildAgentTrace, graphFromFork, graphFromPropagation, inspectFork, inspectPropagation } from '../lib/forkGraph'
import { summarizeSimulationStory } from '../api/cogsec'
import { buildSimulationStory, buildStorySnapshot } from '../lib/simulationStory'
import { resolveAgentPersona } from '../lib/agentPersona'

const FLOW_DETAILS = {
  risk_profile: {
    title: '场景识别与风险画像',
    intro: '把自然语言输入整理成可核对的场景线索，再落到风险画像和行动建议。',
    steps: [
      ['输入材料', '对话、文件或语音先被整理成可分析文本。', 'input'],
      ['场景线索', '从原文中提取诈骗、舆情或传播相关的证据。', 'signals'],
      ['认知画像', '解释情绪、保护习惯和权威服从等脆弱因素。', 'cognition'],
      ['输出建议', '给出风险分数、证据和下一步干预动作。', 'output'],
    ],
  },
  counterfactual: {
    title: '个体对照路径',
    intro: '比较「继续被诱导」和「及时止损」两条路径。六步对照按时间对齐星图：施压、隔离、关键操作、加码、不可逆、事后。',
    steps: [
      ['分叉点', '对照从这里分成两条路：不是传播里的人，只标记「接下来分别模拟两种选择」。', 'fork'],
      ['继续被诱导', '左列：施害者继续施压后的后验风险。', 'attack'],
      ['及时止损', '右列：核验、求助和拒绝后的变化。', 'defense'],
      ['转折点', '两条路在这里比出差异。干预越早，不可逆操作越少。', 'turn'],
    ],
  },
  propagation_graph: {
    title: '传播关系图',
    intro: '从左到右是传播跳数：源头 → 第一跳 → 扩散 → 更远接收。对照六步会压到这四列上，用来比较「在哪一跳介入」。',
    steps: [
      ['源头', '话题从这里发出。左侧这一列是起点，不是对照路径里的分叉点。', 'hop-0'],
      ['第一跳', '最先接到内容、最容易放大的人，例如意见领袖或媒体。', 'hop-1'],
      ['扩散', '同群、师生、好友之间继续传开。', 'hop-2'],
      ['更远接收', '旁观、官方或更外围的人；箭头指向谁，就是信息流向谁。', 'hop-3'],
    ],
  },
}

const FEATURE_GRAPHS = {
  risk_profile: {
    nodes: [
      { id: 'input', label: '输入材料', desc: '', kind: 'input', group: 'input', who: '这不是某个人。汉语名称「输入材料」对应对话、文件或语音这些分析入口。' },
      { id: 'signals', label: '场景线索', desc: '', kind: 'evidence', group: 'signals', who: '这不是某个人。汉语名称「场景线索」对应原文里能核对的证据。' },
      { id: 'cognition', label: '认知维度', desc: '', kind: 'profile', group: 'cognition', who: '这不是某个人。汉语名称「认知维度」对应情绪、保护习惯、权威服从等。' },
      { id: 'risk', label: '风险画像', desc: '', kind: 'result', group: 'output', who: '这不是某个人。汉语名称「风险画像」对应本次汇总出的脆弱度。' },
      { id: 'action', label: '干预处方', desc: '', kind: 'action', group: 'output', who: '这不是某个人。汉语名称「干预处方」对应核验、求助、止损这些可执行动作。' },
    ],
    edges: [
      ['input', 'signals', '提取线索'],
      ['signals', 'cognition', '解释脆弱点'],
      ['cognition', 'risk', '计算风险'],
      ['risk', 'action', '生成建议'],
    ],
  },
  counterfactual: {
    nodes: [
      { id: 'input', label: '风险线索', desc: '原文中的施压与诱导', kind: 'input', group: 'fork', who: '这不是某个人。汉语名称「风险线索」对应原文里能核对的施压与诱导。', behaviors: [{ time: '第 1 步', action: '识别线索', content: '从原文里抽出权威、时限、转账等施压', target: '策略节点' }] },
      { id: 'strategy', label: '策略节点', desc: '权威、时限、转账等策略', kind: 'evidence', group: 'attack', who: '这不是某个人。汉语名称「策略节点」对应对方用的施压手法。', behaviors: [{ time: '第 2 步', action: '施加压力', content: '对方用权威或截止时间继续施压', target: '攻击路径' }] },
      { id: 'attack', label: '攻击路径', desc: '继续服从后的可能结果', kind: 'risk', group: 'attack', who: '这不是某个人。汉语名称「攻击路径」对应「继续被诱导」这一侧。', behaviors: [{ time: '继续被诱导', action: '答应配合', content: '如果继续按对方节奏走，风险沿这条路累积', target: '路径差异' }] },
      { id: 'intervention', label: '干预节点', desc: '核验、暂停、求助', kind: 'action', group: 'defense', who: '这不是某个人。汉语名称「干预节点」对应核验、暂停、求助这些止损动作。', behaviors: [{ time: '及时止损', action: '核验身份', content: '停下来、独立核实、不发验证码', target: '防御路径' }] },
      { id: 'defense', label: '防御路径', desc: '及时干预后的变化', kind: 'result', group: 'defense', who: '这不是某个人。汉语名称「防御路径」对应「及时止损」这一侧。', behaviors: [{ time: '及时止损', action: '拒绝继续', content: '核验和求助之后，局面转向安全', target: '路径差异' }] },
      { id: 'gap', label: '路径差异', desc: '风险被截断的位置', kind: 'result', group: 'turn', who: '这不是某个人。汉语名称「路径差异」对应两条路比完之后的差别。', behaviors: [{ time: '比较', action: '对照结果', content: '两条路在这里比出差异，干预越早越好', target: '' }] },
    ],
    edges: [
      ['input', 'strategy', '识别策略'],
      ['strategy', 'attack', '继续施压'],
      ['strategy', 'intervention', '触发干预'],
      ['intervention', 'defense', '执行保护'],
      ['attack', 'gap', '风险累积'],
      ['defense', 'gap', '风险下降'],
    ],
  },
  propagation_graph: {
    nodes: [
      { id: 'source', label: '源头内容', desc: '', kind: 'input', hop: 0, group: 'hop-0', who: '对应话题起点，代表最先发出内容的人或账号。', behaviors: [{ time: '第 1 步', action: '发布', content: '把原始内容发到关系网里', target: '关键角色' }] },
      { id: 'roles', label: '关键角色', desc: '', kind: 'evidence', hop: 1, group: 'hop-1', who: '对应最先接到内容的人，代表意见领袖或媒体这一社会部分。', behaviors: [{ time: '第 2 步', action: '接到内容', content: '从源头接到话题', target: '源头内容' }, { time: '第 3 步', action: '转发扩散', content: '继续传给影响关系', target: '影响关系' }] },
      { id: 'relation', label: '影响关系', desc: '', kind: 'profile', hop: 2, group: 'hop-2', who: '对应信任、同群这些关系，代表信息在熟人圈里怎么传。', behaviors: [{ time: '第 3 步', action: '同群往来', content: '在信任关系里继续传开', target: '扩散过程' }] },
      { id: 'spread', label: '扩散过程', desc: '', kind: 'risk', hop: 2, group: 'hop-2', who: '对应跨群继续传开的阶段，代表扩散中的受众。', behaviors: [{ time: '第 4 步', action: '转发扩散', content: '把话题带进更大的圈', target: '关系图' }] },
      { id: 'graph', label: '关系图', desc: '', kind: 'result', hop: 3, group: 'hop-3', who: '这不是某个人。它代表谁把内容传给了谁。', behaviors: [{ time: '汇总', action: '记录路径', content: '把转发和接到内容写成关系', target: '传播结果' }] },
      { id: 'outcome', label: '传播结果', desc: '', kind: 'action', hop: 3, group: 'hop-3', who: '这不是某个人。它代表话题被放大还是被刹住。', behaviors: [{ time: '结果', action: '观察', content: '看话题是继续放大还是被刹住', target: '' }] },
    ],
    edges: [
      ['source', 'roles', '触达角色'],
      ['roles', 'relation', '形成关系'],
      ['relation', 'spread', '推动扩散'],
      ['spread', 'graph', '写入网络'],
      ['graph', 'outcome', '观察结果'],
    ],
  },
}

const FEATURE_LAYOUTS = {
  risk_profile: [
    [150, 92], [325, 155], [575, 155], [700, 315], [430, 410],
  ],
  counterfactual: [
    [135, 95], [345, 145], [700, 115], [330, 350], [700, 350], [500, 430],
  ],
  propagation_graph: [
    [110, 274], [320, 160], [320, 390], [540, 160], [540, 390], [760, 274],
  ],
}

export default function SimulationMapPage() {
  const location = useLocation()
  const analysis = location.state?.analysis || null
  const inputText = location.state?.inputText || ''
  const featureKey = location.state?.featureKey || inferFeatureKey(analysis)
  const feature = FLOW_DETAILS[featureKey] || FLOW_DETAILS.counterfactual
  const [selectedId, setSelectedId] = useState('')
  const [highlightGroup, setHighlightGroup] = useState('')
  const [story, setStory] = useState(null)
  const [storyStatus, setStoryStatus] = useState('idle')
  const graph = useMemo(() => buildGraph(analysis, featureKey), [analysis, featureKey])
  const localStory = useMemo(() => buildSimulationStory(analysis, featureKey, graph, inputText), [analysis, featureKey, graph, inputText])

  useEffect(() => {
    let cancelled = false
    const snapshot = buildStorySnapshot(analysis, featureKey, graph, inputText)
    if (!snapshot.input_text && !snapshot.nodes.length && !snapshot.attack_summary) {
      setStory(localStory)
      setStoryStatus('local')
      return undefined
    }
    setStory(localStory)
    setStoryStatus('loading')
    summarizeSimulationStory({
      input_text: snapshot.input_text,
      scenario: snapshot.scenario,
      feature_key: featureKey,
      snapshot,
    }).then((result) => {
      if (cancelled || !result?.people?.body) return
      setStory({ ...result, hopGuide: localStory.hopGuide })
      setStoryStatus('ready')
    }).catch(() => {
      if (cancelled) return
      setStory(localStory)
      setStoryStatus('local')
    })
    return () => {
      cancelled = true
    }
  }, [analysis, featureKey, graph, inputText, localStory])
  const selectedNode = graph.nodes.find((node) => node.id === selectedId)
  const fork = inspectFork(analysis)
  const propagation = inspectPropagation(analysis)
  const isPropagation = featureKey === 'propagation_graph'
  const traces = buildAgentTrace(analysis)
  const visibleTraces = tracesForNode(traces, selectedNode, isPropagation)
  const mapTitle = isPropagation
    ? '传播关系图'
    : (fork.ran ? '对照路径' : '线索结构')
  const mapHint = isPropagation
    ? (propagation.ran
      ? `从左到右是传播跳数。对照六步会压到这四列上。图上约 ${graph.nodes?.length || 0} 个点，仿真规模约 ${propagation.graph?.agent_count || propagation.nodes?.length || 50} 个代理。`
      : '从左到右是传播跳数。对照六步分别对齐源头、第一跳、扩散、更远接收。')
    : (fork.ran
      ? '从上到下是时间顺序：六步对照对齐分叉、左右两条路和转折点。左列继续被诱导，右列及时止损。'
      : '每个点是本轮能核对的线索。')

  return (
    <div className="h-full min-h-0 overflow-auto bg-[#0f172a]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5">
      <div className="flex items-center justify-between gap-3 mb-5">
        <div className="flex items-center gap-3">
          <Link to={location.state?.returnPath || '/chat'} state={{ sessionId: location.state?.sessionId }} className="btn-ghost px-2 text-white/70 hover:text-white" aria-label="返回">←</Link>
          <div>
            <div className="flex items-center gap-2">
              <span className="w-7 h-7 rounded-lg bg-sand-50 text-sand-600 flex items-center justify-center"><Icon name="network" className="w-4 h-4" /></span>
              <h1 className="text-xl font-semibold text-white">{isPropagation ? '传播关系图' : '对照路径图'}</h1>
            </div>
            <p className="text-xs text-white/55 mt-1">{feature.intro}</p>
          </div>
        </div>
        <Link to="/chat" state={{ sessionId: location.state?.sessionId }} className="btn-ghost text-xs text-white/70 hover:text-white">回到对话</Link>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1.35fr_0.65fr] gap-5">
        <div className="space-y-4">
        <ExpandableFrame
          title={mapTitle}
          hint={mapHint}
          trigger="chrome"
          size="graph"
          tone="dark"
          previewClassName="relative min-h-[320px] h-[42vh] overflow-hidden bg-slate-950"
          modalClassName="relative h-full min-h-0 overflow-hidden bg-slate-950"
        >
          <ForceConstellation
            graph={graph}
            selectedId={selectedId}
            highlightGroup={highlightGroup}
            onSelect={setSelectedId}
            onHighlight={setHighlightGroup}
          />
        </ExpandableFrame>
        <SimulationStoryCards story={story || localStory} status={storyStatus} />
        </div>

        <aside className="space-y-4">
          <ExpandableFrame title="这张图怎么读" hint="悬停放大，点击后可对照节点说明">
            <div className="p-5">
              <p className="text-sm text-ink-500 leading-relaxed">
                {isPropagation
                  ? '每个点是一个传播代理。点击后不只看角色，还能看到他这次转发、接到内容、和谁往来。从左到右是跳数：源头、第一跳、扩散、更远接收。'
                  : '每个点是对照路径上的角色或阶段。点击后看这个角色在对照里做了哪几步。左列「继续被诱导」，右列「及时止损」。'}
              </p>
              {selectedNode && (
                <div className="mt-3 flex flex-wrap gap-2 text-[10px] text-ink-400">
                  <span className="px-2 py-0.5 rounded-full bg-slate-100">角色</span>
                  <span className="px-2 py-0.5 rounded-full bg-slate-100">行为</span>
                  <span className="px-2 py-0.5 rounded-full bg-slate-100">关系</span>
                </div>
              )}
              <NodeInspectCard node={selectedNode} />
            </div>
          </ExpandableFrame>
          {visibleTraces.length > 0 && (
            <ExpandableFrame title={selectedNode ? `${selectedNode.label} · 相关步骤` : '谁在何时对谁做了什么'} hint="逐步说明，点击后可完整翻阅" size="lg">
              <AgentTracePanel events={visibleTraces} scenario={analysis?.scenario || analysis?.scenario_type || ''} />
            </ExpandableFrame>
          )}
          <ExpandableFrame title={`${feature.title} · 四步流程`} hint="点击某一步，图上会高亮这一部分的点" trigger="chrome">
            <div className="p-5 space-y-2">
              {feature.steps.map(([title, text, group], index) => {
                const active = highlightGroup === group
                return (
                  <button
                    key={title}
                    type="button"
                    onClick={() => setHighlightGroup(active ? '' : group)}
                    className={`w-full flex gap-3 text-left rounded-lg px-2 py-2 transition-colors ${active ? 'bg-brand-50 ring-1 ring-brand-100' : 'hover:bg-slate-50'}`}
                  >
                    <div className={`w-6 h-6 rounded-full text-xs font-semibold flex items-center justify-center shrink-0 ${active ? 'bg-brand text-white' : 'bg-brand-50 text-brand'}`}>{index + 1}</div>
                    <div>
                      <div className="text-sm font-medium text-ink-900">{title}</div>
                      <div className="mt-0.5 text-xs text-ink-500 leading-relaxed">{text}</div>
                    </div>
                  </button>
                )
              })}
            </div>
          </ExpandableFrame>
          <Link to="/chat" state={{ sessionId: location.state?.sessionId }} className="group flex items-center gap-3 rounded-xl border border-brand-100 bg-brand-50/60 px-4 py-3 hover:shadow-cardHover transition-all">
            <div className="flex-1"><div className="text-sm font-semibold text-ink-900">继续用自然语言提问</div><div className="text-xs text-ink-500 mt-0.5">回到 MiroCogSec 对话入口</div></div>
            <Icon name="arrow-right" className="w-4 h-4 text-brand transition-transform group-hover:translate-x-1" />
          </Link>
        </aside>
      </div>
      </div>
    </div>
  )
}

function tracesForNode(traces, node, isPropagation) {
  if (!node || !Array.isArray(traces) || !traces.length) return traces
  if (!isPropagation) {
    if (node.lane === 'attack') return traces.filter((event) => /攻击|施害/.test(`${event.actor || ''}${event.target || ''}`))
    if (node.lane === 'defense') return traces.filter((event) => /防御|受害|核验/.test(`${event.actor || ''}${event.target || ''}`))
    return traces
  }
  const keys = [node.id, node.label].filter(Boolean)
  const related = traces.filter((event) => keys.some((key) => `${event.actor || ''} ${event.target || ''} ${event.content || ''}`.includes(String(key))))
  return related.length ? related : traces
}

function inferFeatureKey(analysis) {
  const scenario = String(analysis?.scenario || analysis?.scenario_type || '').toLowerCase()
  if (scenario.includes('event') || scenario.includes('propagation') || scenario.includes('public') || scenario.includes('opinion')) {
    return 'propagation_graph'
  }
  return 'counterfactual'
}

function buildGraph(analysis, featureKey) {
  const isPropagation = featureKey === 'propagation_graph'
  if (isPropagation) {
    const live = graphFromPropagation(analysis)
    const fallback = FEATURE_GRAPHS.propagation_graph
    const nodes = live
      ? live.nodes
      : fallback.nodes.map((node, index) => ({
        ...node,
        source: '能力示意',
        x: FEATURE_LAYOUTS.propagation_graph[index][0],
        y: FEATURE_LAYOUTS.propagation_graph[index][1],
      }))
    const byId = new Map(nodes.map((node) => [node.id, node]))
    const edges = live
      ? (live.edges || []).map((edge, index) => makeEdge(byId.get(String(edge.source)), byId.get(String(edge.target)), edge.relation, false, index)).filter(Boolean)
      : fallback.edges.map(([sourceId, targetId, relation], index) => makeEdge(byId.get(sourceId), byId.get(targetId), relation, true, index)).filter(Boolean)
    return {
      nodes,
      edges,
      dust: [],
      source: live ? live.source : 'template',
      layout: 'layered',
      directed: true,
    }
  }

  const forkGraph = graphFromFork(analysis)
  if (forkGraph) {
    const nodes = forkGraph.nodes
    const byId = new Map(nodes.map((node) => [node.id, node]))
    const edges = (forkGraph.edges || []).map((edge, index) => makeEdge(byId.get(String(edge.source)), byId.get(String(edge.target)), edge.relation, false, index)).filter(Boolean)
    return { nodes, edges, dust: [], source: 'fork', layout: 'sequential', directed: true }
  }
  const fallback = FEATURE_GRAPHS[featureKey] || FEATURE_GRAPHS.counterfactual
  const graph = analysis?.graphPayload || analysis?.graph_payload || {}
  const rawNodes = Array.isArray(graph.nodes) ? graph.nodes : []
  const rawEdges = Array.isArray(graph.edges) ? graph.edges : (Array.isArray(graph.links) ? graph.links : [])
  const useClue = rawNodes.length >= 2 && rawEdges.length > 0
  const sourceNodes = useClue
    ? rawNodes.slice(0, 28).map((node, index) => {
        const persona = resolveAgentPersona(node)
        return {
          id: String(node.id ?? node.node_id ?? node.name ?? index),
          label: persona.label,
          desc: '',
          who: persona.who,
          source: toChinese(String(node.type ?? node.category ?? '线索图')).slice(0, 22),
          kind: node.kind || (index % 3 === 0 ? 'evidence' : 'profile'),
        }
      })
    : fallback.nodes.map((node) => ({ ...node, source: '能力示意' }))
  const semanticLayout = !useClue ? FEATURE_LAYOUTS[featureKey] : null
  const nodes = sourceNodes.map((node, index) => {
    if (semanticLayout?.[index]) {
      return { ...node, x: semanticLayout[index][0], y: semanticLayout[index][1] }
    }
    return layoutNodes(sourceNodes)[index]
  })
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const indexById = new Map(nodes.map((node, index) => [node.id, index]))
  const getEndpoint = (value) => {
    if (value && typeof value === 'object') return String(value.id ?? value.node_id ?? value.name ?? '')
    return String(value ?? '')
  }
  const edges = useClue
    ? rawEdges.slice(0, 60).map((edge, index) => {
        const sourceId = getEndpoint(edge.source ?? edge.from ?? edge.src ?? edge.start)
        const targetId = getEndpoint(edge.target ?? edge.to ?? edge.dst ?? edge.end)
        const source = byId.get(sourceId) || nodes[indexById.get(sourceId)]
        const target = byId.get(targetId) || nodes[indexById.get(targetId)]
        if (!source || !target || source.id === target.id) return null
        const relation = toChinese(String(edge.relation ?? edge.label ?? edge.type ?? edge.description ?? '')).slice(0, 16)
        return makeEdge(source, target, relation, true, index)
      }).filter(Boolean)
    : fallback.edges.map(([sourceId, targetId, relation], index) => makeEdge(byId.get(sourceId), byId.get(targetId), relation, true, index)).filter(Boolean)
  return { nodes, edges, dust: [], source: useClue ? 'clue' : 'template' }
}

function layoutNodes(sourceNodes) {
  return sourceNodes.map((node, index) => {
    const angle = -Math.PI / 2 + index * 2.399963
    const radius = 118 + (index % 4) * 43 + Math.floor(index / 4) * 12
    const x = index === 0 ? 150 : 450 + Math.cos(angle) * radius * 1.55
    const y = index === 0 ? 92 : 250 + Math.sin(angle) * radius * .82
    return { ...node, x, y }
  })
}

function makeEdge(source, target, relation, synthetic, index) {
  if (!source || !target) return null
  const verb = describeInteraction(source, target, relation).verb
  const bend = (index % 2 ? -1 : 1) * (22 + (index % 4) * 7)
  const mx = (source.x + target.x) / 2
  const my = (source.y + target.y) / 2
  const dx = target.x - source.x
  const dy = target.y - source.y
  const length = Math.max(1, Math.hypot(dx, dy))
  const nx = -dy / length
  const ny = dx / length
  return {
    source: source.id,
    target: target.id,
    relation: verb,
    path: `M ${source.x.toFixed(1)} ${source.y.toFixed(1)} Q ${(mx + nx * bend).toFixed(1)} ${(my + ny * bend).toFixed(1)} ${target.x.toFixed(1)} ${target.y.toFixed(1)}`,
    labelX: mx + nx * bend * .65,
    labelY: my + ny * bend * .65 - 4,
    synthetic,
  }
}

const ZH_DICTIONARY = {
  attacker: '施害者',
  victim: '受害人',
  adversary: '对抗者',
  authority: '权威话术',
  transfer: '转账',
  intervention: '干预',
  evidence: '证据',
  strategy: '策略',
  risk: '风险',
  action: '行动',
  input: '输入',
  output: '输出',
  node: '节点',
  edge: '关系',
  source: '源头',
  target: '目标',
  platform: '平台',
  message: '消息',
  rumor: '谣言',
  spread: '扩散',
  core: '核心',
  unknown: '未判定',
  observed: '原文可见',
  inferred: '知识库推断',
  synthetic: '模拟补全',
  offender: '疑似施害者',
  suspect: '疑似施害者',
  witness: '旁观者',
  fraud: '诈骗',
  opinion: '舆情',
  event: '事件',
  propagation: '传播',
  profile: '画像',
  cognition: '认知',
  identity: '身份',
  pressure: '施压',
  account: '账户',
  relation: '关系',
  graph: '星图',
  cluster: '集群',
  amplifier: '放大器',
  origin: '源头',
  'attack path': '攻击路径',
  'defense path': '防御路径',
  'safe account': '安全账户',
  'time pressure': '时间压力',
  'public opinion': '舆情分析',
  'event propagation': '事件传播',
  fraud_im: '诈骗即时通讯',
  public_opinion: '舆情分析',
  event_propagation: '事件传播',
}

function toChinese(value) {
  const text = String(value || '').trim()
  if (!text) return ''
  if (/[\u4e00-\u9fff]/.test(text) && !/[A-Za-z]{3,}/.test(text)) return text
  const direct = ZH_DICTIONARY[text] || ZH_DICTIONARY[text.toLowerCase()]
  if (direct) return direct
  return text
    .replace(/[_-]+/g, ' ')
    .split(' ')
    .map((part) => ZH_DICTIONARY[part.toLowerCase()] || part)
    .join('')
}
