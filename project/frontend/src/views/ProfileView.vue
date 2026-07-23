<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { updateProfileApi, changePasswordApi } from '@/api/auth'

const userStore = useUserStore()
const activeTab = ref('profile')

const profileForm = reactive({
  displayName: '',
  email: '',
  phone: '',
})
const profileLoading = ref(false)

const passwordForm = reactive({
  oldPassword: '',
  newPassword: '',
  confirmPassword: '',
})
const passwordLoading = ref(false)

const roleLabels: Record<string, string> = {
  admin: '系统管理员',
  school_admin: '学校管理员',
  teacher: '教师',
  student: '学生',
  parent: '家长',
}

onMounted(() => {
  if (userStore.userInfo) {
    profileForm.displayName = userStore.userInfo.displayName
    profileForm.email = userStore.userInfo.email
    profileForm.phone = userStore.userInfo.phone || ''
  }
})

async function saveProfile() {
  profileLoading.value = true
  try {
    const payload: Record<string, string> = {}
    if (profileForm.displayName !== userStore.userInfo?.displayName) {
      payload.display_name = profileForm.displayName
    }
    if (profileForm.email !== userStore.userInfo?.email) {
      payload.email = profileForm.email
    }
    if (profileForm.phone !== (userStore.userInfo?.phone || '')) {
      payload.phone = profileForm.phone
    }
    if (Object.keys(payload).length === 0) {
      ElMessage.info('未检测到信息变更')
      return
    }
    const res = await updateProfileApi(payload as any)
    userStore.setUserInfo(res.data.data)
    ElMessage.success('个人信息更新成功')
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '更新失败')
  } finally {
    profileLoading.value = false
  }
}

async function changePassword() {
  if (!passwordForm.oldPassword) {
    ElMessage.warning('请输入原密码')
    return
  }
  if (!passwordForm.newPassword) {
    ElMessage.warning('请输入新密码')
    return
  }
  if (passwordForm.newPassword.length < 6) {
    ElMessage.warning('新密码长度至少 6 位')
    return
  }
  if (passwordForm.newPassword !== passwordForm.confirmPassword) {
    ElMessage.warning('两次输入的密码不一致')
    return
  }

  passwordLoading.value = true
  try {
    await changePasswordApi({
      old_password: passwordForm.oldPassword,
      new_password: passwordForm.newPassword,
    })
    ElMessage.success('密码修改成功')
    passwordForm.oldPassword = ''
    passwordForm.newPassword = ''
    passwordForm.confirmPassword = ''
  } catch (err: any) {
    ElMessage.error(err?.response?.data?.message || '密码修改失败')
  } finally {
    passwordLoading.value = false
  }
}
</script>

<template>
  <div class="page-container" style="max-width: 640px; margin: 0 auto; padding: 24px;">
    <h2 class="page-title">个人中心</h2>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="个人信息" name="profile">
          <div class="profile-header">
            <el-avatar :size="72" :icon="'UserFilled'" />
            <div class="profile-meta">
              <p class="profile-name">{{ userStore.displayName }}</p>
              <p class="profile-role">{{ roleLabels[userStore.userRole] || userStore.userRole }}</p>
            </div>
          </div>

          <el-form :model="profileForm" label-position="top" style="margin-top: 24px;">
            <el-row :gutter="16">
              <el-col :span="12">
                <el-form-item label="用户名">
                  <el-input :model-value="userStore.userInfo?.username" disabled />
                </el-form-item>
              </el-col>
              <el-col :span="12">
                <el-form-item label="显示名称">
                  <el-input v-model="profileForm.displayName" placeholder="请输入显示名称" />
                </el-form-item>
              </el-col>
            </el-row>

            <el-form-item label="邮箱">
              <el-input v-model="profileForm.email" placeholder="请输入邮箱" />
            </el-form-item>

            <el-form-item label="手机号">
              <el-input v-model="profileForm.phone" placeholder="请输入手机号" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="profileLoading" @click="saveProfile">
                保存修改
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="修改密码" name="password">
          <el-form :model="passwordForm" label-position="top" style="max-width: 400px;">
            <el-form-item label="原密码">
              <el-input
                v-model="passwordForm.oldPassword"
                type="password"
                show-password
                placeholder="请输入原密码"
              />
            </el-form-item>

            <el-form-item label="新密码">
              <el-input
                v-model="passwordForm.newPassword"
                type="password"
                show-password
                placeholder="至少 6 位字符"
              />
            </el-form-item>

            <el-form-item label="确认新密码">
              <el-input
                v-model="passwordForm.confirmPassword"
                type="password"
                show-password
                placeholder="再次输入新密码"
              />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" :loading="passwordLoading" @click="changePassword">
                修改密码
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<style scoped>
.profile-header {
  display: flex;
  align-items: center;
  gap: 20px;
  padding-bottom: 20px;
  border-bottom: 1px solid #f0f0f0;
}

.profile-name {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 0 0 4px;
}

.profile-role {
  font-size: 14px;
  color: #909399;
  margin: 0;
}
</style>
