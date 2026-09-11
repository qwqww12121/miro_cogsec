/** User-facing copy must not mention unused OASIS / FORK internals. */
const SKIP_COPY = /未调用|不是 OASIS|不是 FORK|未接入 OASIS|未启用 OASIS|未采用 OASIS|未运行 OASIS|非完整 OASIS|FORK 未调用|不会启动 OASIS|不会启动.*FORK|多智能体 FORK/

export function isInternalSkipCopy(value) {
  return SKIP_COPY.test(String(value || ''))
}

export function stripInternalSkipCopy(value) {
  if (Array.isArray(value)) return value.filter((item) => !isInternalSkipCopy(item))
  if (typeof value !== 'string') return value
  return isInternalSkipCopy(value) ? '' : value
}
