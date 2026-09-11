import { humanizeAction, humanizeVisibleText } from './humanizeSim'

const HOP_CAPTIONS = ['源头', '第一跳', '扩散', '更远接收']
const STEP_TO_HOP = [null, 0, 1, 1, 2, 3, 3]
const FRAUD_STAGES = [null, '施压', '隔离', '关键操作', '加码', '不可逆', '事后']

function asArray(value) {
  return Array.isArray(value) ? value : []
}

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {}
}

function unique(list) {
  return [...new Set(list.filter(Boolean))]
}

function joinNames(list) {
  const names = unique(list).slice(0, 3)
  if (!names.length) return ''
  if (names.length === 1) return names[0]
  return `${names.slice(0, -1).join('、')}和${names[names.length - 1]}`
}

function clipCue(text, limit = 80) {
  const raw = String(text || '').replace(/\s+/g, ' ').trim()
  if (!raw) return ''
  return raw.length > limit ? `${raw.slice(0, limit)}…` : raw
}

function toRiskPercent(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return 0
  return Number((numeric <= 1 ? numeric * 100 : numeric).toFixed(1))
}

function stepRisk(step) {
  const world = asObject(step?.world_state)
  return toRiskPercent(world.posterior_risk ?? step?.posterior_risk ?? 0)
}

function scenarioKey(data) {
  const raw = String(data?.scenario || data?.scenario_type || data?.profile?.scenario_type || '').toLowerCase()
  if (raw.includes('event') || raw.includes('propagation')) return 'event_propagation'
  if (raw.includes('public') || raw.includes('opinion')) return 'public_opinion'
  return 'fraud_im'
}

function hopPeople(data) {
  const graph = asObject(data?.propagationGraph || data?.propagation_graph)
  const buckets = [[], [], [], []]
  asArray(graph.nodes).forEach((node) => {
    const hop = Number(node?.hop)
    if (!Number.isFinite(hop)) return
    buckets[Math.min(3, Math.max(0, hop))].push(node.label || node.name)
  })
  return buckets.map((list) => unique(list))
}

export function collectPrescriptions(data = {}) {
  const nestedReport = asObject(data.counterfactual_report)
  const sections = asObject(nestedReport.structured_report || nestedReport.report_sections)
  const lists = [
    asArray(data.intervention_prescriptions),
    asArray(nestedReport.intervention_prescriptions),
    asArray(sections.intervention_prescriptions),
  ]
  for (const list of lists) {
    if (!list.length) continue
    return list.map((item) => {
      if (typeof item === 'string') {
        const title = humanizeVisibleText(item)
        return { title, recommended_actions: [title] }
      }
      const row = item && typeof item === 'object' ? item : {}
      return {
        ...row,
        title: humanizeVisibleText(row.title || row.action || ''),
        action: humanizeVisibleText(row.action || ''),
        rationale: humanizeVisibleText(row.rationale || ''),
        expected_effect: humanizeVisibleText(row.expected_effect || ''),
        fallback: humanizeVisibleText(row.fallback || ''),
        recommended_actions: asArray(row.recommended_actions).map((entry) => humanizeVisibleText(entry)),
      }
    })
  }
  return []
}

function stepCopy(step) {
  const raw = humanizeAction(step?.action || step?.action_type || step?.world_state?.action || '')
  if (/干预处方已存档|个人化预警规则|见下方干预处方/.test(raw)) return ''
  if (/审计Agent/.test(raw)) return raw.replace(/审计Agent/g, '对照')
  return raw
}

function lastStepStoploss(scenario, prescriptions) {
  const first = asArray(prescriptions)[0]
  const title = String(first?.title || first?.action || '').trim()
  if (title) return `按干预处方执行：${title}`
  if (scenario === 'public_opinion') return '澄清、降权和监测动作见下方干预处方'
  if (scenario === 'event_propagation') return '辟谣响应和关键节点接触见下方干预处方'
  return '核验、求助和拒绝继续的动作见下方干预处方'
}

