const ROLE_PERSONA = {
  student_kol: {
    label: '学生意见领袖',
    who: '对应校园里粉丝较多、爱转发评论的学生，代表意见领袖这一社会部分。',
  },
  ordinary_student: {
    label: '普通学生',
    who: '对应普通在校学生，代表一般校园受众。',
  },
  teacher: {
    label: '老师',
    who: '对应高校教师，代表会先核实再传播的教育工作者。',
  },
  school_official: {
    label: '校方',
    who: '对应学校官方账号，代表校方权威信息源。',
  },
  media_observer: {
    label: '媒体观察者',
    who: '对应媒体观察员或记者，代表专业传播机构。',
  },
  anonymous_amplifier: {
    label: '匿名放大器',
    who: '对应匿名起哄账号，代表网络里的情绪放大器。',
  },
  original_poster: {
    label: '首发者',
    who: '对应这条信息的首发账号，代表源头爆料或当事人。',
  },
  repost_kol: {
    label: '转发意见领袖',
    who: '对应有影响力的转发大V，代表社交平台意见领袖。',
  },
  ordinary_viewer: {
    label: '普通网民',
    who: '对应普通围观网民，代表一般公众。',
  },
  fact_checker: {
    label: '事实核查员',
    who: '对应事实核查组织或核验人员，代表社会里的纠偏力量。',
  },
  official_responder: {
    label: '官方回应',
    who: '对应政府或权威机构发言人，代表官方处置方。',
  },
  controversy_amplifier: {
    label: '争议放大器',
    who: '对应爱制造争议的账号，代表煽动扩散这一部分。',
  },
  victim: {
    label: '受害人',
    who: '对应被诱导的当事人，代表需要保护的这一侧。',
  },
  attacker: {
    label: '施害者',
    who: '对应继续施压的对方，代表攻击这一侧。',
  },
  family_member: {
    label: '家人',
    who: '对应受害人亲友，代表身边可求助的人。',
  },
  platform_moderator: {
    label: '平台审核',
    who: '对应平台审核员，代表内容治理这一部分。',
  },
  police_or_bank: {
    label: '警方或银行',
    who: '对应警方或银行工作人员，代表可核验的权威渠道。',
  },
  fork: {
    label: '分叉点',
    who: '这不是某个人。它代表对照开始的分叉：接下来分别模拟两种选择。',
  },
  pathA: {
    label: '攻击路径',
    who: '这不是某个人。它代表「继续被诱导」这一整条路上的行为。',
  },
  pathB: {
    label: '防御路径',
    who: '这不是某个人。它代表「及时止损」这一整条路上的行为。',
  },
  turn: {
    label: '转折点',
    who: '这不是某个人。它代表两条路比完之后的差异。',
  },
}

const TOKEN_TO_ROLE = [
  ['controversyamplifier', 'controversy_amplifier'],
  ['controversy_amplifier', 'controversy_amplifier'],
  ['officialresponder', 'official_responder'],
  ['official_responder', 'official_responder'],
  ['officialrespond', 'official_responder'],
  ['anonymousamplifier', 'anonymous_amplifier'],
  ['anonymous_amplifier', 'anonymous_amplifier'],
  ['ordinarystudent', 'ordinary_student'],
  ['ordinary_student', 'ordinary_student'],
  ['ordinaryviewer', 'ordinary_viewer'],
  ['ordinary_viewer', 'ordinary_viewer'],
  ['originalposter', 'original_poster'],
  ['original_poster', 'original_poster'],
  ['originalpost', 'original_poster'],
  ['schoolofficial', 'school_official'],
  ['school_official', 'school_official'],
  ['mediaobserver', 'media_observer'],
  ['media_observer', 'media_observer'],
  ['platformmoderator', 'platform_moderator'],
  ['platform_moderator', 'platform_moderator'],
  ['familymember', 'family_member'],
  ['family_member', 'family_member'],
  ['policeorbank', 'police_or_bank'],
  ['police_or_bank', 'police_or_bank'],
  ['factchecker', 'fact_checker'],
  ['fact_checker', 'fact_checker'],
  ['factchecke', 'fact_checker'],
  ['studentkol', 'student_kol'],
  ['student_kol', 'student_kol'],
  ['repostkol', 'repost_kol'],
  ['repost_kol', 'repost_kol'],
  ['controversy', 'controversy_amplifier'],
  ['amplifier', 'anonymous_amplifier'],
  ['responder', 'official_responder'],
  ['observer', 'media_observer'],
  ['official', 'official_responder'],
  ['teacher', 'teacher'],
  ['student', 'ordinary_student'],
  ['media', 'media_observer'],
  ['school', 'school_official'],
  ['victim', 'victim'],
  ['attacker', 'attacker'],
  ['repost', 'repost_kol'],
  ['kol', 'repost_kol'],
]

