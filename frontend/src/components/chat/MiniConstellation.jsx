export default function MiniConstellation({ graph, height = 168 }) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes.slice(0, 18) : []
  const edges = Array.isArray(graph?.edges) ? graph.edges : (Array.isArray(graph?.links) ? graph.links : [])
  if (nodes.length < 2) return null
  const width = 520
  const live = graph?.source === 'lightweight_propagation' || graph?.engine === 'social_state'
  const placed = nodes.map((node, index) => {
    const angle = -Math.PI / 2 + (index / Math.max(nodes.length, 1)) * Math.PI * 2
    const radius = live ? 58 + (index % 3) * 10 : 36
    return {
      ...node,
      x: 260 + Math.cos(angle) * (live ? radius * 1.7 : 190),
      y: height / 2 + Math.sin(angle) * radius,
    }
  })
  const byId = new Map(placed.map((node) => [String(node.id), node]))
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={`w-full mt-2 rounded-xl ${live ? 'bg-slate-950' : 'bg-slate-900'}`} style={{ height }}>
      {edges.slice(0, 40).map((edge, index) => {
        const source = byId.get(String(edge.source ?? edge.from))
        const target = byId.get(String(edge.target ?? edge.to))
        if (!source || !target) return null
        return (
          <g key={`${source.id}-${target.id}-${index}`}>
            <line x1={source.x} y1={source.y} x2={target.x} y2={target.y} stroke="#94a3b8" strokeOpacity=".55" />
          </g>
        )
      })}
      {placed.map((node) => (
        <g key={node.id} transform={`translate(${node.x} ${node.y})`}>
          <circle r="4" fill={node.kind === 'risk' ? '#fb7185' : (node.kind === 'action' ? '#34d399' : '#60a5fa')} stroke="#fff" strokeWidth="0.6" />
          <text y="12" textAnchor="middle" fill="#e2e8f0" fontSize="8">{String(node.label || '').slice(0, 8)}</text>
        </g>
      ))}
    </svg>
  )
}
