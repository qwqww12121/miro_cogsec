import { useMemo } from 'react'
import { ReactFlow, Background, Controls } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import Section from './Section'
import Empty from './Empty'

const ROLE_STYLE = {
  origin_node:         { border: '2px solid #e8736b', background: '#fff5f5' },
  amplifier:           { border: '2px solid #e8b84b', background: '#fbf5e6' },
  intervention_target: { border: '2px solid #4a90d9', background: '#eff6fc' },
  default:             { border: '1px solid #e2e8f0', background: '#ffffff' },
}

const RISK_TONE = (risk) => {
  const r = Number(risk ?? 0)
  if (r >= 0.7) return '#e8736b'
  if (r >= 0.4) return '#e8b84b'
  return '#52a882'
}

function autoLayout(nodes) {
  const cols = Math.max(1, Math.ceil(Math.sqrt(nodes.length)))
  const GAP_X = 200
  const GAP_Y = 90
  return nodes.map((n, i) => ({
    ...n,
    position: { x: (i % cols) * GAP_X, y: Math.floor(i / cols) * GAP_Y },
  }))
}

function toRfNodes(nodes, highlights, annotations) {
  const highlightSet = new Set((highlights || []).map(String))
  const annotMap = annotations || {}

  return autoLayout(
    nodes.map((n) => {
      const id = String(n.id)
      const ann = annotMap[id] || {}
      const role = ann.role || 'default'
      const roleStyle = ROLE_STYLE[role] || ROLE_STYLE.default
      const isHighlighted = highlightSet.has(id)

      return {
        id,
        data: {
          label: (
            <div style={{ textAlign: 'center', lineHeight: 1.3 }}>
              <div style={{ fontWeight: isHighlighted ? 600 : 400, fontSize: 11 }}>
                {n.label || id}
              </div>
              {n.category && (
                <div style={{ fontSize: 9, color: '#64748b', marginTop: 2 }}>{n.category}</div>
              )}
            </div>
          ),
        },
        style: {
          ...roleStyle,
          borderRadius: 6,
          padding: '4px 8px',
          fontSize: 11,
          minWidth: 80,
          boxShadow: isHighlighted ? '0 0 0 2px #4a90d940' : 'none',
          ...(n.risk != null ? { borderLeftColor: RISK_TONE(n.risk), borderLeftWidth: 3 } : {}),
        },
      }
    })
  )
}

function toRfEdges(edges) {
  return (edges || []).map((e, i) => ({
    id: `e-${i}`,
    source: String(e.source),
    target: String(e.target),
    label: e.label || undefined,
    style: { stroke: '#cbd5e1', strokeWidth: 1.2 },
    labelStyle: { fontSize: 9, fill: '#64748b' },
    markerEnd: { type: 'arrowclosed', color: '#cbd5e1', width: 12, height: 12 },
  }))
}

export default function GraphPayloadView({ graphPayload }) {
  const nodes = graphPayload?.nodes
  const edges = graphPayload?.edges
  const highlights = graphPayload?.highlight_nodes
  const annotations = graphPayload?.node_annotations
  const evidenceLinks = graphPayload?.evidence_links || []

  const rfNodes = useMemo(
    () => (nodes?.length ? toRfNodes(nodes, highlights, annotations) : []),
    [nodes, highlights, annotations]
  )

  const rfEdges = useMemo(
    () => toRfEdges(edges),
    [edges]
  )

  if (!nodes?.length) {
    return (
      <Section title="风险图谱">
        <Empty title="图谱数据未返回" hint="后端未生成 graph_payload.nodes。" />
      </Section>
    )
  }

  return (
    <Section title="风险图谱">
      <div
        className="rounded-md overflow-hidden border border-border"
        style={{ height: Math.min(320, Math.max(180, Math.ceil(nodes.length / Math.ceil(Math.sqrt(nodes.length))) * 90 + 40)) }}
      >
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          panOnScroll
          zoomOnScroll={false}
          minZoom={0.4}
          maxZoom={1.8}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#f1f5f9" gap={20} size={1} />
          <Controls showInteractive={false} style={{ bottom: 8, right: 8 }} />
        </ReactFlow>
      </div>

      {/* 图例 */}
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-ink-500">
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm border-2 border-brand bg-brand-50" />
          干预目标
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm border-2 border-rose-400 bg-rose-50" />
          起点/源头
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-2.5 h-2.5 rounded-sm border-2 border-sand bg-sand-50" />
          放大节点
        </span>
        {highlights?.length > 0 && (
          <span className="text-brand-600">· 蓝色外框 = 高亮节点 ({highlights.length})</span>
        )}
      </div>

      {/* 关键证据链接 */}
      {evidenceLinks.length > 0 && (
        <div className="mt-3 space-y-1.5">
          <div className="text-[11px] text-ink-500 font-medium">关键证据</div>
          {evidenceLinks.slice(0, 3).map((link, i) => (
            <div key={i} className="text-xs text-ink-900 leading-relaxed flex items-start gap-1.5">
              <span className="tag bg-brand-50 text-brand-600 flex-none mt-0.5">证据 {i + 1}</span>
              <span>{link.text}</span>
            </div>
          ))}
        </div>
      )}
    </Section>
  )
}
