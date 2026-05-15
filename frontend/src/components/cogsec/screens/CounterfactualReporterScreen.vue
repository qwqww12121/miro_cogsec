<template>
  <section class="screen-card">
    <h3>CounterfactualReporter</h3>
    <p class="meta">{{ report?.critical_bifurcation_reason || '' }}</p>

    <BranchTimeline
      :branch-a="branchA"
      :branch-b="branchB"
      :critical-step="report?.critical_bifurcation_step"
      :critical-reason="report?.critical_bifurcation_reason"
    />

    <GraphVisualization :graph-data="graphData" />

    <div class="recommend-list">
      <article v-for="item in report?.recommendations || []" :key="`${item.priority}-${item.action}`" class="recommend-item">
        <strong>P{{ item.priority }}</strong>
        <div>
          <h4>{{ item.action }}</h4>
          <p>{{ item.reason }}</p>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import BranchTimeline from '../BranchTimeline.vue'
import GraphVisualization from '../GraphVisualization.vue'

defineProps({
  report: {
    type: Object,
    default: () => ({})
  },
  branchA: {
    type: Array,
    default: () => []
  },
  branchB: {
    type: Array,
    default: () => []
  },
  graphData: {
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
  display: grid;
  gap: 14px;
}
.meta {
  margin: 0;
  color: #475467;
}
.recommend-list {
  display: grid;
  gap: 8px;
}
.recommend-item {
  border: 1px solid #f1d8cd;
  border-radius: 10px;
  background: #fff9f6;
  padding: 10px 12px;
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
}
.recommend-item h4 {
  margin: 0 0 4px 0;
  font-size: 14px;
}
.recommend-item p {
  margin: 0;
  color: #667085;
  line-height: 1.6;
}
</style>
