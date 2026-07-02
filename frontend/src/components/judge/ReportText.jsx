// 轻量报告文本格式化器。
// 数据扫描结论：裁判报告是"半结构化纯文本"——只有段落（\n\n）和
// 列表（"- " 无序 / "1. " 有序），没有标题/加粗/代码/链接等富 Markdown。
// 因此不引入 react-markdown，这里按 段落 + 列表 两类块渲染即可。

const UL_RE = /^\s*[-•]\s+/
const OL_RE = /^\s*\d+[.、)]\s+/

function stripMarker(line) {
  if (UL_RE.test(line)) return line.replace(UL_RE, '')
  const m = line.match(OL_RE)
  return m ? line.slice(m[0].length) : line
}

function renderBlock(lines, keyBase) {
  const out = []
  let list = null // { type: 'ul' | 'ol', items: [] }
  let counter = 0
  const flush = () => {
    if (!list) return
    const Tag = list.type === 'ol' ? 'ol' : 'ul'
    const cls =
      list.type === 'ol'
        ? 'list-decimal pl-5 space-y-0.5 marker:text-ink-300'
        : 'list-disc pl-5 space-y-0.5 marker:text-ink-300'
    out.push(
      <Tag key={`l-${keyBase}-${counter++}`} className={cls}>
        {list.items.map((t, i) => (
          <li key={i}>{t}</li>
        ))}
      </Tag>
    )
    list = null
  }
  for (const raw of lines) {
    const line = raw.replace(/\s+$/, '')
    if (!line.trim()) continue
    if (UL_RE.test(line)) {
      if (!list || list.type !== 'ul') {
        flush()
        list = { type: 'ul', items: [] }
      }
      list.items.push(stripMarker(line))
    } else if (OL_RE.test(line)) {
      if (!list || list.type !== 'ol') {
        flush()
        list = { type: 'ol', items: [] }
      }
      list.items.push(stripMarker(line))
    } else {
      flush()
      out.push(
        <p key={`p-${keyBase}-${counter++}`} className="leading-relaxed">
          {line}
        </p>
      )
    }
  }
  flush()
  return out
}

export default function ReportText({ text, className = '' }) {
  const blocks = String(text || '')
    .split(/\n{2,}/)
    .map((b) => b.split(/\n/))
    .filter((b) => b.join('').trim())
  return (
    <div className={`text-[13px] text-ink-900 space-y-2 ${className}`}>
      {blocks.map((b, i) => (
        <div key={i} className="space-y-1.5">
          {renderBlock(b, i)}
        </div>
      ))}
    </div>
  )
}
