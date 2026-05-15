<template>
  <section class="screen-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">Screen 3</p>
        <h3 class="title">MIRO-FISH 双分支反事实推演屏</h3>
      </div>
      <div class="fork-pill">{{ forkComparison?.fork_point_type || 'fork' }}</div>
    </div>

    <BranchTimeline
      :branch-a="branchA"
      :branch-b="branchB"
      :critical-step="forkComparison?.best_intervention_window?.open_step || 0"
      :critical-reason="criticalReason"
    />

    <div class="step-grid">
      <article v-for="item in combinedSteps" :key="item.step" class="step-card">
        <div class="step-head">
          <strong>T{{ item.step }}</strong>
          <span>posterior gap {{ item.gap }}</span>
        </div>
        <div class="branch-block danger">
          <h4>Branch A</h4>
          <p>{{ item.a?.action || '-' }}</p>
          <small>
            mode {{ item.a?.world_state?.cognitive_mode || '-' }} ·
            risk {{ format(item.a?.world_state?.posterior_risk) }} ·
            reversibility {{ format(item.a?.world_state?.reversibility) }}
          </small>
        </div>
        <div class="branch-block safe">
          <h4>Branch B</h4>
          <p>{{ item.b?.action || '-' }}</p>
          <small>
            mode {{ item.b?.world_state?.cognitive_mode || '-' }} ·
            risk {{ format(item.b?.world_state?.posterior_risk) }} ·
            reversibility {{ format(item.b?.world_state?.reversibility) }}
          </small>
        </div>
      </article>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import BranchTimeline from '../BranchTimeline.vue'

const props = defineProps({
  branchA: {
    type: Array,
    default: () => []
  },
  branchB: {
    type: Array,
    default: () => []
  },
  forkComparison: {
    type: Object,
    default: () => ({})
  }
})

const format = (value) => Number(value || 0).toFixed(3)

const criticalReason = computed(() => {
  const step = props.forkComparison?.best_intervention_window?.open_step || 1
  return `Fork node ${props.forkComparison?.fork_point_type || 'unknown'} 在第 ${step} 步前后形成最大干预价值。`
})

const combinedSteps = computed(() => {
  const max = Math.max(props.branchA.length, props.branchB.length)
  return Array.from({ length: max }, (_, index) => {
    const a = props.branchA[index]
    const b = props.branchB[index]
    const gap = Math.abs(Number(a?.world_state?.posterior_risk || 0) - Number(b?.world_state?.posterior_risk || 0))
    return {
      step: index + 1,
      a,
      b,
      gap: gap.toFixed(3)
    }
  })
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
  color: #b54708;
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

.fork-pill {
  background: #fff1d6;
  color: #b54708;
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 800;
}

.step-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.step-card {
  background: #fff;
  border: 1px solid #dbe4ee;
  border-radius: 18px;
  padding: 16px;
  display: grid;
  gap: 10px;
}

.step-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  color: #475467;
  font-size: 13px;
}

.branch-block {
  border-radius: 14px;
  padding: 12px;
}

.branch-block h4,
.branch-block p,
.branch-block small {
  margin: 0;
}

.branch-block p {
  line-height: 1.6;
  margin: 6px 0;
}

.branch-block.danger {
  background: #fff7ed;
  border: 1px solid #fdba74;
}

.branch-block.safe {
  background: #f0fdf4;
  border: 1px solid #86efac;
}

@media (max-width: 960px) {
  .step-grid {
    grid-template-columns: 1fr;
  }
}
</style>
