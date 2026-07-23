<script setup lang="ts">
/**
 * StudentLayout - 学生端布局
 * 简洁顶部导航 + 主内容区
 *
 * 顶级导航：工作台 / 我的任务 / 项目空间 / 我的评价 / 成长档案。
 * 反馈订正从任务列表进入，不加顶级导航（计划 3.7）。
 */
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

interface NavItem {
  path: string
  label: string
  /** 锚点：项目空间指向工作台的项目概览区。 */
  hash?: string
}

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

/** 学生端导航菜单 */
const navItems: NavItem[] = [
  { path: '/student/dashboard', label: '工作台' },
  { path: '/student/tasks', label: '我的任务' },
  { path: '/student/dashboard', label: '项目空间', hash: '#projects' },
  { path: '/student/evaluations', label: '我的评价' },
  { path: '/student/growth', label: '成长档案' },
]

/** 解析导航目标（带锚点时使用对象形式）。 */
function navTo(item: NavItem): string | { path: string; hash: string } {
  return item.hash ? { path: item.path, hash: item.hash } : item.path
}

/** 高亮判断：路径匹配且（无锚点或锚点匹配）。 */
function isActive(item: NavItem): boolean {
  if (route.path !== item.path) return false
  if (!item.hash) return route.hash === '' || route.hash === undefined
  return route.hash === item.hash
}

/** 下拉菜单命令处理 */
function handleCommand(cmd: string) {
  if (cmd === 'profile') {
    router.push('/student/profile')
  } else if (cmd === 'logout') {
    userStore.logout()
  }
}
</script>

<template>
  <div class="student-layout">
    <!-- 顶部导航 -->
    <header class="header">
      <div class="header-left">
        <el-icon :size="28" color="#409EFF"><School /></el-icon>
        <span class="header-title">教学评一体化平台</span>
      </div>

      <nav class="header-nav">
        <router-link
          v-for="(item, idx) in navItems"
          :key="item.label + idx"
          :to="navTo(item)"
          class="nav-item"
          :class="{ active: isActive(item) }"
        >
          {{ item.label }}
        </router-link>
      </nav>

      <div class="header-right">
        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-info">
            <el-avatar :size="28" :icon="UserFilled" />
            <span class="username">{{ userStore.displayName }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">个人中心</el-dropdown-item>
              <el-dropdown-item divided command="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
.student-layout {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

.header {
  height: 56px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-nav {
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-item {
  padding: 8px 16px;
  font-size: 14px;
  color: #606266;
  border-radius: 6px;
  transition: all 0.2s;
  text-decoration: none;

  &:hover {
    color: #409EFF;
    background: #ecf5ff;
  }

  &.active {
    color: #409EFF;
    background: #ecf5ff;
    font-weight: 500;
  }
}

.header-right {
  display: flex;
  align-items: center;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 6px;
  transition: background 0.2s;

  &:hover {
    background: #f5f7fa;
  }
}

.username {
  font-size: 14px;
  color: #303133;
}

.content {
  flex: 1;
  overflow-y: auto;
}

/* 平板与移动端响应式：导航横向滚动，避免遮挡 */
@media (max-width: 768px) {
  .header {
    padding: 0 12px;
    gap: 8px;
  }
  .header-title {
    display: none;
  }
  .header-nav {
    overflow-x: auto;
    flex: 1;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
  }
  .header-nav::-webkit-scrollbar {
    display: none;
  }
  .nav-item {
    padding: 8px 10px;
    white-space: nowrap;
    flex-shrink: 0;
  }
  .username {
    display: none;
  }
}
</style>
