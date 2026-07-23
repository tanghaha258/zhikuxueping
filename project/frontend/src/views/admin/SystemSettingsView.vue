<script setup lang="ts">
/**
 * SystemSettings - 系统设置
 * 系统基本信息 + 注册设置
 */
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'

const activeTab = ref('basic')

/** 系统基本信息表单 */
const basicForm = reactive({
  platformName: '初中跨学科教学评一体化平台',
  platformLogo: '',
  icpRecord: '沪ICP备2026xxxx号',
  copyright: '© 2026 NZSK 科技',
  contactEmail: 'admin@nzsk.com',
  contactPhone: '400-888-0000',
})

/** 注册设置表单 */
const registerForm = reactive({
  enableRegister: true,
  defaultRole: 'student' as string,
  requireEmailVerify: false,
  requireAdminApprove: true,
  maxSchools: 100,
})

/** 保存基本信息 */
function saveBasic() {
  ElMessage.success('基本信息已保存')
}

/** 保存注册设置 */
function saveRegister() {
  ElMessage.success('注册设置已保存')
}
</script>

<template>
  <div class="page-container">
    <h2 class="page-title">系统设置</h2>

    <el-card shadow="never">
      <el-tabs v-model="activeTab">
        <el-tab-pane label="基本信息" name="basic">
          <el-form :model="basicForm" label-position="left" label-width="140px" style="max-width: 600px; margin-top: 16px;">
            <el-form-item label="平台名称">
              <el-input v-model="basicForm.platformName" />
            </el-form-item>

            <el-form-item label="平台 Logo">
              <el-upload
                action="#"
                :auto-upload="false"
                :show-file-list="false"
              >
                <el-button :icon="Upload">上传 Logo</el-button>
                <template #tip>
                  <span style="font-size: 12px; color: #909399; margin-left: 8px;">建议尺寸 200x200，PNG 格式</span>
                </template>
              </el-upload>
            </el-form-item>

            <el-form-item label="ICP 备案号">
              <el-input v-model="basicForm.icpRecord" />
            </el-form-item>

            <el-form-item label="版权信息">
              <el-input v-model="basicForm.copyright" />
            </el-form-item>

            <el-form-item label="联系邮箱">
              <el-input v-model="basicForm.contactEmail" />
            </el-form-item>

            <el-form-item label="联系电话">
              <el-input v-model="basicForm.contactPhone" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveBasic">保存设置</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <el-tab-pane label="注册设置" name="register">
          <el-form :model="registerForm" label-position="left" label-width="180px" style="max-width: 600px; margin-top: 16px;">
            <el-form-item label="允许开放注册">
              <el-switch v-model="registerForm.enableRegister" active-text="开启" inactive-text="关闭" />
            </el-form-item>

            <el-form-item label="新用户默认角色">
              <el-select v-model="registerForm.defaultRole" style="width: 140px">
                <el-option label="学生" value="student" />
                <el-option label="教师" value="teacher" />
                <el-option label="家长" value="parent" />
              </el-select>
            </el-form-item>

            <el-form-item label="需要邮箱验证">
              <el-switch v-model="registerForm.requireEmailVerify" active-text="开启" inactive-text="关闭" />
            </el-form-item>

            <el-form-item label="需要管理员审批">
              <el-switch v-model="registerForm.requireAdminApprove" active-text="开启" inactive-text="关闭" />
            </el-form-item>

            <el-form-item label="最大学校数">
              <el-input-number v-model="registerForm.maxSchools" :min="1" :max="9999" />
            </el-form-item>

            <el-form-item>
              <el-button type="primary" @click="saveRegister">保存设置</el-button>
              <el-button @click="Object.assign(registerForm, { enableRegister: true, defaultRole: 'student', requireEmailVerify: false, requireAdminApprove: true, maxSchools: 100 })">
                恢复默认
              </el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>
