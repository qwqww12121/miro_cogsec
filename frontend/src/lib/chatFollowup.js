const FOLLOWUP = /^(为什么|怎么办|那我|然后|还有|证据|详细|展开|受害人|谁说|怎么判定|星图|图谱|建议|该怎么|可以怎么|帮我|再讲|说清楚)(.*)$/u
const NEW_CASE = /(我是|打钱|转账|汇款|受害人：|攻击者：|骗子：|客服：|舆情|转发|传播链)/
const VICTIM_COMPLY = /(答应|同意|好的|好吧|行吧|可以了|我转|转了|验证码|收到了|我信了|马上办|我去搜|我去办)/

export function isFollowupTurn(text, lastResult) {
  const compact = String(text || '').trim()
  if (!compact || !lastResult) return false
  if (compact.length > 80) return false
  if (NEW_CASE.test(compact) && compact.length > 18) return false
  const lastScene = lastResult.scenario_type || lastResult.scenario || lastResult.chat_reply?.primary_scene || ''
  if (lastScene === 'fraud_im' && compact.length <= 40 && VICTIM_COMPLY.test(compact)) return true
  if (FOLLOWUP.test(compact)) return true
  return compact.length <= 36 && /[吗呢吧？?]|为什么|怎么|那|还|详细|谁/.test(compact)
}

export function buildFollowupReply(text, lastResult) {
  const attribution = lastResult.attribution || {}
  const reply = lastResult.chat_reply || {}
  if ((lastResult.scenario_type === 'fraud_im' || reply.primary_scene === 'fraud_im') && VICTIM_COMPLY.test(text)) {
    return {
      style: 'fraud_im',
      lead: '先停住。你刚才等于答应继续往下走了，这一步最危险。',
      paragraphs: [
        '对方要的不是你配合办事，而是验证码、账户和转账窗口。奖学金、教务处、内部审核、不许问辅导员，这几句叠在一起，就是在把你从学校正规渠道里拽走。',
        '验证码还没发出去、也还没去支付宝搜索所谓认证中心的话，现在止损仍然来得及。已经发出去的，立刻改密、冻结，并告诉家人或学校保卫处。',
        '我不会把「我答应了」当成可以继续办理的信号，更不会因此跳到微博舆情。下面两张卡片可以看完整证据和对照路径；你此刻最该做的，是拒绝下一步。',
      ],
      sections: [
        {
          heading: '现在立刻不要做的事',
          title: '现在立刻不要做的事',
          emphasis: true,
          body: '这些动作一旦做完，往往不可逆。',
          items: [
            '不要把短信验证码发给对方。',
            '不要在支付宝里搜索对方给的「认证中心」并填写身份证和银行卡。',
            '不要交 1 元验证费或转入任何「安全账户」。',
            '不要遵守「别告诉辅导员、别问同学」这种隔离指令。',
          ],
        },
      ],
      closing: '正规奖学金不会要求你私下发验证码。先打学校教务处公开电话核对，再决定要不要看场景分析和对照路径。',
      show_feature_cards: false,
      suggested_followups: ['进入场景分析', '先看对照路径图', '我该怎么回对方？'],
    }
  }
  if (/谁说|受害人|切分|归属|怎么判定/.test(text)) {
    return {
      style: reply.style || lastResult.scenario_type,
      lead: '发言是怎么切开的，已经写在上方思考过程里。这里只补一句判定结论。',
      paragraphs: [
        attribution.summary || '切分依据见思考过程中的「判定发言归属」。',
      ],
      sections: [],
      closing: '如果实际还有另一侧回复，把带角色前缀的原文贴过来，我可以重新切分。',
      show_feature_cards: false,
      suggested_followups: ['接下来我该怎么办？', '先看对照路径图'],
    }
  }
  if (/怎么办|建议|该怎么/.test(text)) {
    return {
      style: reply.style || lastResult.scenario_type,
      lead: '先不要继续按对方节奏走。你现在最稳妥的一步，是停下来核验，而不是在对话框里把钱转出去。',
      paragraphs: [
        '场景分析页会把保护因子、话术证据和干预建议按条目列清楚。对照路径图用来看「继续被诱导」和「及时止损」差在哪一步。',
      ],
      sections: [
        {
          heading: '可以立刻做的三件事',
          body: '',
          items: ['暂停转账、验证码和远程操作。', '向家人或官方渠道核实身份，不要回拨对方给的号码。', '进入场景分析，补全受害人背景后再看完整画像。'],
        },
      ],
      closing: '要不要我带你进入对应的场景分析页？',
      show_feature_cards: false,
      suggested_followups: ['进入场景分析', '先看对照路径图'],
    }
  }
  if (/星图|图谱|关系图|对照路径/.test(text)) {
    return {
      style: reply.style || lastResult.scenario_type,
      lead: '对照路径图看个体怎么走；传播关系图看人物之间怎么传。',
      paragraphs: ['诈骗场景看对照路径；舆情和事件看传播关系。然后再回场景分析核对证据。'],
      sections: [],
      closing: '需要的话我把跳转入口放在这条回复下面。',
      show_feature_cards: false,
      suggested_followups: ['进入场景分析'],
    }
  }
  return {
    style: reply.style || lastResult.scenario_type,
    lead: '我还记得上一轮已经完成的判断，可以继续往下讲。',
    paragraphs: [
      lastResult.extracted_summary || reply.lead || '上一轮已经识别出场景线索。',
      '如果你要换一段新材料，直接整段贴过来或重新上传；如果是追问上一轮，我可以按已有结论继续解释。',
    ],
    sections: [],
    closing: '你更想看证据、建议，还是直接进场景分析？',
    show_feature_cards: false,
    suggested_followups: ['为什么这样判定说话人？', '接下来我该怎么办？', '先看对照路径图'],
  }
}
