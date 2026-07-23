<script setup lang="ts">
/**
 * TeacherDashboard - 教师工作台
 * 欢迎区域 + 统计卡片 + 项目列表 + 待办事项
 */
import { ref, onMounted } from 'vue'
import { useUserStore } from '@/stores/user'
import { listProjectsApi } from '@/api/projects'
import { getTaskStatsApi } from '@/api/tasks'

const userStore = useUserStore()

const stats = ref([
  { title: '进行中的项目', value: 0, icon: 'FolderOpened', color: '#409EFF' },
  { title: '待评价任务', value: 0, icon: 'EditPen', color: '#E6A23C' },
  { title: '资源总数', value: 0, icon: 'Files', color: '#67C23A' },
  { title: '本周待办', value: 0, icon: 'Clock', color: '#F56C6C' },
])

const recentProjects = ref<any[]>([])
const todos = ref([
  { task: '评价学生"水资源保护"项目报告', time: '今日截止', priority: 'urgent' as const },
  { task: '审阅第3小组的跨学科项目方案', time: '明天截止', priority: 'normal' as const },
  { task: '完善智能备课"光合作用"教案', time: '3天后截止', priority: 'normal' as const },
])

onMounted(async () => {
  try {
    const res = await listProjectsApi({})
    const projects = res.data.data.items || []
    const active = projects.filter((p) => p.status === 'active')
    recentProjects.value = active.slice(0, 3).map((p) => ({
      name: p.title,
      subject: p.subjectIds?.join('·') || '',
      status: '进行中',
      deadline: p.endDate || '',
    }))
  } catch {
    /* recentProjects stays empty */
  }

  try {
    const res = await getTaskStatsApi()
    const s = res.data.data
    stats.value[0].value = s.activeProjects ?? 0
    stats.value[1].value = s.pendingEvaluation ?? 0
    stats.value[2].value = s.totalResources ?? 0
    stats.value[3].value = s.upcomingDeadlines ?? 0
  } catch {
    stats.value[1].value = 0
    stats.value[2].value = 0
    stats.value[3].value = 0
  }
})
</script>

<template>
  <div class="page-container">
    <!-- 欢迎区域 -->
    <div class="welcome-section">
      <div class="welcome-text">
        <h2 class="welcome-title">欢迎回来，{{ userStore.displayName }}老师</h2>
        <p class="welcome-desc">今天也是充满教学灵感的一天！以下是您的工作概览。</p>
      </div>
      <el-button type="primary" :icon="Plus">创建新项目</el-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-cards">
      <el-card
        v-for="stat in stats"
        :key="stat.title"
        shadow="hover"
        class="stat-card"
      >
        <div class="stat-card-inner">
          <div class="stat-info">
            <p class="stat-value">{{ stat.value }}</p>
            <p class="stat-title">{{ stat.title }}</p>
          </div>
          <el-icon :size="40" :color="stat.color">
            <component :is="stat.icon" />
          </el-icon>
        </div>
      </el-card>
    </div>

    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
      <!-- 进行中的项目 -->
      <el-card shadow="never">
        <template #header>
          <div class="flex-between">
            <span class="card-title">进行中的项目</span>
            <el-link type="primary" href="#/teacher/projects">查看全部</el-link>
          </div>
        </template>
        <div v-for="(project, idx) in recentProjects" :key="idx" class="project-item">
          <div class="project-info">
            <p class="project-name">{{ project.name }}</p>
            <p class="project-subject">{{ project.subject }}</p>
          </div>
          <div class="project-meta">
            <el-tag :type="project.status === '进行中' ? 'primary' : 'info'" size="small">
              {{ project.status }}
            </el-tag>
            <span class="project-deadline">截止: {{ project.deadline }}</span>
          </div>
        </div>
        <div v-if="recentProjects.length === 0" class="empty-state">
          <el-empty description="暂无进行中的项目" />
        </div>
      </el-card>

      <!-- 待办事项 -->
      <el-card shadow="never">
        <template #header>
          <span class="card-title">待办事项</span>
        </template>
        <div v-for="(todo, idx) in todos" :key="idx" class="todo-item">
          <div class="todo-content">
            <p class="todo-task">{{ todo.task }}</p>
            <p class="todo-time" :class="{ urgent: todo.priority === 'urgent' }">
              {{ todo.time }}
            </p>
          </div>
        </div>
        <div v-if="todos.length === 0" class="empty-state">
          <el-empty description="暂无待办事项" />
        </div>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.welcome-section {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.welcome-title {
  font-size: 22px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.welcome-desc {
  font-size: 14px;
  color: #909399;
  margin: 6px 0 0;
}

.stat-card {
  border-radius: 8px;
}

.stat-card-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  color: #303133;
  margin: 0;
}

.stat-title {
  font-size: 14px;
  color: #909399;
  margin: 4px 0 0;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.project-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;

  &:last-child {
    border-bottom: none;
  }
}

.project-name {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin: 0 0 4px;
}

.project-subject {
  font-size: 12px;
  color: #909399;
  margin: 0;
}

.project-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.project-deadline {
  font-size: 12px;
  color: #909399;
  white-space: nowrap;
}

.todo-item {
  padding: 12px 0;
  border-bottom: 1px solid #f0f0f0;

  &:last-child {
    border-bottom: none;
  }
}

.todo-task {
  font-size: 14px;
  color: #303133;
  margin: 0 0 4px;
  line-height: 1.5;
}

.todo-time {
  font-size: 12px;
  color: #909399;
  margin: 0;

  &.urgent {
    color: #f56c6c;
  }
}
</style>