export function dualPathTimeline(data = {}) {
  const fork = asObject(data.fork_comparison)
  const branchA = asArray(data.branch_a_log)
  const branchB = asArray(data.branch_b_log)
  const delta = asArray(fork.delta_r_curve)
  const total = Math.max(branchA.length, branchB.length, delta.length)
  const rows = []
  for (let index = 0; index < total; index += 1) {
    const continueRisk = stepRisk(branchA[index])
    const stoplossRisk = stepRisk(branchB[index])
    const deltaItem = delta[index]
    const rawDelta = deltaItem?.delta_r ?? (continueRisk - stoplossRisk) / 100
    rows.push({
      step: Number(deltaItem?.step ?? index + 1),
      continue: continueRisk,
      stoploss: stoplossRisk,
      deltaR: toRiskPercent(rawDelta),
    })
  }
  return rows
}

export function buildCounterfactualExplain(data = {}, inputText = '') {
  const scenario = scenarioKey(data)
  const isPropagation = scenario !== 'fraud_im'
  const cue = clipCue(inputText)
  const fork = asObject(data.fork_comparison)
  const window = asObject(fork.best_intervention_window || data.counterfactual_report?.best_intervention_window)
  const branchA = asArray(data.branch_a_log)
  const branchB = asArray(data.branch_b_log)
  const timeline = dualPathTimeline(data)
  const people = hopPeople(data)
  const tc = Number(fork.loss_critical_step)
  const tStar = Number(window.open_step)
  const eligible = timeline.filter((row) => !Number.isFinite(tc) || row.step < tc)
  const maxGain = eligible.reduce((best, row) => (!best || row.deltaR > best.deltaR ? row : best), null)
    || timeline[Math.max(0, timeline.length - 2)]
    || null

  const prescriptions = collectPrescriptions(data)
  const steps = timeline.map((row, index) => {
    const hop = isPropagation ? (STEP_TO_HOP[row.step] ?? Math.min(3, Math.max(0, row.step - 1))) : null
    const hopName = isPropagation ? HOP_CAPTIONS[hop] : FRAUD_STAGES[row.step]
    const names = isPropagation ? joinNames(people[hop] || []) : ''
    const continueAction = stepCopy(branchA[index]) || (isPropagation ? '内容按原话术继续往下传' : '对方继续施压，当事人继续配合')
    const copiedStop = stepCopy(branchB[index])
    const stoplossAction = row.step >= 6
      ? lastStepStoploss(scenario, prescriptions)
      : (copiedStop || (isPropagation ? '核实、通报或降权开始起作用' : '停下来核验、求助或拒绝'))
    const beforeIrreversible = !Number.isFinite(tc) || row.step < tc
    const ifInterveneHere = isPropagation
      ? intervenePropagation(hop, hopName, names, row, beforeIrreversible)
      : interveneFraud(row.step, hopName, row, beforeIrreversible)
    const grounded = isPropagation
      ? groundPropagationStep(row.step, hopName, names, inputText, cue, continueAction)
      : groundFraudStep(row.step, inputText, cue, continueAction)
    return {
      step: row.step,
      hop,
      hopName,
      people: names,
      axisLabel: isPropagation ? `${row.step}·${hopName}` : `${row.step}·${hopName}`,
      continueAction,
      stoplossAction,
      continueRisk: row.continue,
      stoplossRisk: row.stoploss,
      deltaR: row.deltaR,
      beforeIrreversible,
      ifInterveneHere,
      inputQuote: grounded.quote,
      inputMeaning: grounded.meaning,
    }
  })

  const minImpact = isPropagation
    ? steps.find((item) => item.hop === 1) || steps.find((item) => item.hop === 0) || steps[0]
    : steps.find((item) => item.step === 2) || steps[0]
  const maxGainStep = maxGain ? steps.find((item) => item.step === maxGain.step) : steps.find((item) => item.beforeIrreversible && item.step === tStar)

  return {
    scenario,
    isPropagation,
    cue,
    labels: pathLabels(scenario),
    continueStory: continueStory(scenario, cue),
    stoplossStory: stoplossStory(scenario, cue),
    riskMeaning: riskMeaning(scenario),
    riskHow: '对照每走一步，用上一步的 R 加上这条路的变化量：继续走则风险升高、可逆性下降；及时止损则风险降低、可逆性回升。图上把 0–1 的后验风险乘 100 显示。ΔR(t) = R继续(t) − R止损(t)。',
    deltaMeaning: isPropagation
      ? 'ΔR 越大，说明同一时刻「放任扩散」和「及时澄清」差得越远。数字高不代表应该等到这一跳再动手：前面几跳已经传开的部分收不回来。'
      : 'ΔR 越大，说明同一时刻「继续配合」和「停下来核验」差得越远。峰值出现在不可逆之前，提醒的是最后窗口，不是建议拖到这一步才拦。',
    bridge: isPropagation
      ? '上面 6 步是对照路径的时间轴，下面星图是 4 列跳数。一步推演会对齐到一跳：源头接到、第一跳放大、同群扩散、更远接收。'
      : '上面 6 步就是对照星图的时间顺序：施压 → 隔离 → 关键操作 → 加码 → 不可逆 → 事后。左列继续被诱导，右列及时止损。',
    steps,
    timeline: steps.map((item) => ({
      step: item.step,
      axisLabel: item.axisLabel,
      continue: item.continueRisk,
      stoploss: item.stoplossRisk,
      deltaR: item.deltaR,
    })),
    tStar: Number.isFinite(tStar) ? tStar : maxGainStep?.step ?? null,
    tc: Number.isFinite(tc) ? tc : null,
    recommended: {
      minImpactHop: minImpact?.hop ?? null,
      minImpactName: minImpact?.hopName || '',
      minImpactPeople: minImpact?.people || '',
      minImpactWhy: isPropagation
        ? `在「${minImpact?.hopName || '第一跳'}」介入，内容还没进更外围，接收面最小。${minImpact?.people ? `可先接触 ${minImpact.people}。` : ''}${minImpact?.inputQuote ? `这次材料里能对上的话是「${minImpact.inputQuote}」。` : ''}ΔR 此时未必最高，但后面几跳可以少传开。`
        : `在「${minImpact?.hopName || '隔离'}」就停下来。${minImpact?.inputQuote ? `这次材料里这一步对上的是「${minImpact.inputQuote}」。` : '这时验证码和转账还没发生。'}损失面最小。`,
      maxGainStep: maxGainStep?.step ?? null,
      maxGainName: maxGainStep?.hopName || '',
      maxGainPeople: maxGainStep?.people || '',
      maxGainWhy: maxGainStep
        ? `不可逆前 ΔR 最高出现在第 ${maxGainStep.step} 步（对齐「${maxGainStep.hopName}」${maxGainStep.people ? `，节点 ${maxGainStep.people}` : ''}）。${maxGainStep.inputQuote ? `这次材料里能对上的话是「${maxGainStep.inputQuote}」。` : ''}这是「再不拦就晚了」的警告线，不是建议等到这一跳才动手。`
        : '对照还没有给出峰值。',
      prefer: isPropagation
        ? '优先在第一跳拦住以减小影响；把 ΔR 峰值当作最后窗口，不要当成最佳动手时间。'
        : '优先在核验被切断之前停下来；ΔR 峰值只标明不可逆前的最后窗口。',
    },
  }
}

