<template>
  <section class="diagram-card">
    <div class="header-row">
      <div>
        <p class="eyebrow">Static Master Diagram</p>
        <h3 class="title">CogSec-MIROFISH 认知安全反事实演化总图</h3>
      </div>
      <div class="meta-pill">答辩 / PPT / 海报可复用</div>
    </div>
    <p class="caption">
      左侧展示输入与数字孪生初始化，中部展示 Threat-Persona-Context Risk Graph 与 WorldState，
      右侧展示 Fork 后的红绿双分支演化，下方落到风险曲线、可逆性曲线与个性化干预处方。
    </p>
    <img
      class="diagram-image"
      src="/cogsec-mirofish-mainline-diagram.svg"
      alt="CogSec-MIROFISH mainline master diagram"
    />
  </section>
</template>

<style scoped>
.diagram-card {
  display: grid;
  gap: 14px;
  background: linear-gradient(180deg, #fffef9 0%, #ffffff 100%);
  border: 1px solid #e6e9f0;
  border-radius: 22px;
  padding: 20px;
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
  font-size: 22px;
  color: #0f172a;
}

.meta-pill {
  background: #e0f2fe;
  color: #0c4a6e;
  border-radius: 999px;
  padding: 8px 12px;
  font-size: 12px;
  font-weight: 700;
}

.caption {
  margin: 0;
  color: #475467;
  line-height: 1.7;
}

.diagram-image {
  width: 100%;
  border-radius: 18px;
  border: 1px solid #dbe4ee;
  background: #f8fafc;
}
</style>
