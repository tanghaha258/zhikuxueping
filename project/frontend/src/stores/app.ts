// ============================================================
// 应用状态管理 (Pinia)
// ============================================================

import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Project } from '@/types'

export const useAppStore = defineStore('app', () => {
  // ============================================================
  // State
  // ============================================================

  /** 侧边栏折叠状态 */
  const sidebarCollapsed = ref(false)

  /** 当前选中的项目（各页面上下文共享） */
  const currentProject = ref<Project | null>(null)

  // ============================================================
  // Actions
  // ============================================================

  /** 切换侧边栏 */
  function toggleSidebar(): void {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  /** 设置侧边栏状态 */
  function setSidebarCollapsed(collapsed: boolean): void {
    sidebarCollapsed.value = collapsed
  }

  /** 设置当前项目 */
  function setCurrentProject(project: Project | null): void {
    currentProject.value = project
  }

  return {
    // state
    sidebarCollapsed,
    currentProject,
    // actions
    toggleSidebar,
    setSidebarCollapsed,
    setCurrentProject,
  }
})
