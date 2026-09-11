import { useEffect, useMemo, useRef, useState } from 'react'
import { useLocation } from 'react-router-dom'
import { SCENARIOS } from '../../scenarios/config'
import ScenarioLayout from '../../components/ScenarioLayout'
import Section from '../../components/Section'
import { FormField, TextInput, Select } from '../../components/FormField'
import Icon from '../../components/Icon'
import Spinner from '../../components/Spinner'
import { runFraudImAnalysis } from '../../api/scenarios'
import FraudImResult from '../../components/results/FraudImResult'
import PlainViewWrapper from '../../components/results/PlainViewWrapper'
import AnalysisAnswer from '../../components/results/AnalysisAnswer'
import MultimodalComposer from '../../components/MultimodalComposer'
import AnalysisJumpCards from '../../components/AnalysisJumpCards'
import { loadWorkspace, saveWorkspace } from '../../lib/scenarioWorkspace'
import { composeFraudText } from '../../lib/platformContext'

const SCENARIO_CATEGORIES = [
  '虚假征信类',
  '刷单返利类',
  '虚假网络投资理财类',
  '冒充电商物流客服类',
  '冒充公检法及政府机关类',
  '冒充领导熟人类',
  '虚假贷款代办信用卡类',
  '机票退改签类',
  '网络婚恋交友类',
  '网络游戏产品虚假交易类',
]

const FRAUD_TYPE_KEYWORDS = [
  ['奖学金', '冒充领导熟人类'], ['助学金', '冒充领导熟人类'], ['教务', '冒充领导熟人类'],
  ['征信', '虚假征信类'], ['刷单', '刷单返利类'], ['投资', '虚假网络投资理财类'],
  ['理财', '虚假网络投资理财类'], ['客服', '冒充电商物流客服类'], ['电商', '冒充电商物流客服类'],
  ['公检法', '冒充公检法及政府机关类'], ['政府', '冒充公检法及政府机关类'], ['领导', '冒充领导熟人类'],
  ['熟人', '冒充领导熟人类'], ['贷款', '虚假贷款代办信用卡类'], ['信用卡', '虚假贷款代办信用卡类'],
  ['机票', '机票退改签类'], ['婚恋', '网络婚恋交友类'], ['情感', '网络婚恋交友类'],
  ['游戏', '网络游戏产品虚假交易类'],
]

// Chat platform and attacker-role keyword tables. The backend classify
// endpoint currently only returns confidence/reason/extracted_summary —
// no structured extracted_fields — so these are matched directly against
// the pasted text as a client-side best-effort fallback.
const PLATFORM_KEYWORDS = [
  ['微信', '微信'], ['wechat', '微信'], ['qq', 'QQ'], ['短信', '短信'],
  ['电话', '电话'], ['支付宝', '支付宝'], ['钉钉', '钉钉'], ['邮件', '邮件'], ['email', '邮件'],
]

const ATTACKER_ROLE_KEYWORDS = [
  ['教务', '学校教务人员'], ['奖学金', '学校教务人员'], ['老师', '学校老师'],
  ['客服', '冒充客服'], ['公检法', '冒充公检法'], ['警察', '冒充公检法'], ['检察院', '冒充公检法'],
  ['法院', '冒充公检法'], ['领导', '冒充领导熟人'], ['同事', '冒充领导熟人'], ['熟人', '冒充领导熟人'],
  ['银行', '冒充银行工作人员'], ['客户经理', '冒充银行工作人员'], ['快递', '冒充快递/物流客服'],
  ['物流', '冒充快递/物流客服'], ['电商', '冒充电商平台客服'],
]

function matchFraudType(text) {
  if (!text) return ''
  return FRAUD_TYPE_KEYWORDS.find(([keyword]) => text.includes(keyword))?.[1] || ''
}

function matchKeyword(text, table) {
  if (!text) return ''
  const lower = text.toLowerCase()
  return table.find(([keyword]) => lower.includes(keyword.toLowerCase()))?.[1] || ''
}

const EXAMPLE = `攻击者：您好，我是某行客服，您的征信存在异常风险，现在不处理会影响贷款。
受害人：是真的吗？
攻击者：请配合操作，先下载我们指定的 APP 并打开屏幕共享，按提示把余额转入"安全账户"。`

const initialForm = {
  platform: '',
  attackerRole: '',
  victimContext: '',
  scenarioCategory: '',
  conversation: '',
  attachments: [],
}

function inferVictimContext(text) {
  const src = String(text || '')
  if (/同学|学生|奖学金|助学金|教务|大学|校园|本科/.test(src)) {
    const school = src.match(/([\u4e00-\u9fa5]{2,12}大学)/)?.[1]
    return school
      ? `在校学生（${school}），收到奖学金或教务类通知，缺少当面核验条件`
      : '在校学生，收到奖学金或教务类通知，缺少当面核验条件'
  }
  if (/老人|退休|独居|50\s*岁/.test(src)) return '中老年，独居或缺少反诈科普'
  return ''
}

