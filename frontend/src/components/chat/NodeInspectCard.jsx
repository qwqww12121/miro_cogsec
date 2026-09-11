import { describeAgentWho } from '../../lib/agentPersona'

export default function NodeInspectCard({ node }) {
  if (!node) {
    return (
      <p className="mt-4 text-xs text-ink-400 leading-relaxed">
        点击图上的一个点，查看这个角色，以及他在这次仿真里做了什么。
      </p>
    )
  }
  const who = node.who || describeAgentWho(node.role || node.label, node.id)
  const behaviors = Array.isArray(node.behaviors) ? node.behaviors.filter((item) => item?.action || item?.content) : []
  const relations = Array.isArray(node.relations) ? node.relations : []
  return (
    <div className="mt-4 rounded-lg bg-sand-50 border border-sand-100 p-3 space-y-3">
      <div>
        <div className="text-[10px] uppercase tracking-wide text-ink-400">角色</div>
        <div className="mt-0.5 text-sm font-semibold text-ink-900">{node.label}</div>
        {(node.place || node.source) && (
          <div className="mt-0.5 text-[11px] text-ink-400">{node.place || node.source}</div>
        )}
        {who ? (
          <div className="mt-2 text-xs text-ink-700 leading-relaxed">{who}</div>
        ) : null}
      </div>
      {behaviors.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wide text-ink-400">这次做了什么</div>
          <ul className="mt-1 space-y-1.5">
            {behaviors.map((item, index) => (
              <li key={`${item.time}-${item.action}-${index}`} className="text-xs text-ink-700 leading-relaxed">
                <span className="text-ink-400 font-mono">{item.time || `行为 ${index + 1}`}</span>
                <span className="ml-2 font-medium">{item.action}</span>
                {item.target ? <span className="text-ink-500"> → {item.target}</span> : null}
                {item.content && item.content !== item.action ? (
                  <div className="mt-0.5 text-ink-500">{item.content}</div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
      {relations.length > 0 && (
        <div>
          <div className="text-[10px] uppercase tracking-wide text-ink-400">和谁有关系</div>
          <ul className="mt-1 space-y-1">
            {relations.map((item, index) => (
              <li key={`${item.direction}-${item.other}-${index}`} className="text-xs text-ink-600">
                {item.direction === 'from' ? `从 ${item.other} ${item.relation || '接到信息'}` : `向 ${item.other} ${item.relation || '传出信息'}`}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