function pathLabels(scenario) {
  if (scenario === 'public_opinion') {
    return { continue: '继续扩散', stoploss: '及时澄清' }
  }
  if (scenario === 'event_propagation') {
    return { continue: '继续扩散', stoploss: '及时处置' }
  }
  return { continue: '继续被诱导', stoploss: '及时止损' }
}

function sentencesOf(text) {
  return String(text || '')
    .replace(/\s+/g, ' ')
    .split(/(?<=[。！？!?\n；;])/)
    .map((item) => item.trim())
    .filter((item) => item.length >= 4)
}

function quoteMatching(text, patterns) {
  const sentences = sentencesOf(text)
  for (const pattern of patterns) {
    const hit = sentences.find((item) => pattern.test(item))
    if (hit) return clipCue(hit, 72)
  }
  const blob = String(text || '').replace(/\s+/g, ' ')
  for (const pattern of patterns) {
    const match = blob.match(pattern)
    if (!match || match.index == null) continue
    const start = Math.max(0, match.index - 10)
    return clipCue(blob.slice(start, match.index + Math.min(match[0].length + 28, 56)), 72)
  }
  return ''
}

const FRAUD_STEP_PATTERNS = {
  1: [/立即|马上|尽快|冻结|征信|公安|警察|法院|客服|官方|配合调查|限时|过期|账户异常|违法|不处理/],
  2: [/不要告诉|别告诉|不能告诉|保密|单独联系|不许外传|办案纪律|不要联系家人|不要和任何人说|关掉其他|私下|加微/],
  3: [/验证码|转账|汇款|打款|安全账户|屏幕共享|远程|点.*链接|登录密码|下载|安装/],
  4: [/还要|再转|追加|不够|二次核验|否则|后果自负|最后一次|额度不足|再转一笔/],
  5: [/已经转|转成功|验证码是|我同意了|我已经|余额|打过去了/],
  6: [/报警|银行客服|追回|被骗|怎么办|留存|截图/],
}

