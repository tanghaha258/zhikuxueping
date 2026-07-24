<script setup lang="ts">
/**
 * TeacherLayout - 教师端布局（Task 4 重构）。
 *
 * 一级导航按规格 §5.1 分为五组：工作台、智跨学评、备课与设计、题库与测评、教学实施。
 * 能力中心入口保留；项目阶段不出现在一级侧栏（阶段导航由项目工作区外壳承担）。
 * 顶部导航 + 分组侧边栏 + 主内容区，沿用通用设计令牌。
 */
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const appStore = useAppStore()

const sidebarCollapsed = computed(() => appStore.sidebarCollapsed)

/**
 * 一级导航分组。每组可含一个入口或多个子入口；项目阶段不在此出现。
 * 路由路径沿用现状，不擅自新增/删除路由（路由调整归后续 Task）。
 */
interface NavLeaf { path: string; icon: string; label: string }
interface NavGroup { key: string; label: string; icon: string; children?: NavLeaf[]; path?: string }

const navGroups: NavGroup[] = [
  { key: 'workbench', label: '工作台', icon: 'Odometer', path: '/teacher/dashboard' },
  {
    key: 'zhikua',
    label: '智跨学评',
    icon: 'FolderOpened',
    children: [{ path: '/teacher/projects', icon: 'Collection', label: '我的跨学科项目' }],
  },
  {
    key: 'design',
    label: '备课与设计',
    icon: 'Notebook',
    children: [{ path: '/teacher/lesson-plans', icon: 'EditPen', label: '智能备课' }],
  },
  {
    key: 'assessment',
    label: '题库与测评',
    icon: 'Document',
    children: [
      { path: '/teacher/question-bank', icon: 'Files', label: '题库管理' },
      { path: '/teacher/paper-generator', icon: 'MagicStick', label: '智能组卷' },
      { path: '/teacher/papers', icon: 'Document', label: '试卷管理' },
      { path: '/teacher/grading', icon: 'Stamp', label: '智能批改' },
    ],
  },
  {
    key: 'implementation',
    label: '教学实施',
    icon: 'List',
    children: [
      { path: '/teacher/tasks', icon: 'List', label: '任务中心' },
      { path: '/teacher/evaluations', icon: 'Star', label: '评价中心' },
      { path: '/teacher/resources', icon: 'Files', label: '资源中心' },
    ],
  },
]

/** 当前激活的菜单（按路径匹配） */
const activeMenu = computed(() => route.path)

/** 默认展开包含当前路由的分组 */
const defaultOpeneds = computed(() => {
  const opens: string[] = []
  for (const g of navGroups) {
    if (g.children?.some((c) => route.path.startsWith(c.path))) {
      opens.push(g.key)
    }
  }
  return opens
})

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
          aria-label="折叠侧边栏"
          @click="toggleSidebar"
        />
        <span class="header-title">初中跨学科教学评一体化平台</span>
      </div>

      <div class="header-right">
        <el-dropdown trigger="click" @command="handleCommand">
          <span class="user-info">
            <el-avatar :size="32" icon="UserFilled" />
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
          :default-openeds="defaultOpeneds"
          :collapse="sidebarCollapsed"
          :router="false"
          @select="handleMenuSelect"
        >
          <template v-for="g in navGroups" :key="g.key">
            <!-- 单入口分组：直接渲染为菜单项 -->
            <el-menu-item v-if="g.path" :index="g.path">
              <el-icon><component :is="g.icon" /></el-icon>
              <template #title>
                <span>{{ g.label }}</span>
              </template>
            </el-menu-item>

            <!-- 多入口分组：渲染为子菜单 -->
            <el-sub-menu v-else :index="g.key">
              <template #title>
                <el-icon><component :is="g.icon" /></el-icon>
                <span>{{ g.label }}</span>
              </template>
              <el-menu-item
                v-for="c in g.children"
                :key="c.path"
                :index="c.path"
              >
                <el-icon><component :is="c.icon" /></el-icon>
                <template #title>
                  <span>{{ c.label }}</span>
                </template>
              </el-menu-item>
            </el-sub-menu>
          </template>
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
  background: var(--ui-bg-app, #f4f6f8);
}

/* 顶部导航 */
.header {
  height: var(--ui-header-height, 56px);
  background: var(--ui-bg-surface, #fff);
  border-bottom: 1px solid var(--ui-border, #d9dee5);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 var(--ui-space-4, 16px);
  flex-shrink: 0;
  z-index: 100;
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--ui-space-3, 12px);
}

.header-title {
  font-size: var(--ui-font-size-md, 16px);
  font-weight: 600;
  color: var(--ui-text-primary, #1f2933);
}

.header-right {
  display: flex;
  align-items: center;
  gap: var(--ui-space-4, 16px);
}

.user-info {
  display: flex;
  align-items: center;
  gap: var(--ui-space-2, 8px);
  cursor: pointer;
  padding: var(--ui-space-1, 4px) var(--ui-space-2, 8px);
  border-radius: var(--ui-radius-md, 6px);
  transition: background 0.2s;
}

.user-info:hover {
  background: var(--ui-bg-subtle, #f8f9fb);
}

.username {
  font-size: var(--ui-font-size-sm, 14px);
  color: var(--ui-text-primary, #1f2933);
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
  width: var(--ui-sidebar-width, 224px);
  background: var(--ui-bg-surface, #fff);
  border-right: 1px solid var(--ui-border, #d9dee5);
  transition: width 0.3s ease;
  overflow-y: auto;
  flex-shrink: 0;
}

.sidebar.collapsed {
  width: var(--ui-sidebar-collapsed-width, 64px);
}

.sidebar :deep(.el-menu) {
  border-right: none;
}

/* 主内容 */
.content {
  flex: 1;
  overflow-y: auto;
  padding: 0;
}
</style>
