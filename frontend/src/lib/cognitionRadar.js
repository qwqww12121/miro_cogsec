export function cognitionRadarDims(profile = {}) {
  return [
    { dim: '情绪波动', value: Number(profile.emotional_volatility ?? 0) },
    { dim: '从众敏感', value: Number(profile.social_proof_sensitivity ?? 0) },
    { dim: '损失厌恶', value: Number(profile.loss_aversion_threshold ?? 0) },
    { dim: '信任阈值', value: Number(profile.trust_threshold ?? 0) },
    { dim: '权威服从', value: Number(profile.authority_compliance ?? 0) },
    { dim: '稀缺敏感', value: Number(profile.scarcity_sensitivity ?? 0) },
  ]
}

export function hasCognitionSignal(dims) {
  return dims.some((item) => Number(item.value) > 0)
}