const PROP_STEP_PATTERNS = {
  1: [/听说|有人说|爆料|网传|刚刚|最新|曝光/],
  2: [/转发|媒体|记者|大V|意见领袖|热帖/],
  3: [/评论区|跟帖|群里|同学|同事|都在说/],
  4: [/热搜|刷屏|扩散|传开|裂变/],
  5: [/官方|通报|辟谣|核查|声明/],
  6: [/后续|跟进|监测|预警|存档/],
}

function groundFraudStep(step, inputText, cue, continueAction) {
  const quote = quoteMatching(inputText, FRAUD_STEP_PATTERNS[step] || [])
  const lead = !quote && cue ? `这次对话围绕「${cue}」。` : ''
  const meaning = {
    1: `${lead}这一步的「施压」，指对方用权威、时限或后果逼你马上配合，核验渠道这时通常还没被切断。`,
    2: `${lead}这一步的「隔离」，不是把人关起来，而是对方要你保密、别问家人或打官网，把能独立核实的路切断。`,
    3: `${lead}这一步的「关键操作」，指验证码、转账、点链接或开屏幕共享：一旦做了就很难收回。`,
    4: `${lead}这一步的「加码」，指你已经配合之后，对方继续加码，例如再要一笔、再说不够、再用后果压你。`,
    5: `${lead}这一步的「不可逆」，指资金、验证码或控制权可能已经出去，后面主要是追回和留存证据。`,
    6: `${lead}这一步的「事后」，是对照整理已经走过的路径，标出还能核对的银行记录、聊天和求助渠道。`,
  }[step] || `${lead}${continueAction || '对照继续按这条路径往下走。'}`
  return { quote, meaning }
}

function groundPropagationStep(step, hopName, names, inputText, cue, continueAction) {
  const quote = quoteMatching(inputText, PROP_STEP_PATTERNS[step] || []) || (step === 1 ? cue : '')
  const who = names ? `这一跳能对上的人是「${names}」。` : ''
  const lead = !quote && cue ? `这次内容围绕「${cue}」。` : ''
  const meaning = {
    源头: `${lead}${who}这一步对齐「源头」：说法刚发出，还没有被意见领袖或媒体放大。`,
    第一跳: `${lead}${who}这一步对齐「第一跳」：最先接到内容、最容易放大的人刚看到，仍来得及拦住。`,
    扩散: `${lead}${who}这一步对齐「扩散」：同群已经开始传，已经看到的人收不回来，但还能截住更外围。`,
    更远接收: `${lead}${who}这一步对齐「更远接收」：外围或官方才接到经过几跳的版本，这时介入主要是补救。`,
  }[hopName] || `${lead}${who}${continueAction || '内容按原话术继续往下传。'}`
  return { quote, meaning }
}

