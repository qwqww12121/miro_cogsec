<template>
  <section class="screen-card">
    <h3>PrivacySanitizer</h3>
    <p class="meta">Engine: {{ data?.used_presidio ? 'Presidio + Regex' : 'Regex Fallback' }}</p>
    <div class="preview">
      {{ data?.sanitized_text || '' }}
    </div>

    <table v-if="(data?.entities || []).length" class="entity-table">
      <thead>
        <tr>
          <th>Type</th>
          <th>Placeholder</th>
          <th>Span</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in data.entities" :key="`${item.placeholder}-${item.start}`">
          <td>{{ item.entity_type }}</td>
          <td>{{ item.placeholder }}</td>
          <td>{{ item.start }}-{{ item.end }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">未检测到可脱敏实体。</p>
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
  color: #475467;
}
.preview {
  margin: 10px 0 14px 0;
  padding: 12px;
  border: 1px solid #e4ebf3;
  border-radius: 10px;
  background: #f8fafc;
  line-height: 1.7;
}
.entity-table {
  width: 100%;
  border-collapse: collapse;
}
.entity-table th,
.entity-table td {
  border-bottom: 1px solid #eceff3;
  padding: 8px 6px;
  text-align: left;
  font-size: 13px;
}
.empty {
  color: #667085;
}
</style>
