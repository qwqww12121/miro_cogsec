<template>
  <section class="screen-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">Screen 5</p>
        <h3 class="title">个性化干预处方屏</h3>
      </div>
      <div class="window-pill">
        open T{{ report?.best_intervention_window?.open_step || 1 }}
      </div>
    </div>

    <div class="window-card">
      <strong>Best Intervention Window</strong>
      <p>{{ report?.best_intervention_window?.label || 'No explicit window.' }}</p>
    </div>

    <div class="prescription-grid">
      <article
        v-for="item in prescriptions"
        :key="`${item.priority}-${item.title}`"
        class="prescription-card"
      >
        <div class="card-top">
          <span class="priority-pill">P{{ item.priority }}</span>
          <strong>{{ item.title }}</strong>
        </div>
        <p class="node">failure node: {{ item.target_failure_node }}</p>
        <p class="reason">{{ item.rationale }}</p>
        <ul>
          <li v-for="action in item.recommended_actions || []" :key="action">{{ action }}</li>
        </ul>
        <p class="meta">channel: {{ item.channel }} · fallback: {{ item.fallback }}</p>
      </article>
    </div>

    <div class="status-grid">
      <section class="status-card">
        <h4>稳定底座能力</h4>
        <ul>
          <li v-for="item in implementationStatus?.stable_base || []" :key="item">{{ item }}</li>
        </ul>
      </section>
      <section class="status-card accent">
        <h4>当前新增主链能力</h4>
        <ul>
          <li v-for="item in implementationStatus?.new_mainline || []" :key="item">{{ item }}</li>
        </ul>
      </section>
      <section class="status-card">
        <h4>Phase-II 深化能力</h4>
        <ul>
          <li v-for="item in implementationStatus?.phase_ii || []" :key="item">{{ item }}</li>
        </ul>
      </section>
    </div>
  </section>
</template>

<script setup>
defineProps({
  prescriptions: {
    type: Array,
    default: () => []
  },
  report: {
    type: Object,
    default: () => ({})
  },
  implementationStatus: {
    type: Object,
    default: () => ({})
  }
})
</script>

<style scoped>
.screen-card {
  display: grid;
  gap: 16px;
}

.header-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: flex-start;
}

.eyebrow {
  margin: 0 0 6px 0;
  color: #0f766e;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-weight: 700;
}

.title {
  margin: 0;
  color: #0f172a;
  font-size: 24px;
}

.window-pill {
  background: #ecfdf3;
  color: #166534;
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 800;
}

.window-card,
.status-card {
  background: #fff;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  padding: 16px;
}

.window-card p,
.reason,
.meta,
.node {
  margin: 8px 0 0 0;
  color: #475467;
  line-height: 1.7;
}

.prescription-grid,
.status-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
}

.prescription-card {
  background: linear-gradient(180deg, #fffef9 0%, #ffffff 100%);
  border: 1px solid #f2dfb6;
  border-radius: 18px;
  padding: 16px;
  display: grid;
  gap: 10px;
}

.card-top {
  display: grid;
  gap: 8px;
}

.priority-pill {
  justify-self: start;
  background: #fff1d6;
  color: #b54708;
  border-radius: 999px;
  padding: 5px 10px;
  font-size: 12px;
  font-weight: 700;
}

.prescription-card ul,
.status-card ul {
  margin: 0;
  padding-left: 18px;
  color: #0f172a;
  line-height: 1.7;
}

.status-card h4 {
  margin: 0 0 10px 0;
}

.status-card.accent {
  background: #f8fafc;
  border-color: #bfdbfe;
}

@media (max-width: 1100px) {
  .prescription-grid,
  .status-grid {
    grid-template-columns: 1fr;
  }
}
</style>
