import { describeAnomaly } from '../scenarios/glossary'

/**
 * 异常信号标签：统一展示面向用户的中文短语，不把内部枚举名暴露到页面。
 */
export default function AnomalyTag({ raw }) {
  const { label } = describeAnomaly(raw)
  return <span className="tag bg-rose-50 text-rose-600">{label}</span>
}
