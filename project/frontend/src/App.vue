<script setup lang="ts">
// 根组件 - 仅提供路由视图出口
</script>

<template>
  <router-view />
</template>

<style>
/* 全局基础样式 */
html,
body {
  margin: 0;
  padding: 0;
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto,
    'Helvetica Neue', Arial, 'Noto Sans SC', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

#app {
  height: 100%;
}

*,
*::before,
*::after {
  box-sizing: border-box;
}

a {
  color: inherit;
  text-decoration: none;
}
</style>
