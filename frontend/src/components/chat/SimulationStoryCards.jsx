export default function SimulationStoryCards({ story, status = 'idle' }) {
  if (!story) return null
  return (
    <div className="space-y-4">
      {status === 'loading' ? (
        <div className="text-[11px] text-white/45">正在根据原文和仿真结果整理这次事件的说明…</div>
      ) : null}
      <article className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-white shadow-card">
        <div className="text-[10px] uppercase tracking-wide text-white/40">人物关系</div>
        <h3 className="mt-1 text-sm font-semibold text-white">{story.people.title}</h3>
        <p className="mt-3 text-sm leading-7 text-white/80 whitespace-pre-wrap">{story.people.body}</p>
      </article>
      <article className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-white shadow-card">
        <div className="text-[10px] uppercase tracking-wide text-white/40">事态发展</div>
        <h3 className="mt-1 text-sm font-semibold text-white">{story.futures.title}</h3>
        {story.futures.lead ? (
          <p className="mt-2 text-xs leading-6 text-white/50">{story.futures.lead}</p>
        ) : null}
        <div className="mt-4 grid gap-3 sm:grid-cols-1">
          {story.futures.items.map((item) => (
            <div key={item.label} className="rounded-lg border border-slate-800 bg-slate-950/80 p-4">
              <div className="text-xs font-semibold text-amber-200">{item.label} · {item.title}</div>
              <p className="mt-2 text-sm leading-7 text-white/75 whitespace-pre-wrap">{item.body}</p>
            </div>
          ))}
        </div>
      </article>
      {story.hopGuide?.rows?.length ? (
        <article className="rounded-xl border border-slate-800 bg-slate-900 p-5 text-white shadow-card">
          <div className="text-[10px] uppercase tracking-wide text-white/40">干预跳数</div>
          <h3 className="mt-1 text-sm font-semibold text-white">{story.hopGuide.title}</h3>
          {story.hopGuide.lead ? (
            <p className="mt-2 text-xs leading-6 text-white/50">{story.hopGuide.lead}</p>
          ) : null}
          <div className="mt-3 space-y-2">
            {story.hopGuide.rows.map((row) => (
              <div key={row.step} className="rounded-lg border border-slate-800 bg-slate-950/80 px-3 py-2.5">
                <div className="text-xs font-semibold text-amber-200">第 {row.step} 步 · {row.where}</div>
                <p className="mt-1 text-sm leading-6 text-white/75">{row.ifIntervene}</p>
              </div>
            ))}
          </div>
          {story.hopGuide.minImpact ? (
            <p className="mt-3 text-sm leading-6 text-emerald-200/90">影响最小：{story.hopGuide.minImpact}</p>
          ) : null}
          {story.hopGuide.maxGain ? (
            <p className="mt-2 text-sm leading-6 text-amber-100/80">ΔR 最大：{story.hopGuide.maxGain}</p>
          ) : null}
          {story.hopGuide.prefer ? (
            <p className="mt-2 text-xs leading-6 text-white/55">{story.hopGuide.prefer}</p>
          ) : null}
        </article>
      ) : null}
      {story.prescriptions?.items?.length ? (
        <article className="rounded-xl border border-emerald-900/60 bg-slate-900 p-5 text-white shadow-card">
          <div className="text-[10px] uppercase tracking-wide text-emerald-200/70">干预处方</div>
          <h3 className="mt-1 text-sm font-semibold text-white">{story.prescriptions.title}</h3>
          {story.prescriptions.lead ? (
            <p className="mt-2 text-xs leading-6 text-white/50">{story.prescriptions.lead}</p>
          ) : null}
          <ol className="mt-3 space-y-3">
            {story.prescriptions.items.map((item, index) => (
              <li key={item.title} className="rounded-lg border border-emerald-900/40 bg-slate-950/80 px-3 py-2.5">
                <div className="text-xs font-semibold text-emerald-200">{index + 1}. {item.title}</div>
                {item.rationale ? (
                  <p className="mt-1 text-xs leading-6 text-white/50">{item.rationale}</p>
                ) : null}
                {item.actions?.length ? (
                  <ul className="mt-1.5 space-y-1 text-sm leading-6 text-white/80">
                    {item.actions.map((action) => (
                      <li key={action}>· {action}</li>
                    ))}
                  </ul>
                ) : null}
                {item.expected ? (
                  <p className="mt-1.5 text-xs leading-6 text-emerald-100/70">预期：{item.expected}</p>
                ) : null}
              </li>
            ))}
          </ol>
        </article>
      ) : null}
    </div>
  )
}
