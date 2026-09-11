const PLATFORMS = ['小红书', '抖音', '微博', '知乎', '多平台聚合', '跨平台', '微信', 'QQ', '短信', '电话']

const WINDOW = {
  '6h': '最近 6 小时',
  '24h': '最近 24 小时',
  '7d': '最近 7 天',
}

const PUBLIC = {
  微博: {
    lens: '传播主要靠转发链、热搜和超话，一条原帖被包装后会迅速离开现场。',
    actions: [
      '先核对本条微博和转发链，而不是只看截图。',
      '官方说明应发在原帖评论置顶，并同步长文。',
      '热搜词和超话标题若已变形，要单独标注「已确认 / 仍在核实」。',
    ],
  },
  抖音: {
    lens: '传播主要靠推荐页和几秒钩子，评论置顶会比长文先被刷到。',
    actions: [
      '先看同一条作品的推荐封面、文案和置顶评论。',
      '澄清要用短视频或原作品置顶评论回到同一条。',
      '同款 BGM、话题标签若在带跑说法，要和原作品分开核对。',
    ],
  },
  小红书: {
    lens: '传播主要靠封面、标题和搜索词，很多人没看完正文就会转。',
    actions: [
      '先核对笔记封面、标题和标签，不要只引用最冲的一句。',
      '澄清要发能搜到的笔记，覆盖同一批标签。',
      '把种草口吻和能核对的价格、时间、出处拆开写。',
    ],
  },
  知乎: {
    lens: '传播主要靠高赞回答和问题页，立场帖容易被当成论证。',
    actions: [
      '先看原问题下的高赞回答是在举证还是在带节奏。',
      '澄清应发在原问题下，并标明来源。',
      '把仍待核实的部分单独标出。',
    ],
  },
  多平台聚合: {
    lens: '同一套说法会在不同平台换成各自的体裁，不能假设已经传成同一版本。',
    actions: [
      '先分别核对各平台主帖，不要混成一条。',
      '每个平台用该平台习惯的澄清方式，再交叉核验。',
      '缺来源的版本单独标成未证实。',
    ],
  },
}

PUBLIC['跨平台'] = PUBLIC['多平台聚合']

const FRAUD = {
  微信: '回到微信官方入口或公开电话核对，不要按对方给的搜索词走。',
  QQ: '回到 QQ 官方客服或机构公开账号核对，不要在临时会话里继续。',
  短信: '回拨官方号码或打开官方 App，不要点短信里的链接。',
  电话: '挂断后用官方公开号码回拨，不要按对方要求转接到第二个电话。',
}

export function windowLabel(value) {
  return WINDOW[value] || value || ''
}

export function detectPlatform(text) {
  const labeled = String(text || '').match(/\[(?:平台|渠道)\]\s*([^\n]+)/)
  if (labeled) return labeled[1].trim()
  const src = String(text || '')
  return PLATFORMS.find((name) => src.includes(name)) || ''
}

export function detectTimeWindow(text) {
  const labeled = String(text || '').match(/\[时间窗口\]\s*([^\n]+)/)
  return labeled ? labeled[1].trim() : ''
}

export function publicOpinionLens(platform) {
  return PUBLIC[platform] || {
    lens: '先按该平台真实可见的主帖来核对，不要套用别的平台的传播方式。',
    actions: ['先补来源，再决定转不转。', '官方回应要标出「已确认 / 仍在核实」。'],
  }
}

export function channelLens(channel) {
  return publicOpinionLens(channel)
}

export function fraudPlatformAction(platform) {
  return FRAUD[platform] || ''
}

export function composePublicOpinionText(form = {}) {
  const parts = []
  if (form.platform) parts.push(`[平台]${form.platform}`)
  if (form.topic) parts.push(`[话题]${form.topic}`)
  const window = windowLabel(form.timeWindow)
  if (window) parts.push(`[时间窗口]${window}`)
  if (form.samples) parts.push(`[样本]\n${form.samples}`)
  return parts.join('\n')
}

export function composeEventPropagationText(form = {}) {
  const parts = []
  if (form.channel) parts.push(`[渠道]${form.channel}`)
  if (form.eventName) parts.push(`[事件]${form.eventName}`)
  if (form.origin) parts.push(`[起点]${form.origin}`)
  const window = windowLabel(form.timeWindow)
  if (window) parts.push(`[时间窗口]${window}`)
  if (form.nodes) parts.push(`[节点描述]\n${form.nodes}`)
  return parts.join('\n')
}

export function composeFraudText(form = {}) {
  const parts = []
  if (form.platform) parts.push(`[平台]${form.platform}`)
  if (form.conversation) parts.push(form.conversation)
  return parts.join('\n')
}
