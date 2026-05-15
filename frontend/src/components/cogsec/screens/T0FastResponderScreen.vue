<template>
  <section class="screen-card">
    <h3>T0FastResponder</h3>
    <p class="meta">
      Latency: {{ Number(data?.latency_ms || 0).toFixed(3) }}ms
      · Target &lt; 500ms: {{ data?.target_met ? 'YES' : 'NO' }}
    </p>
    <p class="meta">Alert: {{ data?.alert ? 'TRIGGERED' : 'CLEAR' }}</p>

    <ul v-if="(data?.hits || []).length" class="hit-list">
      <li v-for="item in data.hits" :key="`${item.rule_id}-${item.span_start}`">
        <strong>{{ item.rule_id }}</strong>
        <span>{{ item.matched_text }}</span>
      </li>
    </ul>
    <p v-else class="empty">当前样本未命中高危规则。</p>
  </section>
</template>

<script setup>
defineProps({
  data: {
    type: Object,
    default: () => ({})
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
  margin: 4px 0;
  color: #475467;
}
.hit-list {
  margin: 12px 0 0 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}
.hit-list li {
  border: 1px solid #f1d8cd;
  background: #fff9f6;
  border-radius: 10px;
  padding: 10px 12px;
  display: grid;
  gap: 4px;
}
.empty {
  color: #667085;
}
</style>