export default function FraudImPage() {
  const location = useLocation()
  const sessionId = location.state?.sessionId || 'local'
  const cached = useMemo(() => loadWorkspace('fraud_im', sessionId), [sessionId])
  const prefillText = location.state?.prefillText ?? ''
  // ChatPage classify response includes extracted_fields when the backend
  // can infer platform / identity / fraud type from the pasted text.
  const extractedFields = location.state?.extractedFields || {}
  const extractedSummary = location.state?.extractedSummary || ''
  const matchSource = `${prefillText}\n${extractedSummary}`
  const prefillChanged = Boolean(prefillText && cached?.form?.conversation && prefillText.trim() !== String(cached.form.conversation || '').trim())

  const [form, setForm] = useState(() => {
    const base = { ...initialForm, ...(cached?.form || {}), attachments: [] }
    if (prefillText) base.conversation = prefillText

    const platform = extractedFields.chat_platform || matchKeyword(matchSource, PLATFORM_KEYWORDS)
    if (platform) base.platform = platform

    const attackerRole = extractedFields.suspect_identity || matchKeyword(matchSource, ATTACKER_ROLE_KEYWORDS)
    if (attackerRole) base.attackerRole = attackerRole

    const category = matchFraudType(extractedFields.fraud_type) || matchFraudType(matchSource)
    if (category) base.scenarioCategory = category

    const victimContext = inferVictimContext(matchSource) || base.victimContext
    if (victimContext) base.victimContext = victimContext

    return base
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(() => (prefillChanged ? null : (cached?.data || null)))
  const autoStarted = useRef(false)
  const analysisText = useMemo(() => composeFraudText(form), [form])

  const onChange = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))
  const onFilesChange = (attachments) => setForm((s) => ({ ...s, attachments }))
  const onRemoveFile = (index) => setForm((s) => ({ ...s, attachments: s.attachments.filter((_, i) => i !== index) }))

  const analyze = async (payload) => {
    setError(null)
    if (!payload.conversation.trim() && !payload.attachments.length) {
      setError('请填写对话内容或添加文件/语音')
      return
    }
    setLoading(true)
    setData(null)
    try {
      const result = await runFraudImAnalysis({
        ...payload,
        victimContext: payload.victimContext.trim() || inferVictimContext(payload.conversation),
      })
      setData(result)
      saveWorkspace('fraud_im', sessionId, { form: payload, data: result })
    } catch (err) {
      setError(err.message || '请求失败')
    } finally {
      setLoading(false)
    }
  }

  const onSubmit = (e) => {
    e.preventDefault()
    analyze(form)
  }

  useEffect(() => {
    saveWorkspace('fraud_im', sessionId, { form, data })
  }, [form, data, sessionId])

  useEffect(() => {
    if (autoStarted.current) return
    if (data) return
    if (!prefillText) return
    autoStarted.current = true
    analyze(form)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const fillExample = () => setForm((s) => ({ ...s, conversation: EXAMPLE }))

  return (
    <ScenarioLayout
      scenario={SCENARIOS.fraud_im}
      input={
        <Section
          title="输入参数"
          action={
            <button type="button" className="btn-ghost text-xs" onClick={fillExample}>
              填入示例
            </button>
          }
        >
          <form className="space-y-3" onSubmit={onSubmit}>
            <FormField label="对话平台">
              <TextInput value={form.platform} onChange={onChange('platform')} placeholder="如：微信 / QQ / 短信" />
            </FormField>
            <FormField label="嫌疑人身份">
              <TextInput value={form.attackerRole} onChange={onChange('attackerRole')} placeholder="如：冒充客服 / 公检法" />
            </FormField>
            <FormField label="受害人背景" hint="年龄、社会关系、风险习惯等">
              <TextInput value={form.victimContext} onChange={onChange('victimContext')} placeholder="例如：在校学生，收到奖学金通知" />
            </FormField>
            <FormField label="疑似诈骗类别">
              <Select value={form.scenarioCategory} onChange={onChange('scenarioCategory')}>
                <option value="">由系统自动判定</option>
                {SCENARIO_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </Select>
            </FormField>
            <FormField label="对话内容 *" hint='按"角色：内容"逐行粘贴'>
              <MultimodalComposer
                value={form.conversation}
                onChange={onChange('conversation')}
                files={form.attachments}
                onFilesChange={onFilesChange}
                onRemoveFile={onRemoveFile}
                loading={loading}
                rows={9}
                accent="brand"
                placeholder={EXAMPLE}
              />
            </FormField>
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              {loading ? <Spinner className="w-4 h-4 mr-1.5" /> : <Icon name="spark" className="w-4 h-4 mr-1.5" />}
              {loading ? '分析中…' : '开始分析'}
            </button>
            <div className="text-[11px] text-ink-500 leading-relaxed pt-1">
              提交后会生成认知画像、攻击策略与对照路径。
            </div>
          </form>
        </Section>
      }
      result={
        <div className="space-y-4">
          <AnalysisAnswer data={data} inputText={analysisText} scenarioType="fraud_im" />
          <PlainViewWrapper data={data} scenarioType="fraud_im">
            <FraudImResult data={data} loading={loading} error={error} inputText={analysisText} victimContext={form.victimContext} />
          </PlainViewWrapper>
          <AnalysisJumpCards scenarioType="fraud_im" data={data} inputText={analysisText} sessionId={sessionId} />
        </div>
      }
    />
  )
}
