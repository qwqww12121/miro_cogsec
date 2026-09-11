import { useEffect, useRef, useState } from 'react'
import { nodeStepGroup } from '../../lib/forkGraph'

const TONES = {
  input: { fill: '#60a5fa', ring: 'rgba(147,197,253,.35)', text: '#dbeafe' },
  evidence: { fill: '#38bdf8', ring: 'rgba(125,211,252,.35)', text: '#e0f2fe' },
  profile: { fill: '#a78bfa', ring: 'rgba(196,181,253,.35)', text: '#ede9fe' },
  risk: { fill: '#fb7185', ring: 'rgba(252,165,165,.32)', text: '#ffe4e6' },
  result: { fill: '#fbbf24', ring: 'rgba(253,230,138,.32)', text: '#fef3c7' },
  action: { fill: '#34d399', ring: 'rgba(167,243,208,.32)', text: '#d1fae5' },
}

const HOP_LABELS = ['源头', '第一跳', '扩散', '更远接收']

export default function ForceConstellation({ graph, selectedId, highlightGroup = '', onSelect, onHighlight }) {
  const wrapRef = useRef(null)
  const [size, setSize] = useState({ w: 900, h: 540 })
  const [simNodes, setSimNodes] = useState([])
  const [transform, setTransform] = useState({ x: 0, y: 0, k: 1 })
  const [hoveredId, setHoveredId] = useState('')
  const dragRef = useRef(null)
  const nodesRef = useRef([])

  useEffect(() => {
    const el = wrapRef.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver(() => {
      const rect = el.getBoundingClientRect()
      setSize({ w: Math.max(360, rect.width), h: Math.max(420, rect.height) })
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [])

  const sequential = graph?.layout === 'sequential' || graph?.source === 'fork'
  const layered = graph?.layout === 'layered'
  const fixedLayout = sequential || layered
  const rawNodes = graph?.nodes || []
  const rawEdges = graph?.edges || []
  const signature = rawNodes.map((node) => node.id).join('|')
  const hopXs = hopColumnXs(size.w)

  useEffect(() => {
    const { w, h } = size
    const count = Math.max(1, rawNodes.length)
    if (layered) {
      const nodes = placeLayeredNodes(rawNodes, w, h)
      nodesRef.current = nodes
      setSimNodes(nodes)
      setTransform({ x: 0, y: 0, k: 1 })
      return undefined
    }
    if (sequential) {
      const nodes = placeSequentialNodes(rawNodes, w, h)
      nodesRef.current = nodes
      setSimNodes(nodes)
      setTransform({ x: 0, y: 0, k: 1 })
      return undefined
    }
    const nodes = rawNodes.map((node, index) => {
      const angle = -Math.PI / 2 + (index / count) * Math.PI * 2
      return {
        ...node,
        x: Number.isFinite(node.x) ? node.x * (w / 900) : w / 2 + Math.cos(angle) * Math.min(w, h) * 0.28,
        y: Number.isFinite(node.y) ? node.y * (h / 500) : h / 2 + Math.sin(angle) * Math.min(w, h) * 0.24,
        vx: 0,
        vy: 0,
      }
    })
    nodesRef.current = nodes
    const indexById = Object.fromEntries(nodes.map((node, index) => [String(node.id), index]))
    let frame = 0
    let ticks = 0
    const rest = Math.max(130, Math.min(w, h) / Math.max(3, Math.sqrt(count)))
    const tick = () => {
      ticks += 1
      const current = nodesRef.current
      for (let i = 0; i < current.length; i += 1) {
        for (let j = i + 1; j < current.length; j += 1) {
          const dx = current[j].x - current[i].x
          const dy = current[j].y - current[i].y
          const dist = Math.max(1, Math.hypot(dx, dy))
          const minDist = 108
          if (dist < minDist) {
            const push = ((minDist - dist) / dist) * 0.09
            current[i].vx -= dx * push
            current[i].vy -= dy * push
            current[j].vx += dx * push
            current[j].vy += dy * push
          } else {
            const charge = 2800 / (dist * dist)
            current[i].vx -= (dx / dist) * charge
            current[i].vy -= (dy / dist) * charge
            current[j].vx += (dx / dist) * charge
            current[j].vy += (dy / dist) * charge
          }
        }
        current[i].vx += (w / 2 - current[i].x) * 0.012
        current[i].vy += (h / 2 - current[i].y) * 0.012
      }
      rawEdges.forEach((edge) => {
        const a = current[indexById[String(edge.source)]]
        const b = current[indexById[String(edge.target)]]
        if (!a || !b) return
        const dx = b.x - a.x
        const dy = b.y - a.y
        const dist = Math.max(1, Math.hypot(dx, dy))
        const pull = (dist - rest) * 0.01
        a.vx += (dx / dist) * pull
        a.vy += (dy / dist) * pull
        b.vx -= (dx / dist) * pull
        b.vy -= (dy / dist) * pull
      })
      current.forEach((node) => {
        if (node.fx != null) {
          node.x = node.fx
          node.y = node.fy
          node.vx = 0
          node.vy = 0
          return
        }
        node.vx *= 0.78
        node.vy *= 0.78
        node.x += node.vx
        node.y += node.vy
        node.x = Math.min(w - 72, Math.max(72, node.x))
        node.y = Math.min(h - 56, Math.max(48, node.y))
      })
      if (ticks % 2 === 0) setSimNodes(current.map((node) => ({ ...node })))
      if (ticks < 240) frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [signature, size.w, size.h, rawEdges, rawNodes, sequential, layered, fixedLayout])

  const onPointerDown = (event) => {
    if (event.target?.closest?.('[data-node]')) return
    dragRef.current = { x: event.clientX, y: event.clientY, ox: transform.x, oy: transform.y, moved: false }
  }

  const onPointerMove = (event) => {
    const drag = dragRef.current
    if (!drag) return
    const dx = event.clientX - drag.x
    const dy = event.clientY - drag.y
    if (Math.hypot(dx, dy) > 3) drag.moved = true
    setTransform((prev) => ({ ...prev, x: drag.ox + dx, y: drag.oy + dy }))
  }

  const zoomBy = (factor) => {
    setTransform((prev) => {
      const nextK = Math.min(2.4, Math.max(0.4, prev.k * factor))
      const cx = size.w / 2
      const cy = size.h / 2
      return {
        k: nextK,
        x: cx - ((cx - prev.x) / Math.max(0.01, prev.k)) * nextK,
        y: cy - ((cy - prev.y) / Math.max(0.01, prev.k)) * nextK,
      }
    })
  }

  useEffect(() => {
    const el = wrapRef.current
    if (!el) return undefined
    const onWheel = (event) => {
      event.preventDefault()
      zoomBy(event.deltaY < 0 ? 1.1 : 0.9)
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  })

  const onPointerUp = () => {
    const drag = dragRef.current
    dragRef.current = null
    if (!drag || drag.moved) return
    onSelect?.('')
    onHighlight?.('')
    setHoveredId('')
  }

  const nodes = simNodes.length
    ? simNodes
    : (layered
      ? placeLayeredNodes(rawNodes, size.w, size.h)
      : sequential
        ? placeSequentialNodes(rawNodes, size.w, size.h)
        : rawNodes)
  const byId = Object.fromEntries(nodes.map((node) => [String(node.id), node]))
  const groupActive = Boolean(highlightGroup)
  const attackX = size.w * 0.22
  const defenseX = size.w * 0.78

  return (
    <div ref={wrapRef} className="absolute inset-0 h-full w-full min-h-[420px] cursor-grab active:cursor-grabbing">
      <svg
        width="100%"
        height="100%"
        viewBox={`0 0 ${size.w} ${size.h}`}
        className="w-full h-full"
        role="img"
        aria-label="关系图"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerLeave={onPointerUp}
      >
        <defs>
          <marker id="flowArrow" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 Z" fill="#93c5fd" />
          </marker>
          <marker id="flowArrowHot" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 Z" fill="#facc15" />
          </marker>
        </defs>
        <g transform={`translate(${transform.x} ${transform.y}) scale(${transform.k})`}>
          {sequential && (
            <g fill="rgba(226,232,255,.82)" fontSize="12" fontWeight="700" pointerEvents="none">
              <text x={attackX} y={28} textAnchor="middle" fill={captionFill(highlightGroup, 'attack')}>左列 · 继续被诱导</text>
              <text x={defenseX} y={28} textAnchor="middle" fill={captionFill(highlightGroup, 'defense')}>右列 · 及时止损</text>
            </g>
          )}
          {layered && (
            <g fontSize="12" fontWeight="700" pointerEvents="none">
              {HOP_LABELS.map((label, hop) => (
                <text
                  key={label}
                  x={hopXs[hop]}
                  y={28}
                  textAnchor="middle"
                  fill={captionFill(highlightGroup, `hop-${hop}`)}
                >
                  {label}
                </text>
              ))}
            </g>
          )}
          {rawEdges.map((edge, index) => {
            const source = byId[String(edge.source)]
            const target = byId[String(edge.target)]
            if (!source || !target) return null
            const line = shortenLine(source.x, source.y, target.x, target.y, 8)
            const mx = (line.x1 + line.x2) / 2
            const my = (line.y1 + line.y2) / 2
            const sourceGroup = nodeStepGroup(source)
            const targetGroup = nodeStepGroup(target)
            const hovered = hoveredId && hoveredId !== source.id && hoveredId !== target.id
            const inHighlight = !groupActive || sourceGroup === highlightGroup || targetGroup === highlightGroup
            const hot = groupActive && (sourceGroup === highlightGroup || targetGroup === highlightGroup)
            return (
              <g key={`${edge.source}-${edge.target}-${index}`} opacity={hovered || !inHighlight ? 0.12 : 0.9}>
                <line
                  x1={line.x1}
                  y1={line.y1}
                  x2={line.x2}
                  y2={line.y2}
                  stroke={hot ? '#facc15' : (edge.synthetic ? '#64748b' : '#93c5fd')}
                  strokeWidth={hot ? 2.4 : 1.8}
                  strokeDasharray={edge.synthetic ? '5 6' : undefined}
                  markerEnd={graph?.directed || sequential || layered ? (hot ? 'url(#flowArrowHot)' : 'url(#flowArrow)') : undefined}
                />
                {edge.relation && String(edge.relation).length <= 4 && (
                  <text x={mx} y={my - 6} textAnchor="middle" fill="rgba(226,232,255,.72)" fontSize="9">
                    {edge.relation}
                  </text>
                )}
              </g>
            )
          })}
          {nodes.map((node) => {
            const tone = TONES[node.kind] || TONES.evidence
            const inGroup = !groupActive || nodeStepGroup(node) === highlightGroup
            const selected = selectedId === node.id || hoveredId === node.id
            const hot = groupActive && inGroup
            return (
              <g
                key={node.id}
                data-node="true"
                transform={`translate(${node.x} ${node.y})`}
                className="cursor-pointer"
                opacity={inGroup ? 1 : 0.14}
                onMouseEnter={() => setHoveredId(node.id)}
                onMouseLeave={() => setHoveredId('')}
                onClick={() => onSelect?.(selectedId === node.id ? '' : node.id)}
              >
                {hot ? <circle r="12" fill="none" stroke="#facc15" strokeWidth="2" /> : null}
                <circle r={selected || hot ? 8 : 5} fill={tone.fill} stroke={hot ? '#facc15' : '#fff'} strokeWidth={hot ? 2 : 1} />
                <text y="18" textAnchor="middle" fill={hot ? '#fde68a' : '#f8fafc'} fontSize="11" fontWeight={selected || hot ? 700 : 600}>
                  {node.label}
                </text>
              </g>
            )
          })}
        </g>
      </svg>
      <div className="absolute right-3 top-3 z-10 flex flex-col gap-1">
        <button type="button" className="w-8 h-8 rounded-lg bg-white/90 text-ink-900 text-lg leading-none shadow" onClick={() => zoomBy(1.2)} aria-label="放大">+</button>
        <button type="button" className="w-8 h-8 rounded-lg bg-white/90 text-ink-900 text-lg leading-none shadow" onClick={() => zoomBy(1 / 1.2)} aria-label="缩小">−</button>
        <button type="button" className="w-8 h-8 rounded-lg bg-white/90 text-[10px] text-ink-700 shadow" onClick={() => setTransform({ x: 0, y: 0, k: 1 })} aria-label="复位">复位</button>
      </div>
      <div className="pointer-events-none absolute left-3 bottom-3 text-[10px] text-white/45">
        {sequential
          ? '左列是继续被诱导，右列是及时止损；箭头表示先后'
          : layered
            ? '从左到右是源头、第一跳、扩散、更远接收；箭头表示信息流向谁'
            : '右上角放大缩小，滚轮也可缩放，拖空白处平移'}
      </div>
    </div>
  )
}

function hopColumnXs(w) {
  const pad = Math.max(72, Math.min(110, w * 0.09))
  const inner = Math.max(280, w - pad * 2)
  return [0, 1, 2, 3].map((index) => pad + (inner * (index + 0.5)) / 4)
}

function hopIndex(node) {
  const group = nodeStepGroup(node)
  const match = /^hop-(\d)$/.exec(group)
  if (match) return Number(match[1])
  if (Number.isFinite(Number(node?.hop))) return Math.min(3, Math.max(0, Number(node.hop)))
  return 2
}

function placeLayeredNodes(rawNodes, w, h) {
  const xs = hopColumnXs(w)
  const buckets = [[], [], [], []]
  rawNodes.forEach((node) => {
    buckets[hopIndex(node)].push(node)
  })
  const yTop = 72
  const yBottom = Math.max(yTop + 80, h - 44)
  const band = (xs[1] - xs[0]) || (w / 4)
  const placed = []
  buckets.forEach((siblings, layer) => {
    const count = siblings.length
    siblings.forEach((node, index) => {
      let x = xs[layer]
      let y = count <= 1 ? (yTop + yBottom) / 2 : yTop + (index / Math.max(1, count - 1)) * (yBottom - yTop)
      if (count > 6) {
        const cols = count > 12 ? 3 : 2
        const col = index % cols
        const row = Math.floor(index / cols)
        const rows = Math.ceil(count / cols)
        x = xs[layer] + (col - (cols - 1) / 2) * Math.min(56, band * 0.32)
        y = rows <= 1 ? (yTop + yBottom) / 2 : yTop + (row / Math.max(1, rows - 1)) * (yBottom - yTop)
      }
      placed.push({
        ...node,
        hop: layer,
        group: `hop-${layer}`,
        x,
        y,
      })
    })
  })
  return placed
}

function placeSequentialNodes(rawNodes, w, h) {
  return rawNodes.map((node) => {
    const group = nodeStepGroup(node)
    let x = Number.isFinite(node.x) ? node.x * (w / 900) : w / 2
    if (group === 'attack') x = w * 0.22
    else if (group === 'defense') x = w * 0.78
    else if (group === 'fork' || group === 'turn') x = w / 2
    return {
      ...node,
      x,
      y: Number.isFinite(node.y) ? node.y * (h / 520) : h / 2,
    }
  })
}

function captionFill(highlightGroup, group) {
  if (!highlightGroup) return 'rgba(226,232,255,.88)'
  return highlightGroup === group ? '#fde68a' : 'rgba(226,232,255,.28)'
}

function shortenLine(x1, y1, x2, y2, pad = 8) {
  const dx = x2 - x1
  const dy = y2 - y1
  const length = Math.max(1, Math.hypot(dx, dy))
  const ux = dx / length
  const uy = dy / length
  return {
    x1: x1 + ux * pad,
    y1: y1 + uy * pad,
    x2: x2 - ux * pad,
    y2: y2 - uy * pad,
  }
}
