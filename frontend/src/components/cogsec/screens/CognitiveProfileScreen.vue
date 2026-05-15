<template>
  <section class="screen-card">
    <h3>CognitiveProfileExtractor + ThreatKnowledgeRAG</h3>
    <p class="meta">Scenario: {{ profile?.scenario_type || 'unknown' }}</p>
    <p class="meta">Vulnerability: {{ Number(profile?.overall_vulnerability_score || 0).toFixed(1) }}</p>

    <div class="strategy-grid">
      <article v-for="item in strategies || []" :key="item.id" class="strategy-card">
        <h4>{{ item.tactic_name }}</h4>
        <p>{{ item.description }}</p>
        <span>{{ item.cialdini_principle }} · intensity {{ item.intensity_level }}</span>
      </article>
    </div>

    <div class="dimension-grid">
      <div v-for="(item, key) in profile?.dimension_details || {}" :key="key" class="dim-item">
        <strong>{{ key }}</strong>
        <span>{{ Number(item.value || 0).toFixed(1) }}</span>
        <em>conf: {{ Number(item.confidence_level || 0).toFixed(2) }}</em>
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
