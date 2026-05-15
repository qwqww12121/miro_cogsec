<template>
  <router-view />
</template>

<script setup>
// 使用 Vue Router 来管理页面
</script>

<style>
:root {
  --bg-main: #f4f7fb;
  --bg-soft: #ffffff;
  --bg-elevated: #f8fafc;
  --text-main: #111827;
  --text-secondary: #475467;
  --border-main: #dce3ec;
  --brand-primary: #0f766e;
  --brand-primary-soft: #e7f6f4;
  --accent-orange: #f97316;
  --shadow-soft: 0 12px 30px rgba(15, 23, 42, 0.08);
}

/* 全局样式重置 */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html,
body {
  min-height: 100%;
  background:
    radial-gradient(circle at 10% -10%, rgba(15, 118, 110, 0.08), transparent 40%),
    radial-gradient(circle at 95% 5%, rgba(249, 115, 22, 0.07), transparent 35%),
    var(--bg-main);
  color: var(--text-main);
}

#app {
  min-height: 100vh;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--text-main);
  background: transparent;
}

/* 滚动条样式 */
::-webkit-scrollbar {
  width: 10px;
  height: 10px;
}

::-webkit-scrollbar-track {
  background: #eef2f7;
}

::-webkit-scrollbar-thumb {
  background: #b8c5d6;
  border-radius: 999px;
  border: 2px solid #eef2f7;
}

::-webkit-scrollbar-thumb:hover {
  background: #9db0c7;
}

button {
  font-family: inherit;
  transition: all 0.2s ease;
}

a {
  color: inherit;
}

::selection {
  background: rgba(15, 118, 110, 0.18);
}
</style>
