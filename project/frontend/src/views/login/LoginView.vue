<script setup lang="ts">
/**
 * LoginView - 登录页面
 * 账号密码登录，系统根据用户角色自动分配首页
 */
import { ref, reactive } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'
import { STORAGE_KEYS } from '@/utils/constants'
import { User, Lock, View, Hide } from '@element-plus/icons-vue'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

/** 登录表单 */
const loginForm = reactive({
  username: localStorage.getItem(STORAGE_KEYS.REMEMBERED_USERNAME) || '',
  password: '',
  rememberPassword: !!localStorage.getItem(STORAGE_KEYS.REMEMBERED_USERNAME),
})

/** 表单校验规则 */
const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

const formRef = ref<InstanceType<typeof import('element-plus')['ElForm']> | null>(null)

const loading = ref(false)
const showPassword = ref(false)

/** 登录 */
async function handleLogin() {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await userStore.login({
      username: loginForm.username,
      password: loginForm.password,
    })

    // 记住密码
    if (loginForm.rememberPassword) {
      localStorage.setItem(STORAGE_KEYS.REMEMBERED_USERNAME, loginForm.username)
    } else {
      localStorage.removeItem(STORAGE_KEYS.REMEMBERED_USERNAME)
    }

    ElMessage.success('登录成功')

    // 跳转到 redirect 参数指定的页面或角色首页
    const redirect = (route.query.redirect as string) || userStore.homeRoute
    router.push(redirect)
  } catch (error: any) {
    ElMessage.error(error?.response?.data?.message || '登录失败，请检查用户名和密码')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-view">
    <el-form
      ref="formRef"
      :model="loginForm"
      :rules="rules"
      label-position="top"
      size="large"
      @keyup.enter="handleLogin"
    >
      <!-- 用户名 -->
      <el-form-item label="用户名" prop="username">
        <el-input
          v-model="loginForm.username"
          placeholder="请输入用户名"
          :prefix-icon="User"
        />
      </el-form-item>

      <!-- 密码 -->
      <el-form-item label="密码" prop="password">
        <el-input
          v-model="loginForm.password"
          :type="showPassword ? 'text' : 'password'"
          placeholder="请输入密码"
          :prefix-icon="Lock"
          show-password
        >
          <template #suffix>
            <el-icon
              :size="18"
              style="cursor: pointer"
              @click="showPassword = !showPassword"
            >
              <View v-if="showPassword" />
              <Hide v-else />
            </el-icon>
          </template>
        </el-input>
      </el-form-item>

      <!-- 记住密码 -->
      <el-form-item>
        <el-checkbox v-model="loginForm.rememberPassword">记住密码</el-checkbox>
      </el-form-item>

      <!-- 登录按钮 -->
      <el-form-item>
        <el-button
          type="primary"
          size="large"
          :loading="loading"
          style="width: 100%"
          @click="handleLogin"
        >
          登 录
        </el-button>
      </el-form-item>
    </el-form>

    <!-- 注册入口 -->
    <div class="register-link">
      还没有账号？
      <el-link type="primary" :underline="false" @click="$router.push('/register')">立即注册</el-link>
    </div>
  </div>
</template>

<style scoped>
.login-view {
  width: 100%;
}

.register-link {
  text-align: center;
  font-size: 14px;
  color: #909399;
  margin-top: 8px;
}
</style>
