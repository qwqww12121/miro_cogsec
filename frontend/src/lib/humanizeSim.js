import { detectRole } from './agentPersona'

const ACTION_ZH = {
  applyauthority: '施加权威压力',
  apply_authority: '施加权威压力',
  providesafeaction: '给出可执行的安全建议',
  provide_safe_action: '给出可执行的安全建议',
  applyurgency: '施加截止时间压力',
  comply: '受害人答应配合',
  refuse: '受害人拒绝继续',
  request_verification_code: '对方索要验证码',
  identify_risk_signal: '系统识别到风险信号',
  change_story: '对方改口圆谎',
  apply_urgency: '施加截止时间压力',
  fraud_interaction: '诈骗对打',
  skip: '这一步没有真正执行',
  transfer: '引导转账',
  verify: '核验身份',
  help: '向他人求助',
  intervention: '及时干预',
  world_state: '推演中的局面',
  auditverification: '核对不同版本的信息',
  audit_verification: '核对不同版本的信息',
  containment: '控制继续扩散',
  prescription: '给出应对办法',
  世界状态: '推演中的局面',
  spread: '转发扩散',
  exposed: '接到内容',
  share: '转发',
  post: '发布',
  comment: '评论',
  repost: '转发',
  like: '点赞',
  follow: '关注',
  information_flow: '告知',
  信息流: '告知',
  same_community: '同群讨论',
  trust: '信任往来',
  friend: '好友沟通',
}

const ACTOR_ZH = {
  threat_actor: '施害者智能体',
  user_twin: '受害人孪生',
  verifier: '核验智能体',
  A: '攻击路径',
  B: '防御路径',
  '攻击路径 A': '攻击路径',
  '防御路径 B': '防御路径',
  'FORK 推演器': '对照路径',
}

export const FORK_NODE_ZH = {
  phishing_link_entry: '点击钓鱼链接并提交账号',
  transfer_money: '转账',
  screen_share: '屏幕共享',
  verification_code: '验证码',
  unknown_app_download: '安装不明应用',
  social_isolation: '切断外部核验',
  fake_official_verification: '伪造官方核实',
  private_contact_lure: '转到私人渠道继续沟通',
  identity_asset_exchange: '交出实名身份资料',
  unlicensed_financial_service: '未核验的代还或套现',
  gambling_entry: '被引向博彩充值',
  timeout_fallback: '对照超时回退',
  no_valid_fork: '未形成明确分叉',
  fraud_decision: '诈骗关键决策',
  fraud_multi_role_primary: '多方对打主线',
  verification_gap: '核验习惯缺口',
  info_propagation_risk: '信息不核实就扩散',
  misinformation_risk: '失实信息扩散',
  generic: '高危操作',
}

const T0_RULE_ZH = {
  screen_share_bank_card: '屏幕共享套取银行卡',
  safe_account_transfer: '诱导转入所谓安全账户',
  police_secrecy_isolation: '冒充警方要求保密隔离',
  credit_fraud_app: '以征信异常诱导下载应用',
  impersonation_with_app: '冒充机构诱导下载应用',
  verification_code_request: '索要验证码',
  secrecy_isolation: '要求对家人保密',
  unknown_app_download: '安装不明应用',
  classic_impersonation_opening: '冒充公职或客服开场',
  credit_card_repay_lure: '信用卡代还或套现诱导',
}

const LATENCY_ZH = {
  t0_ms: '即时拦截',
  t0_latency_ms: '即时拦截',
  profile_ms: '认知画像',
  rag_ms: '策略检索',
  runtime_ms: '对照推演',
  report_ms: '报告生成',
  end_to_end_ms: '全程',
}

const TOKEN_ZH = {
  phishing: '钓鱼',
  link: '链接',
  entry: '入口',
  transfer: '转账',
  money: '资金',
  screen: '屏幕',
  share: '共享',
  verification: '核验',
  code: '验证码',
  unknown: '不明',
  app: '应用',
  download: '安装',
  social: '社交',
  isolation: '隔离',
  fake: '伪造',
  official: '官方',
  private: '私人',
  contact: '联系',
  lure: '诱导',
  identity: '身份',
  asset: '资产',
  exchange: '交换',
  unlicensed: '无资质',
  financial: '金融',
  service: '服务',
  gambling: '博彩',
  gap: '缺口',
  node: '',
  fork: '分叉',
  point: '节点',
  type: '',
  safe: '安全',
  account: '账户',
  bank: '银行',
  card: '卡',
  police: '警方',
  secrecy: '保密',
  credit: '征信',
  fraud: '诈骗',
  impersonation: '冒充',
  request: '索要',
  classic: '典型',
  opening: '开场',
  repay: '代还',
}

