import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { SCENARIOS } from '../../scenarios/config'
import ScenarioLayout from '../../components/ScenarioLayout'
import Section from '../../components/Section'
import { FormField, TextInput, TextArea, Select } from '../../components/FormField'
import Icon from '../../components/Icon'
import { runFraudImAnalysis } from '../../api/scenarios'
import FraudImResult from '../../components/results/FraudImResult'

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

const EXAMPLE = `攻击者：您好，我是某行客服，您的征信存在异常风险，现在不处理会影响贷款。
受害人：是真的吗？
攻击者：请配合操作，先下载我们指定的 APP 并打开屏幕共享，按提示把余额转入"安全账户"。`

const initialForm = {
  platform: '微信',
  attackerRole: '冒充客服',
  victimContext: '50 岁，独居，缺少反诈科普',
  scenarioCategory: '虚假征信类',
  conversation: '',
}

export default function FraudImPage() {
  const location = useLocation()
  const prefillText = location.state?.prefillText
  const [form, setForm] = useState(
    prefillText ? { ...initialForm, conversation: prefillText } : initialForm
  )
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [data, setData] = useState(null)

  const onChange = (k) => (e) => setForm((s) => ({ ...s, [k]: e.target.value }))

  const onSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    if (!form.conversation.trim()) {
      setError('请填写对话内容')
      return
    }
    setLoading(true)
    setData(null)
    try {
      const result = await runFraudImAnalysis(form)
      setData(result)
    } catch (err) {
      setError(err.message || '请求失败')
    } finally {
      setLoading(false)
    }
  }

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
              <TextInput value={form.victimContext} onChange={onChange('victimContext')} />
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
              <TextArea
                value={form.conversation}
                onChange={onChange('conversation')}
                rows={9}
                placeholder={EXAMPLE}
              />
            </FormField>
            <button type="submit" className="btn-primary w-full" disabled={loading}>
              <Icon name="spark" className="w-4 h-4 mr-1.5" />
              {loading ? '分析中…' : '开始分析'}
            </button>
            <div className="text-[11px] text-ink-500 leading-relaxed pt-1">
              将调用后端 <code className="text-ink-900">POST /api/cogsec/analyze</code>，返回认知画像、攻击策略与反事实报告。
            </div>
          </form>
        </Section>
      }
      result={<FraudImResult data={data} loading={loading} error={error} />}
    />
  )
}
