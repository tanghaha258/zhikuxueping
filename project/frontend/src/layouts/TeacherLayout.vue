<script setup lang="ts">
/**
 * TeacherLayout - 教师端布局
 * 顶部导航 + 侧边栏 + 主内容区
 */
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()

const sidebarCollapsed = computed(() => appStore.sidebarCollapsed)

/** 教师端导航菜单项 */
const menuItems = [
  { path: '/teacher/dashboard', icon: 'Odometer', label: '工作台' },
  { path: '/teacher/projects', icon: 'FolderOpened', label: '跨学科项目' },
  { path: '/teacher/lesson-plans', icon: 'Notebook', label: '智能备课' },
  { path: '/teacher/tasks', icon: 'List', label: '任务管理' },
  { path: '/teacher/papers', icon: 'Document', label: '试卷管理' },
  { path: '/teacher/question-bank', icon: 'Collection', label: '题库管理' },
  { path: '/teacher/paper-generator', icon: 'MagicStick', label: 'AI 出卷' },
  { path: '/teacher/grading', icon: 'Collection', label: 'AI 批改' },
  { path: '/teacher/evaluations', icon: 'Star', label: '多元评价' },
  { path: '/teacher/resources', icon: 'Files', label: '资源中心' },
]

/** 当前激活的菜单 */
const activeMenu = computed(() => route.path)

/** 处理菜单选择 */
function handleMenuSelect(index: string) {
  router.push(index)
}

/** 下拉菜单命令处理 */
function handleCommand(cmd: string) {
  if (cmd === 'profile' || cmd === 'settings') {
    router.push('/teacher/profile')
  } else if (cmd === 'logout') {
    userStore.logout()
  }
}

/** 侧边栏展开/折叠 */
function toggleSidebar() {
  appStore.toggleSidebar()
}
</script>

<template>
  <div class="teacher-layout">
    <!-- 顶部导航 -->
    <header class="header">
      <div class="header-left">
        <el-button
          :icon="sidebarCollapsed ? 'Expand' : 'Fold'"
          text
          @click="toggleSidebar"
        />
        <span class="header-title">初中跨学科教学评一体化平台</span>
      </div>

      <div class="header-right">
        <el-badge :value="3" :hidden="false" class="header-badge">
          <el-button :icon="Bell" text @click="console.log('notifications')" />
        </el-badge>

        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-info">
            <el-avatar :size="32" :icon="UserFilled" />
            <span class="username">{{ userStore.displayName }}</span>
            <el-icon><ArrowDown /></el-icon>
          </span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">
                <el-icon><User /></el-icon>个人中心
              </el-dropdown-item>
              <el-dropdown-item command="settings">
                <el-icon><Setting /></el-icon>设置
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </header>

    <div class="main-container">
      <!-- 侧边栏 -->
      <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
        <el-menu
          :default-active="activeMenu"
          :collapse="sidebarCollapsed"
          :router="false"
          @select="handleMenuSelect"
        >
          <el-menu-item
            v-for="item in menuItems"
            :key="item.path"
            :index="item.path"
          >
            <el-icon>
              <component :is="item.icon" />
            </el-icon>
            <template #title>
              <span>{{ item.label }}</span>
            </template>
          </el-menu-item>
        </el-menu>
      </aside>

      <!-- 主内容区 -->
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.teacher-layout {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: #f5f7fa;
}

/* 顶部导航 */
.header {
  height: 60px;
  background: #fff;
  border-bottom: 1px solid #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  flex-shrink: 0;
  z-index: 100;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.header-badge {
  :deep(.el-badge__content) {
    top: 8px;
    right: 6px;
  }
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
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 主容器 */
.main-container {
  display: flex;
  flex: 1;
  overflow: hidden;
}

/* 侧边栏 */
.sidebar {
  width: 240px;
  background: #fff;
  border-right: 1px solid #e4e7ed;
  transition: width 0.3s ease;
  overflow-y: auto;
  flex-shrink: 0;

  &.collapsed {
    width: 64px;
  }

  :deep(.el-menu) {
    border-right: none;
  }
}

/* 主内容 */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}
</style>
