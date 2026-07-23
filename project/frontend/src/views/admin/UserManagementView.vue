<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { listUsersApi, createUserApi, updateUserApi, toggleUserStatusApi } from '@/api/users'
import { listSchoolsApi } from '@/api/schools'
import type { UserInfo, School } from '@/types'

const loading = ref(false)
const users = ref<UserInfo[]>([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const schools = ref<School[]>([])

const searchKey = ref('')
const roleFilter = ref('')
const statusFilter = ref('')
const dialogVisible = ref(false)
const dialogTitle = ref('新增用户')
const isEditing = ref(false)
const editingId = ref('')
const formLoading = ref(false)

const roleLabels: Record<string, string> = {
  admin: '系统管理员',
  school_admin: '学校管理员',
  teacher: '教师',
  student: '学生',
  parent: '家长',
}

const roleOptions = [
  { value: '', label: '全部角色' },
  { value: 'admin', label: '系统管理员' },
  { value: 'school_admin', label: '学校管理员' },
  { value: 'teacher', label: '教师' },
  { value: 'student', label: '学生' },
  { value: 'parent', label: '家长' },
]

const form = reactive({
  username: '',
  displayName: '',
  email: '',
  password: '',
  role: 'teacher',
  schoolId: '',
})

const rules: Record<string, unknown> = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  displayName: [{ required: true, message: '请输入姓名', trigger: 'blur' }],
  email: [{ required: true, message: '请输入邮箱', trigger: 'blur' }],
}

async function loadSchools() {
  try {
    const res = await listSchoolsApi()
    schools.value = res.data.data || []
  } catch {
    schools.value = []
  }
}

async function loadUsers() {
  loading.value = true
  try {
    const params: Record<string, unknown> = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value,
      keyword: searchKey.value || undefined,
      role: roleFilter.value || undefined,
    }
    if (statusFilter.value === 'active') params.is_active = true
    else if (statusFilter.value === 'disabled') params.is_active = false

    const res = await listUsersApi(params as any)
    const d = res.data.data
    users.value = d.items || []
    total.value = d.total || 0
  } catch {
    users.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadSchools()
  loadUsers()
})

watch([searchKey, roleFilter, statusFilter], () => {
  page.value = 1
  loadUsers()
})

function onPageChange(p: number) {
  page.value = p
  loadUsers()
}

function resetFilters() {
  searchKey.value = ''
  roleFilter.value = ''
  statusFilter.value = ''
}

function openCreate() {
  isEditing.value = false
  dialogTitle.value = '新增用户'
  editingId.value = ''
  form.username = ''
  form.displayName = ''
  form.email = ''
  form.password = ''
  form.role = 'teacher'
  form.schoolId = ''
  dialogVisible.value = true
}

function openEdit(row: UserInfo) {
  isEditing.value = true
  dialogTitle.value = '编辑用户'
  editingId.value = row.id
  form.username = row.username
  form.displayName = row.displayName
  form.email = row.email
  form.password = ''
  form.role = row.role
  form.schoolId = row.schoolId || ''
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.username || !form.displayName) {
    ElMessage.warning('请填写必填字段')
    return
  }
  if (!isEditing.value && !form.password) {
    ElMessage.warning('请设置密码')
    return
  }
  if (!isEditing.value && form.password.length < 6) {
    ElMessage.warning('密码长度至少 6 位')
    return
  }

  formLoading.value = true
  try {
    if (isEditing.value) {
      const payload: Record<string, unknown> = {
        display_name: form.displayName,
        email: form.email,
        role: form.role,
      }
      if (form.password) payload.password = form.password
      if (form.schoolId) payload.school_id = form.schoolId
      await updateUserApi(editingId.value, payload as any)
      ElMessage.success('用户更新成功')
    } else {
      await createUserApi({
        username: form.username,
        password: form.password,
        email: form.email,
        display_name: form.displayName,
        role: form.role,
        school_id: form.schoolId || undefined,
      })
      ElMessage.success('用户创建成功')
    }
    dialogVisible.value = false
    loadUsers()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '操作失败')
  } finally {
    formLoading.value = false
  }
}

async function toggleStatus(row: UserInfo) {
  const action = row.isActive ? '禁用' : '启用'
  try {
    await ElMessageBox.confirm(`确认${action}用户「${row.displayName}」？`, '提示')
  } catch {
    return
  }
  try {
    await toggleUserStatusApi(row.id)
    ElMessage.success(`${action}成功`)
    loadUsers()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '操作失败')
  }
}

async function handleDelete(row: UserInfo) {
  ElMessage.info('删除功能开发中')
}
</script>

<template>
  <div class="page-container">
    <div class="action-bar">
      <h2 class="page-title" style="margin-bottom: 0;">用户管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增用户</el-button>
    </div>

    <el-card shadow="never">
      <div class="search-bar">
        <el-input
          v-model="searchKey"
          placeholder="搜索用户名/姓名..."
          :prefix-icon="Search"
          clearable
          style="width: 260px"
        />
        <el-select v-model="roleFilter" placeholder="角色筛选" style="width: 140px" clearable>
          <el-option v-for="opt in roleOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-select v-model="statusFilter" placeholder="状态筛选" style="width: 120px" clearable>
          <el-option label="全部状态" value="" />
          <el-option label="已启用" value="active" />
          <el-option label="已禁用" value="disabled" />
        </el-select>
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>

      <el-table :data="users" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="username" label="用户名" width="140" />
        <el-table-column prop="displayName" label="姓名" width="120" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column prop="role" label="角色" width="130">
          <template #default="{ row }">
            <el-tag size="small">
              {{ roleLabels[row.role] || row.role }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="isActive" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.isActive ? 'success' : 'info'" size="small">
              {{ row.isActive ? '已启用' : '已禁用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button
              text
              :type="row.isActive ? 'warning' : 'success'"
              size="small"
              @click="toggleStatus(row)"
            >
              {{ row.isActive ? '禁用' : '启用' }}
            </el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          @current-change="onPageChange"
        />
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="520px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" :rules="rules as any" label-position="top">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="用户名" prop="username">
              <el-input v-model="form.username" :disabled="isEditing" placeholder="请输入用户名" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="姓名" prop="displayName">
              <el-input v-model="form.displayName" placeholder="请输入姓名" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="邮箱" prop="email">
          <el-input v-model="form.email" placeholder="请输入邮箱" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="密码" :prop="isEditing ? '' : 'password'">
              <el-input
                v-model="form.password"
                type="password"
                show-password
                :placeholder="isEditing ? '留空不修改' : '请输入密码'"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="角色">
              <el-select v-model="form.role" style="width: 100%">
                <el-option label="教师" value="teacher" />
                <el-option label="学生" value="student" />
                <el-option label="学校管理员" value="school_admin" />
                <el-option label="家长" value="parent" />
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="所属学校">
          <el-select v-model="form.schoolId" clearable placeholder="选择学校" style="width: 100%">
            <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">确认</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.search-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
</style>
