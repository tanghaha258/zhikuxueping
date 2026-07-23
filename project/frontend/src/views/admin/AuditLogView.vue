<script setup lang="ts">
/**
 * AuditLogView - 审计日志
 * 日志筛选 + 表格 + 分页
 */
import { ref } from 'vue'

const actionType = ref('')
const searchUser = ref('')
const dateRange = ref<[Date, Date] | null>(null)

/** 日志数据 */
const logs = ref([
  { id: '1', time: '2026-05-29 14:32:18', user: 'admin01', action: '用户登录', ip: '192.168.1.100', detail: '管理员 admin01 登录系统', type: 'auth' },
  { id: '2', time: '2026-05-29 14:28:05', user: 'zhanglaoshi', action: '创建项目', ip: '192.168.1.101', detail: '创建了项目"校园垃圾分类调查报告"', type: 'project' },
  { id: '3', time: '2026-05-29 14:20:33', user: 'admin01', action: '新增用户', ip: '192.168.1.100', detail: '新增了教师账号"lisi"', type: 'user' },
  { id: '4', time: '2026-05-29 13:55:12', user: 'wangming', action: '提交任务', ip: '192.168.1.102', detail: '提交了任务"调查问卷填写"', type: 'task' },
  { id: '5', time: '2026-05-29 11:30:00', user: 'lilaoshi', action: 'AI 备课', ip: '192.168.1.103', detail: '使用 AI 生成了教案"光合作用"', type: 'ai' },
  { id: '6', time: '2026-05-29 10:15:44', user: 'admin01', action: '系统设置修改', ip: '192.168.1.100', detail: '修改了注册设置（开放注册关闭）', type: 'system' },
  { id: '7', time: '2026-05-29 09:48:22', user: 'zhaoxiaoming', action: '评价提交', ip: '192.168.1.104', detail: '对任务"数据统计分析报告"进行了教师评价', type: 'evaluation' },
  { id: '8', time: '2026-05-29 09:12:07', user: 'lifang', action: '用户登出', ip: '192.168.1.105', detail: '用户 lifang 登出系统', type: 'auth' },
])

/** 操作类型选项 */
const actionTypeOptions = [
  { value: '', label: '全部类型' },
  { value: 'auth', label: '认证操作' },
  { value: 'user', label: '用户管理' },
  { value: 'project', label: '项目管理' },
  { value: 'task', label: '任务操作' },
  { value: 'evaluation', label: '评价操作' },
  { value: 'ai', label: 'AI 操作' },
  { value: 'system', label: '系统设置' },
]

/** 操作类型标签映射 */
const typeLabels: Record<string, string> = {
  auth: '认证操作',
  user: '用户管理',
  project: '项目管理',
  task: '任务操作',
  evaluation: '评价操作',
  ai: 'AI 操作',
  system: '系统设置',
}

const typeColors: Record<string, string> = {
  auth: 'default',
  user: 'primary',
  project: 'success',
  task: 'warning',
  evaluation: 'danger',
  ai: 'info',
  system: '',
}

/** 分页 */
const pagination = ref({
  currentPage: 1,
  pageSize: 10,
  total: 128,
})

function handlePageChange(page: number) {
  pagination.value.currentPage = page
}
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">审计日志</h2>

    <el-card shadow="never">
      <!-- 筛选 -->
      <div class="search-bar">
        <el-select v-model="actionType" placeholder="操作类型" style="width: 150px">
          <el-option v-for="opt in actionTypeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-input
          v-model="searchUser"
          placeholder="搜索操作用户..."
          :prefix-icon="Search"
          clearable
          style="width: 180px"
        />
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          style="width: 260px"
        />
        <el-button :icon="Search" type="primary">查询</el-button>
        <el-button :icon="Refresh">重置</el-button>
      </div>

      <!-- 日志表格 -->
      <el-table :data="logs" stripe style="width: 100%">
        <el-table-column prop="time" label="时间" width="170" />
        <el-table-column prop="user" label="操作用户" width="130" />
        <el-table-column prop="action" label="操作" width="120">
          <template #default="{ row }">
            <el-tag :type="typeColors[row.type] as any" size="small">
              {{ row.action }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="detail" label="详情" min-width="280">
          <template #default="{ row }">
            <span style="font-size: 13px;">{{ row.detail }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="ip" label="IP 地址" width="140" />
        <el-table-column prop="type" label="分类" width="100">
          <template #default="{ row }">
            <span style="font-size: 12px; color: #909399;">{{ typeLabels[row.type] || row.type }}</span>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div style="display: flex; justify-content: flex-end; margin-top: 20px;">
        <el-pagination
          v-model:current-page="pagination.currentPage"
          :page-size="pagination.pageSize"
          :total="pagination.total"
          background
          layout="total, prev, pager, next, jumper"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>
  </div>
</template>
