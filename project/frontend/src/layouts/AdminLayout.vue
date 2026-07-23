<script setup lang="ts">
/**
 * AdminLayout - 管理端布局
 * 左侧菜单 + 顶部面包屑 + 内容区
 */
import { ref, computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

/** 管理端菜单项 */
const menuItems = [
  {
    path: '/admin/dashboard',
    icon: 'Odometer',
    label: '系统概览',
  },
  {
    path: '/admin/users',
    icon: 'User',
    label: '用户管理',
  },
  {
    path: '/admin/classes',
    icon: 'Collection',
    label: '班级管理',
  },
  {
    path: '/admin/settings',
    icon: 'Setting',
    label: '系统设置',
  },
  {
    path: '/admin/ai-config',
    icon: 'MagicStick',
    label: 'AI 配置',
  },
  {
    path: '/admin/prompt-templates',
    icon: 'ChatLineSquare',
    label: '提示词模板',
  },
  {
    path: '/admin/templates',
    icon: 'CopyDocument',
    label: '模板管理',
  },
  {
    path: '/admin/logs',
    icon: 'Document',
    label: '审计日志',
  },
]

/** 当前激活菜单 */
const activeMenu = computed(() => route.path)

/** 侧边栏折叠 */
const isCollapsed = ref(false)

/** 菜单选择处理 */
function handleMenuSelect(index: string) {
  router.push(index)
}

/** 下拉菜单命令处理 */
function handleCommand(cmd: string) {
  if (cmd === 'logout') {
    userStore.logout()
  } else if (cmd === 'profile') {
    router.push('/admin/profile')
  }
}

/** 面包屑计算 */
const breadcrumbItems = computed(() => {
  const matched = route.matched.filter((r) => r.meta?.title)
  return matched.map((r) => ({
    title: r.meta?.title as string || '',
    path: r.path,
  }))
})
</script>

<template>
  <div class="admin-layout">
    <!-- 左侧菜单 -->
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="sidebar-header" @click="router.push('/admin/dashboard')">
        <el-icon :size="28" color="#fff"><School /></el-icon>
        <span v-show="!isCollapsed" class="sidebar-title">管理后台</span>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        background-color="#1d1e1f"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
        @select="handleMenuSelect"
      >
        <el-menu-item v-for="item in menuItems" :key="item.path" :index="item.path">
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <template #title>
            <span>{{ item.label }}</span>
          </template>
        </el-menu-item>
      </el-menu>

      <div class="sidebar-footer">
        <el-button
          :icon="isCollapsed ? 'Expand' : 'Fold'"
          text
          style="color: #bfcbd9; width: 100%"
          @click="isCollapsed = !isCollapsed"
        />
      </div>
    </aside>

    <!-- 右侧区域 -->
    <div class="main-area">
      <!-- 顶部 -->
      <header class="header">
        <div class="header-left">
          <el-breadcrumb separator="/">
            <el-breadcrumb-item
              v-for="item in breadcrumbItems"
              :key="item.path"
              :to="item.path"
            >
              {{ item.title }}
            </el-breadcrumb-item>
          </el-breadcrumb>
        </div>

        <div class="header-right">
          <el-dropdown trigger="click" @command="handleCommand">
            <span class="user-info">
              <el-avatar :size="28" :icon="UserFilled" />
              <span class="username">{{ userStore.displayName }}</span>
              <el-icon><ArrowDown /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="profile">
                  <el-icon><User /></el-icon>个人中心
                </el-dropdown-item>
                <el-dropdown-item divided command="logout">
                  <el-icon><SwitchButton /></el-icon>退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 内容区 -->
      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<style scoped>
.admin-layout {
  display: flex;
  height: 100vh;
  background: #f0f2f5;
}

/* 侧边栏 */
.sidebar {
  width: 240px;
  background: #1d1e1f;
  display: flex;
  flex-direction: column;
  transition: width 0.3s;
  flex-shrink: 0;

  &.collapsed {
    width: 64px;
  }

  :deep(.el-menu) {
    border-right: none;
  }
}

.sidebar-header {
  height: 60px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  cursor: pointer;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

.sidebar-title {
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  white-space: nowrap;
}

.sidebar-footer {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding: 8px;
  margin-top: auto;
}

/* 主区域 */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.header {
  height: 50px;
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  border-bottom: 1px solid #e4e7ed;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
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
  border-radius: 4px;

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
  padding: 0;
}
</style>