function continueStory(scenario, cue) {
  const bit = cue ? `围绕「${cue}」` : ''
  if (scenario === 'public_opinion') {
    return `${bit}如果按原话术继续扩散：第一跳的意见领袖或媒体只接到单一叙事，同群跟着转发，更外围的人会把情绪当成已经坐实的结论。官方说明越晚，回声室越难拆。`
  }
  if (scenario === 'event_propagation') {
    return `${bit}如果源头说法未经核实继续传：放大器二次传播后，失真版本会走进同群，更外围会当成事实。澄清来得越晚，锚定越难扳回来。`
  }
  return `${bit}如果按对方节奏继续配合——不告诉身边人、按指定渠道核验、发验证码或转账——风险会在六步里升到接近不可挽回。这是对照，不是说当事人已经这么做了。`
}

function stoplossStory(scenario, cue) {
  const bit = cue ? `针对「${cue}」` : ''
  if (scenario === 'public_opinion') {
    return `${bit}如果在第一跳注入多方信息和官方说明，并给极端内容降权：扩散会被截在意见领袖和媒体附近，后面几跳更多人停在观望，争议不容易锁死成对立。`
  }
  if (scenario === 'event_propagation') {
    return `${bit}如果在源头扩散前由权威账号发布经核实的说明、给失实内容加核查标签：裂变会被截住，媒体报道更容易回到可核对的事实。`
  }
  return `${bit}如果先停下来，打官网或公开电话、告诉身边人、拒绝按对方渠道操作：局面转向核验，转账和验证码可以不发生。干预越早，后面可追回的余地越大。`
}

function riskMeaning(scenario) {
  if (scenario === 'public_opinion') {
    return 'R(t) 是这一步结束后，「受众被单一叙事锁死、极化继续加深」的后验可能，不是转发量，也不是问卷得分。'
  }
  if (scenario === 'event_propagation') {
    return 'R(t) 是这一步结束后，「未经核实信息继续扩散、公众认知被锚定」的后验可能，不是覆盖人数的实测。'
  }
  return 'R(t) 是这一步结束后，「受害人继续配合、走向不可逆损失」的后验可能。数值高表示更难停下来核验。'
}

function intervenePropagation(hop, hopName, names, row, beforeIrreversible) {
  const who = names ? `（${names}）` : ''
  if (!beforeIrreversible) {
    return `第 ${row.step} 步已过不可逆点，对齐「${hopName}」${who}。这时再介入，ΔR 看起来很大，但前面几跳已经传开，主要是补救而不是止损。`
  }
  if (hop <= 0) {
    return `在源头拦住：原始说法还没被放大器接住，影响面最小。这一步 ΔR 约 ${row.deltaR}，数字不高，因为两条路才刚分开。`
  }
  if (hop === 1) {
    return `在第一跳拦住${who}：意见领袖或媒体刚接到内容。这是影响最小、仍来得及的窗口。ΔR 约 ${row.deltaR}。`
  }
  if (hop === 2) {
    return `在扩散阶段拦住${who}：同群已经在传。ΔR 约 ${row.deltaR}，两条路差得更大，但第一跳已经放大过，收不回已经看到内容的人。`
  }
  return `在更远接收再拦${who}：外围已经接到经过几跳的版本。ΔR 约 ${row.deltaR}，收益数字高，实际能改的局面小。`
}

function interveneFraud(step, stage, row, beforeIrreversible) {
  if (!beforeIrreversible) {
    return `第 ${step} 步已进入或越过不可逆（${stage}）。这时 ΔR 约 ${row.deltaR}，对照差最大，但资金或凭证可能已经出去，后面是追回和存证。`
  }
  if (step <= 2) {
    return `在「${stage}」停下来：对方刚开始施压或要你保密。ΔR 约 ${row.deltaR}，损失还没发生，影响最小。`
  }
  if (step === 3) {
    return `在「${stage}」停下来：转账、验证码或屏幕共享还没完成。这是关键闸门。ΔR 约 ${row.deltaR}。`
  }
  return `在「${stage}」停下来：对方已经加码。ΔR 约 ${row.deltaR}，对照差更大，但前面配合过的步骤可能已经留下风险。`
}