const IDENTIFIER_ZH = {
  ...FORK_NODE_ZH,
  ...T0_RULE_ZH,
  ...LATENCY_ZH,
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function humanizeIdentifier(raw) {
  const key = String(raw || '').trim()
  if (!key) return ''
  if (IDENTIFIER_ZH[key]) return IDENTIFIER_ZH[key]
  const lower = key.toLowerCase()
  if (IDENTIFIER_ZH[lower]) return IDENTIFIER_ZH[lower]
  const mapped = lower.split(/[_-]+/).map((part) => TOKEN_ZH[part])
  const joined = mapped.filter(Boolean).join('')
  return joined || '高危操作'
}

export function humanizeVisibleText(value) {
  let out = String(value ?? '').trim()
  if (!out) return ''
  const keys = Object.keys(IDENTIFIER_ZH).sort((left, right) => right.length - left.length)
  for (const key of keys) {
    if (!key || key.length < 3) continue
    out = out.replace(new RegExp(escapeRegExp(key), 'gi'), IDENTIFIER_ZH[key])
  }
  out = out
    .replace(/在「([^」]+)」\s*节点前/g, '在「$1」发生前')
    .replace(/在\s*([^，。;\n]{2,40}?)\s*节点前/g, '在「$1」发生前')
    .replace(/\bSYSTEM[_\s-]*2\b/gi, '审慎核验')
    .replace(/\bSYSTEM[_\s-]*1\b/gi, '直觉反应')
    .replace(/System\s*2/gi, '审慎核验')
    .replace(/System\s*1/gi, '直觉反应')
    .replace(/\bFORK\b/g, '对照路径')
    .replace(/\bFork\b/g, '危险分支')
    .replace(/\bAMA\b/g, '公开答疑')
    .replace(/官方\s*APP/gi, '官方应用')
    .replace(/\bAPP\b/g, '应用')
    .replace(/审计Agent/g, '对照')
    .replace(/\bAgent\b/g, '对照')
    .replace(/\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b/gi, (match) => humanizeIdentifier(match))
  return out.replace(/[ \t]{2,}/g, ' ').trim()
}

export function humanizeAction(value) {
  const raw = String(value || '').trim()
  if (!raw) return ''
  if (ACTION_ZH[raw]) return ACTION_ZH[raw]
  const key = raw.replace(/[\s-]+/g, '_').toLowerCase()
  if (ACTION_ZH[key]) return ACTION_ZH[key]
  return humanizeVisibleText(raw)
}

export function humanizeActor(value) {
  const raw = String(value || '').trim()
  if (!raw) return '系统'
  return ACTOR_ZH[raw] || humanizeAction(raw)
}

export function summarizeSteps(steps, limit = 3) {
  const labels = (steps || []).map((step) => humanizeAction(step?.action || step?.action_type || step)).filter(Boolean)
  if (!labels.length) return ''
  const shown = labels.slice(0, limit)
  return shown.join(' → ') + (labels.length > limit ? ' …' : '')
}

export function describeTraceEvent(event, scenario = '') {
  const actor = humanizeActor(event?.actor)
  const targetRaw = String(event?.target || '')
  const target = !targetRaw ? '' : (targetRaw === '世界状态' ? '当前局面' : humanizeActor(targetRaw))
  const action = humanizeAction(event?.action)
  const content = humanizeAction(event?.content) || String(event?.content || '').trim()
  const uniqueBits = [...new Set([action, content].filter(Boolean))]
  const headline = uniqueBits.join(' · ')
  const opinion = scenario === 'public_opinion' || /舆情|舆论|传播/.test(`${actor}${scenario}`)
  const isDefense = /防御/.test(actor)
  const isAttack = /攻击/.test(actor)
  let meaning = headline
  if (event?.skipped) {
    meaning = content || event?.content || '这一层没有真正跑起来。'
  } else if (opinion) {
    meaning = `这一步在看舆论会怎么被放大或被刹住：${content || action || '核对信息、控制扩散、给出说法'}。`
  } else if (isDefense) {
    meaning = `如果及时核验、求助或拒绝，这一步对应：${content || action || '干预生效'}。这不是说当事人已经这么做了。`
  } else if (isAttack) {
    meaning = `如果继续按对方节奏走，这一步对应：${content || action || '继续受影响'}。`
  } else if (headline) {
    meaning = `${actor}${target ? `对${target}` : ''}：${headline}`
  }
  return {
    time: event?.time || '',
    actor,
    target,
    skipped: Boolean(event?.skipped),
    headline,
    meaning,
    amplify: event?.amplify ? humanizeAction(event.amplify) || event.amplify : '',
  }
}

const GENERIC_RELATION = /^(信息流|information_flow|关系|影响|flow|link|edge|把信息传给对方)$/i

const ROLE_VERB = {
  original_poster: '发布',
  student_kol: '转发',
  repost_kol: '转发',
  controversy_amplifier: '煽动',
  anonymous_amplifier: '扩散',
  fact_checker: '澄清',
  official_responder: '通报',
  school_official: '通报',
  media_observer: '报道',
  teacher: '提醒',
  ordinary_student: '讨论',
  ordinary_viewer: '讨论',
  victim: '求助',
  attacker: '施压',
  family_member: '劝阻',
  police_or_bank: '核实',
  platform_moderator: '处置',
}

const ACTION_VERB = {
  spread: '转发',
  share: '转发',
  repost: '转发',
  post: '发布',
  comment: '评论',
  exposed: '告知',
  like: '点赞',
  follow: '关注',
}

function nodeSearchText(node) {
  if (!node) return ''
  if (typeof node === 'string') return node
  return [node.role, node.type, node.label, node.name, node.id].filter(Boolean).join(' ')
}

function verbFromRole(raw) {
  const role = detectRole(raw) || detectRole(String(raw || '').replace(/\d+$/g, ''))
  if (role && ROLE_VERB[role]) return ROLE_VERB[role]
  const text = String(raw || '').toLowerCase()
  if (/(fact|check|核查|澄清)/.test(text)) return '澄清'
  if (/(official|通报|回应|校方)/.test(text)) return '通报'
  if (/(media|记者|报道)/.test(text)) return '报道'
  if (/(kol|意见领袖|转发)/.test(text)) return '转发'
  if (/(amplif|煽动|扩散)/.test(text)) return '扩散'
  if (/(source|origin|首发)/.test(text)) return '发布'
  if (/(teacher|老师|提醒)/.test(text)) return '提醒'
  if (/(attack|施害|催)/.test(text)) return '施压'
  if (/(victim|受害)/.test(text)) return '求助'
  if (/(police|bank|核实|核验)/.test(text)) return '核实'
  if (/(family|家人|劝)/.test(text)) return '劝阻'
  return '告知'
}

export function interactionVerb(source, target, relation = '', actionType = '') {
  const raw = String(relation || '').trim()
  if (raw && !GENERIC_RELATION.test(raw)) {
    if (/[\u4e00-\u9fff]/.test(raw)) return raw
    const mapped = humanizeAction(raw)
    if (mapped && !GENERIC_RELATION.test(mapped)) return mapped
  }
  const fromAction = ACTION_VERB[String(actionType || '').toLowerCase()]
  if (fromAction) return fromAction
  return verbFromRole(nodeSearchText(source) || nodeSearchText(target))
}

export function describeInteraction(source, target, relation = '', actionType = '') {
  const verb = interactionVerb(source, target, relation, actionType)
  const sourceName = (typeof source === 'string' ? source : (source?.label || source?.name || '对方'))
  const targetName = (typeof target === 'string' ? target : (target?.label || target?.name || '对方'))
  return {
    verb,
    toContent: outgoingLine(verb, targetName),
    fromContent: incomingLine(verb, sourceName),
  }
}

function outgoingLine(verb, other) {
  const lines = {
    发布: `把源头内容发给${other}`,
    转发: `把内容转发给${other}`,
    扩散: `把话题扩散给${other}`,
    煽动: `向${other}放大争议`,
    澄清: `向${other}澄清事实`,
    通报: `向${other}通报官方说明`,
    报道: `向${other}报道此事`,
    提醒: `提醒${other}先核实再传播`,
    讨论: `与${other}讨论此事`,
    告知: `把消息告知${other}`,
    施压: `向${other}继续施压`,
    求助: `向${other}求助核验`,
    劝阻: `劝${other}停下来核实`,
    核实: `向${other}核实身份或账户`,
    处置: `限制内容继续传向${other}`,
    评论: `向${other}评论回应`,
    关注: `关注${other}`,
    沟通: `与${other}沟通此事`,
  }
  return lines[verb] || `向${other}${verb}`
}

function incomingLine(verb, other) {
  const lines = {
    发布: `从${other}处看到首发内容`,
    转发: `从${other}处接到转发`,
    扩散: `被${other}扩散触达`,
    煽动: `被${other}带入争议`,
    澄清: `收到${other}的澄清`,
    通报: `收到${other}的官方通报`,
    报道: `看到${other}的报道`,
    提醒: `被${other}提醒核实`,
    讨论: `与${other}沟通讨论`,
    告知: `被${other}告知此事`,
    施压: `受到${other}的施压`,
    求助: `${other}向这边求助`,
    劝阻: `被${other}劝阻`,
    核实: `配合${other}核实`,
    处置: `内容被${other}处置`,
    评论: `收到${other}的评论`,
    沟通: `与${other}沟通此事`,
  }
  return lines[verb] || `从${other}接到「${verb}」`
}
