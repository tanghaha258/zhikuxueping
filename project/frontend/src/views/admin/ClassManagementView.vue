<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Search, Refresh } from '@element-plus/icons-vue'
import { listSchoolsApi, listClassesBySchoolApi, createClassApi, updateClassApi, deleteClassApi } from '@/api/schools'
import type { School, ClassItem } from '@/types'

const loading = ref(false)
const allClasses = ref<ClassItem[]>([])
const schools = ref<School[]>([])

const schoolFilter = ref('')
const gradeFilter = ref('')
const searchKey = ref('')
const dialogVisible = ref(false)
const dialogTitle = ref('新增班级')
const isEditing = ref(false)
const editingId = ref('')
const formLoading = ref(false)

const gradeOptions = [
  { value: '', label: '全部年级' },
  { value: '七年级', label: '七年级' },
  { value: '八年级', label: '八年级' },
  { value: '九年级', label: '九年级' },
]

const filteredClasses = computed(() => {
  let list = allClasses.value
  if (schoolFilter.value) {
    list = list.filter(c => c.schoolId === schoolFilter.value)
  }
  if (gradeFilter.value) {
    list = list.filter(c => c.grade === gradeFilter.value)
  }
  if (searchKey.value) {
    const kw = searchKey.value.toLowerCase()
    list = list.filter(c => c.name.toLowerCase().includes(kw))
  }
  return list
})

function schoolName(schoolId: string): string {
  return schools.value.find(s => s.id === schoolId)?.name || schoolId
}

const form = reactive({
  name: '',
  grade: '七年级',
  schoolId: '',
  headTeacherId: '',
})

async function loadSchools() {
  try {
    const res = await listSchoolsApi()
    schools.value = res.data.data || []
  } catch {
    schools.value = []
  }
}

async function loadClasses() {
  if (!schoolFilter.value) {
    allClasses.value = []
    return
  }
  loading.value = true
  try {
    const res = await listClassesBySchoolApi(schoolFilter.value)
    allClasses.value = res.data.data || []
  } catch {
    allClasses.value = []
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadSchools()
})

watch(schoolFilter, () => {
  gradeFilter.value = ''
  searchKey.value = ''
  loadClasses()
})

function resetFilters() {
  schoolFilter.value = ''
  gradeFilter.value = ''
  searchKey.value = ''
  allClasses.value = []
}

function openCreate() {
  if (!schoolFilter.value) {
    ElMessage.warning('请先选择一个学校')
    return
  }
  isEditing.value = false
  dialogTitle.value = '新增班级'
  editingId.value = ''
  form.name = ''
  form.grade = '七年级'
  form.schoolId = schoolFilter.value
  form.headTeacherId = ''
  dialogVisible.value = true
}

function openEdit(row: ClassItem) {
  isEditing.value = true
  dialogTitle.value = '编辑班级'
  editingId.value = row.id
  form.name = row.name
  form.grade = row.grade
  form.schoolId = row.schoolId
  form.headTeacherId = row.headTeacherId || ''
  dialogVisible.value = true
}

async function handleSave() {
  if (!form.name || !form.grade) {
    ElMessage.warning('请填写班级名称和年级')
    return
  }

  formLoading.value = true
  try {
    if (isEditing.value) {
      const payload: Record<string, unknown> = { name: form.name, grade: form.grade }
      if (form.headTeacherId) payload.head_teacher_id = form.headTeacherId
      await updateClassApi(editingId.value, payload as any)
      ElMessage.success('班级更新成功')
    } else {
      const payload: Record<string, unknown> = { name: form.name, grade: form.grade }
      if (form.headTeacherId) payload.head_teacher_id = form.headTeacherId
      await createClassApi(form.schoolId, payload as any)
      ElMessage.success('班级创建成功')
    }
    dialogVisible.value = false
    loadClasses()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '操作失败')
  } finally {
    formLoading.value = false
  }
}

async function handleDelete(row: ClassItem) {
  try {
    await ElMessageBox.confirm(`确认删除班级「${row.name}」？此操作不可恢复。`, '警告', {
      confirmButtonText: '确认删除',
      confirmButtonClass: 'el-button--danger',
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await deleteClassApi(row.id)
    ElMessage.success('班级已删除')
    loadClasses()
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '删除失败')
  }
}
</script>

<template>
  <div class="page-container">
    <div class="action-bar">
      <h2 class="page-title" style="margin-bottom: 0;">班级管理</h2>
      <el-button type="primary" :icon="Plus" @click="openCreate">新增班级</el-button>
    </div>

    <el-card shadow="never">
      <div class="search-bar">
        <el-select v-model="schoolFilter" placeholder="选择学校" style="width: 200px" clearable>
          <el-option v-for="s in schools" :key="s.id" :label="s.name" :value="s.id" />
        </el-select>
        <el-select v-model="gradeFilter" placeholder="年级筛选" style="width: 130px" clearable>
          <el-option v-for="opt in gradeOptions" :key="opt.value" :label="opt.label" :value="opt.value" />
        </el-select>
        <el-input
          v-model="searchKey"
          placeholder="搜索班级名称..."
          :prefix-icon="Search"
          clearable
          style="width: 200px"
        />
        <el-button :icon="Refresh" @click="resetFilters">重置</el-button>
      </div>

      <el-table :data="filteredClasses" v-loading="loading" stripe style="width: 100%">
        <el-table-column prop="name" label="班级名称" min-width="160" />
        <el-table-column prop="grade" label="年级" width="100" />
        <el-table-column label="所属学校" width="180">
          <template #default="{ row }">
            {{ schoolName(row.schoolId) }}
          </template>
        </el-table-column>
        <el-table-column prop="createdAt" label="创建时间" width="120" />
        <el-table-column label="操作" width="160" fixed="right">
          <template #default="{ row }">
            <el-button text type="primary" size="small" @click="openEdit(row)">编辑</el-button>
            <el-button text type="danger" size="small" @click="handleDelete(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <div v-if="!schoolFilter && !loading" class="empty-hint">
        请选择学校以查看班级列表
      </div>
    </el-card>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="460px"
      :close-on-click-modal="false"
    >
      <el-form :model="form" label-position="top">
        <el-form-item label="班级名称" required>
          <el-input v-model="form.name" placeholder="如：七年级（3）班" />
        </el-form-item>

        <el-row :gutter="16">
          <el-col :span="12">
            <el-form-item label="年级" required>
              <el-select v-model="form.grade" style="width: 100%">
                <el-option label="七年级" value="七年级" />
                <el-option label="八年级" value="八年级" />
                <el-option label="九年级" value="九年级" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属学校">
              <el-input :model-value="schoolName(form.schoolId)" disabled />
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="formLoading" @click="handleSave">
          {{ isEditing ? '保存修改' : '确认创建' }}
        </el-button>
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

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.empty-hint {
  text-align: center;
  padding: 60px 0;
  color: #909399;
  font-size: 14px;
}
</style>
