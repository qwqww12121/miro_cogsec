<template>
  <section class="screen-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">Screen 2</p>
        <h3 class="title">攻击-人-环境风险图谱屏</h3>
      </div>
      <div class="score-badge">
        consistency {{ Number(graphBundle?.consistency_score || 0).toFixed(3) }}
      </div>
    </div>

    <div class="pill-row">
      <span v-for="item in graphBundle?.persuasion_principles || []" :key="item" class="pill">{{ item }}</span>
    </div>

    <GraphVisualization :graph-data="graphBundle" />

    <div class="detail-grid">
      <section class="detail-card">
        <h4>Evidence Items</h4>
        <ul>
          <li v-for="item in graphBundle?.evidence_items || []" :key="item.id">
            <strong>{{ item.label }}</strong>
            <span>{{ item.matched_terms?.join(' / ') || item.detail }}</span>
          </li>
        </ul>
      </section>
      <section class="detail-card">
        <h4>Fork Nodes</h4>
        <ul>
          <li v-for="item in graphBundle?.fork_points || []" :key="item.id">
            <strong>{{ item.type }}</strong>
            <span>{{ item.asset }} · severity {{ Number(item.severity || 0).toFixed(2) }}</span>
          </li>
        </ul>
      </section>
    </div>

    <MasterStaticDiagram />
  </section>
</template>

<script setup>
import GraphVisualization from '../GraphVisualization.vue'
import MasterStaticDiagram from '../MasterStaticDiagram.vue'

defineProps({
  graphBundle: {
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

.score-badge {
  background: #e0f2fe;
  color: #0c4a6e;
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 800;
}

.pill-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.pill {
  background: #fff1d6;
  color: #b54708;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.detail-card {
  background: #fff;
  border: 1px solid #dbe4ee;
  border-radius: 20px;
  padding: 16px;
}

.detail-card h4 {
  margin: 0 0 10px 0;
}

.detail-card ul {
  margin: 0;
  padding: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.detail-card li {
  display: grid;
  gap: 4px;
  border: 1px solid #edf2f7;
  border-radius: 12px;
  padding: 10px 12px;
  background: #f8fafc;
}

.detail-card span {
  color: #667085;
  font-size: 13px;
}

@media (max-width: 960px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