const WORD_ZH = {
  student: '学生',
  kol: '意见领袖',
  media: '媒体',
  observer: '观察者',
  teacher: '老师',
  school: '校方',
  official: '官方',
  amplifier: '放大器',
  source: '源头',
  spreader: '扩散者',
  victim: '受害人',
  adversary: '对抗者',
  actor: '',
  admin: '管理员',
  responder: '处置方',
  community: '社群',
  friend: '好友',
  fact: '事实',
  checker: '核查员',
  factchecker: '事实核查员',
  original: '首发',
  poster: '者',
  originalpost: '首发者',
  ordinary: '普通',
  viewer: '网民',
  controversy: '争议',
  repost: '转发',
  respond: '回应',
}

function compact(value) {
  return String(value || '').toLowerCase().replace(/[^a-z0-9\u4e00-\u9fff]/g, '')
}

export function detectRole(raw) {
  const text = String(raw || '').trim()
  if (!text) return ''
  const key = text.replace(/[_\-\s]+\d+$/g, '').replace(/[\s-]+/g, '_')
  if (ROLE_PERSONA[key]) return key
  const smashed = compact(key)
  if (ROLE_PERSONA[smashed]) return smashed
  const hit = TOKEN_TO_ROLE.find(([token]) => smashed === token || smashed.startsWith(token))
  return hit ? hit[1] : ''
}

export function chineseAgentLabel(raw, fallback = '代理') {
  const text = String(raw || '').trim()
  if (!text) return fallback
  const role = detectRole(text)
  if (role && ROLE_PERSONA[role]) return ROLE_PERSONA[role].label
  if (/[\u4e00-\u9fff]/.test(text) && !/[A-Za-z]{3,}/.test(text)) return text.replace(/[_\-\s]+\d+$/g, '').slice(0, 8)
  const smashed = compact(text)
  const found = []
  let rest = smashed
  const tokens = TOKEN_TO_ROLE.slice().sort((a, b) => b[0].length - a[0].length)
  while (rest) {
    const hit = tokens.find(([token]) => rest.startsWith(token))
    if (!hit) break
    if (!found.includes(hit[1])) found.push(hit[1])
    rest = rest.slice(hit[0].length)
  }
  if (found.length) {
    return [...new Set(found.map((id) => ROLE_PERSONA[id]?.label).filter(Boolean))].join('·').slice(0, 10)
  }
  const words = text
    .replace(/[_\-\s]+\d+$/g, '')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .replace(/[_-]+/g, ' ')
    .split(/\s+/)
    .map((part) => WORD_ZH[part.toLowerCase()] ?? (/[\u4e00-\u9fff]/.test(part) ? part : ''))
    .filter(Boolean)
    .join('')
  return (words || fallback).slice(0, 8)
}

export function describeAgentWho(raw, extra = '') {
  const role = detectRole(raw) || detectRole(extra)
  if (role && ROLE_PERSONA[role]) {
    return `汉语名称「${ROLE_PERSONA[role].label}」${ROLE_PERSONA[role].who}`
  }
  const label = chineseAgentLabel(raw || extra)
  if (!label || label === '代理') return '这是传播网里的一个代理节点，代表参与话题流动的社会角色。'
  return `汉语名称「${label}」对应仿真里的这一类社会角色，用来看这类人会如何接到或传出信息。`
}

export function resolveAgentPersona(node = {}) {
  const raw = [node.role, node.type, node.label, node.name, node.id].filter(Boolean).join(' ')
  const role = detectRole(node.role) || detectRole(node.type) || detectRole(node.id) || detectRole(node.label) || detectRole(raw)
  const label = (role && ROLE_PERSONA[role]?.label) || chineseAgentLabel(node.label || node.name || node.id || node.role)
  const who = describeAgentWho(role || node.role || node.label, node.id)
  return { role, label, who }
}
