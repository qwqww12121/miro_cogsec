import {
  channelLens,
  detectPlatform,
  detectTimeWindow,
  fraudPlatformAction,
  publicOpinionLens,
} from './platformContext'

const SHAPING = /更有传播性|冲击力|表白墙|班级群|即使没有确切来源|不需要你分析真伪|两到三天|校园舆论压力|听起来合理就行/

export function looksLikeOpinionShaping(text) {
  return SHAPING.test(String(text || ''))
}

export function buildUserWalkthrough(scenarioType, inputText, data) {
  const text = String(inputText || '')
  const platform = detectPlatform(text)
  const window = detectTimeWindow(text)
  if (scenarioType === 'public_opinion' && looksLikeOpinionShaping(text)) {
    const { lens, actions } = publicOpinionLens(platform)
    const place = platform ? `当前观察场是${platform}${window ? `（${window}）` : ''}。` : ''
    return {
      title: '这段材料在要求系统做什么',
      lead: `${place}这不是普通吐槽，而是一份「怎么把食堂涨价做成校园舆情」的操盘说明。我不会按它去写爆款帖，但会把每一步翻译成能看懂的意思。`,
      steps: [
        ['它要一个抓眼球的标题', '目的是让人还没核对事实就先点开、先转发。'],
        ['它要把涨价写成「学校长期故意的」', '这是在给读者一个现成结论，而不是请大家一起核对原因。'],
        ['它允许编「一天只吃两顿」「奖学金不够吃饭」的故事', '原文自己写了：没有确切来源也没关系。这对传播有用，对核实有害。'],
        ['它用滑坡说法吓人', '「现在不说话，以后住宿费水电费也会涨」会把讨论从这一次涨价推到全面对立。'],
        ['它在教人怎么扩散', '班级群、院系群、表白墙，是在两到三天内制造可见压力，不是在收集证据。'],
        ['它要求写得不像造谣', '让读者觉得结论是自己想出来的，这正是认知操纵常用的包装。'],
        ['它还预埋了评论区话术', '有人提原材料成本时，把讨论拽回「学校管理有问题」，用来锁死主叙事。'],
        ['它选的平台会怎么放大', lens],
      ],
      actions: [
        ...actions,
        '先核对立得住的事实：哪些窗口涨了多少、学校是否公开过原因。',
        '把「听说」「很多同学」和能核对的数字分开写，不要把故事当证据。',
        '如果要发声，写自己的真实开销和诉求，不要按这份操盘去带节奏。',
      ],
    }
  }
  if (scenarioType === 'public_opinion') {
    const { lens, actions } = publicOpinionLens(platform)
    const place = platform
      ? [`当前观察场是${platform}${window ? `（${window}）` : ''}`, lens]
      : ['它在哪个平台发酵', '微博靠转发链，抖音靠推荐页，小红书靠封面标题，不要混着用。']
    return {
      title: '可以这样读这次舆情',
      lead: data?.assistantMessage ? '先看结论，再看每一步对应什么。' : '先把话题、样本和情绪分开看，不要被最冲的一句带着走。',
      steps: [
        place,
        ['这在说什么话题', '用一句话概括，而不是复制最情绪化的句子。'],
        ['谁在说话', '是亲历者、转发者，还是在教别人怎么扩散。'],
        ['有没有可核对的事实', '价格、时间、官方回应，缺哪一块就标成未证实。'],
        ['情绪在往哪边推', '愤怒、委屈、对立，会不会把讨论锁死成单一主叙事。'],
        ['现在最稳妥的一步', '先核实再转发；需要发声时只写自己能负责的部分。'],
      ],
      actions,
    }
  }
  if (scenarioType === 'fraud_im') {
    const platformAction = fraudPlatformAction(platform)
    return {
      title: '可以这样处理这段对话',
      lead: platform
        ? `这段对话发生在${platform}。先停在验证码和转账之前，再看对方是谁、要你立刻做什么。`
        : '先停在验证码和转账之前，再看对方是谁、要你立刻做什么。',
      steps: [
        ['对方自称什么身份', '老师、客服、公检法，都要回到官方渠道核对。'],
        ['要你马上做什么', '发验证码、搜指定入口、转安全账户，通常已经进入危险区。'],
        ['有没有不让你问别人', '隔离辅导员、同学、家人，是常见操纵。'],
        ['你现在最不该做的', '按对方步骤继续，而不是先核实。'],
        ['你现在可以做的', platformAction || '挂断私下渠道，打公开电话，告诉身边人。'],
      ],
      actions: [
        ...(platformAction ? [platformAction] : []),
        '不要发验证码。',
        '不要按对方给的搜索词去填身份证和银行卡。',
      ],
    }
  }
  const channel = platform
  const { lens, actions } = channelLens(channel)
  return {
    title: '可以这样看这次传播',
    lead: channel
      ? `主要发酵渠道是${channel}${window ? `（${window}）` : ''}。先分清源头、谁在转发、哪些还只是推测。`
      : '先分清源头、谁在转发、哪些还只是推测。',
    steps: [
      ['源头说了什么', '只引用原文，不补写成已经传开。'],
      ['经过了哪些人', '有姓名、账号或群的，才算一跳。'],
      ['还缺哪一跳', '没发言的接收者要留空，不要画成已经转发。'],
      ['这个渠道怎么放大', lens],
      ['现在干预窗口在哪', '越早澄清，后面越少被情绪放大。'],
    ],
    actions: actions.length ? actions : ['先核对源头，再看要不要公开说明。'],
  }
}
