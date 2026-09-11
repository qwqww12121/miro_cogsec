import JumpLinkCard from './chat/JumpLinkCard'
import { SCENARIOS } from '../scenarios/config'

/**
 * 场景分析结果底部的统一出口：回到自然语言对话，或打开本次结果的星图。
 */
export default function AnalysisJumpCards({ scenarioType, data, inputText = '', sessionId = '' }) {
  if (!data) return null
  const scenario = SCENARIOS[scenarioType]

  return (
    <div className="space-y-2 pt-1">
      <JumpLinkCard
        icon="spark"
        title="回到 MiroCogSec 智能对话"
        description="继续追问这次分析，或换一段材料"
        tone="brand"
        to="/chat"
        state={{ sessionId }}
      />
      <JumpLinkCard
        icon="network"
        title={scenarioType === 'fraud_im' ? '打开个体对照路径图' : '打开传播关系图'}
        description={scenarioType === 'fraud_im'
          ? '查看继续被诱导 / 及时止损的对照路径'
          : '查看源头、第一跳、扩散到更远接收的跳数关系'}
        tone={scenario?.theme || 'sand'}
        to="/simulation-map"
        state={{
          analysis: data,
          inputText,
          featureKey: scenarioType === 'fraud_im' ? 'counterfactual' : 'propagation_graph',
          returnPath: scenario?.path || '/chat',
          sessionId,
        }}
      />
    </div>
  )
}
