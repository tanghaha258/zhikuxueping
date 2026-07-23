<script setup lang="ts">
/**
 * AuthLayout - 认证页面布局
 * 居中卡片式布局，用于登录、注册等页面
 */
</script>

<template>
  <div class="auth-layout">
    <div class="auth-container">
      <!-- Logo & 标题 -->
      <div class="auth-header">
        <div class="auth-logo">
          <el-icon :size="48" color="#409EFF">
            <School />
          </el-icon>
        </div>
        <h1 class="auth-title">初中跨学科教学评一体化平台</h1>
        <p class="auth-subtitle">Cross-Subject Teaching & Evaluation Platform</p>
      </div>

      <!-- 内容区（登录表单等） -->
      <div class="auth-content">
        <router-view />
      </div>

      <!-- 底部信息 -->
      <div class="auth-footer">
        <span>&copy; 2026 NZSK 科技 版权所有</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-layout {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  background-size: cover;
  padding: 20px;
}

.auth-container {
  width: 100%;
  max-width: 460px;
  background: #fff;
  border-radius: 16px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.15);
  padding: 40px 36px;
}

.auth-header {
  text-align: center;
  margin-bottom: 32px;
}

.auth-logo {
  margin-bottom: 16px;
  display: flex;
  justify-content: center;
}

.auth-title {
  font-size: 22px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 8px;
  letter-spacing: 1px;
}

.auth-subtitle {
  font-size: 13px;
  color: #909399;
  margin: 0;
}

.auth-content {
  margin-bottom: 24px;
}

.auth-footer {
  text-align: center;
  font-size: 12px;
  color: #c0c4cc;
}
</style>
