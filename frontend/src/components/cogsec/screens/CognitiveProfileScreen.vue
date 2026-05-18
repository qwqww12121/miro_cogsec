<template>
  <section class="screen-card">
    <h3>认知画像提取 + 威胁知识检索</h3>
    <p class="meta">场景：{{ profile?.scenario_type || '未知' }}</p>
    <p class="meta">综合脆弱度：{{ Number(profile?.overall_vulnerability_score || 0).toFixed(1) }}</p>

    <div class="strategy-grid">
      <article v-for="item in strategies || []" :key="item.id" class="strategy-card">
        <h4>{{ item.tactic_name }}</h4>
        <p>{{ item.description }}</p>
        <span>{{ item.cialdini_principle }} · 强度 {{ item.intensity_level }}</span>
      </article>
    </div>

    <div class="dimension-grid">
      <div v-for="(item, key) in profile?.dimension_details || {}" :key="key" class="dim-item">
        <strong>{{ dimLabels[key] || key }}</strong>
        <span>{{ Number(item.value || 0).toFixed(1) }}</span>
        <em>置信：{{ Number(item.confidence_level || 0).toFixed(2) }}</em>
      </div>
    </div>
  </section>
</template>

<script setup>
defineProps({
  profile: {
    type: Object,
    default: () => ({})
  },
  strategies: {
    type: Array,
    default: () => []
  }
})

const dimLabels = {
  authority_compliance: '权威服从度',
  authority_intensity: '权威压力强度',
  cognitive_load: '认知负荷',
  decision_delay: '决策延迟',
  emotional_volatility: '情绪波动性',
  financial_pressure: '财务压力',
  financial_stress: '财务压力',
  fomo_susceptibility: '紧迫感易感性',
  help_seeking: '求助倾向',
  help_seeking_tendency: '求助倾向',
  info_asymmetry: '信息不对称度',
  link_check_ability: '链接核查能力',
  loss_aversion_threshold: '损失厌恶阈值',
  scarcity_sensitivity: '稀缺性敏感度',
  social_isolation_risk: '社交隔离风险',
  social_proof_sensitivity: '从众敏感度',
  time_pressure: '时间压力',
  trust_threshold: '信任阈值',
  verification_habit: '核实习惯',
}
</script>

<style scoped>
.screen-card {
  background: #fff;
  border: 1px solid #d7e3ee;
  border-radius: 18px;
  padding: 18px;
}
.meta {
  color: #475467;
  margin: 4px 0;
}
.strategy-grid {
  margin: 12px 0;
  display: grid;
  gap: 10px;
}
.strategy-card {
  border: 1px solid #f1d8cd;
  border-radius: 10px;
  background: #fff9f6;
  padding: 10px 12px;
}
.strategy-card h4 {
  margin: 0 0 6px 0;
}
.strategy-card p {
  margin: 0 0 6px 0;
  color: #475467;
}
.strategy-card span {
  font-size: 12px;
  color: #667085;
}
.dimension-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}
.dim-item {
  border: 1px solid #e4ebf3;
  border-radius: 10px;
  padding: 8px;
  display: grid;
  gap: 2px;
  background: #f8fafc;
}
.dim-item span {
  color: #0f172a;
}
.dim-item em {
  font-style: normal;
  color: #667085;
  font-size: 12px;
}
@media (max-width: 960px) {
  .dimension-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
