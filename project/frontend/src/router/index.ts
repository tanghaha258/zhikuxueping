// ============================================================
// 路由配置
// ============================================================

import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'

// 布局组件
import AuthLayout from '@/layouts/AuthLayout.vue'
import TeacherLayout from '@/layouts/TeacherLayout.vue'
import StudentLayout from '@/layouts/StudentLayout.vue'
import AdminLayout from '@/layouts/AdminLayout.vue'

// ============================================================
// 路由表
// ============================================================

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    component: AuthLayout,
    children: [
      {
        path: '',
        name: 'Login',
        component: () => import('@/views/login/LoginView.vue'),
        meta: { title: '登录', requiresAuth: false },
      },
    ],
  },

  // ============================================================
  // 教师端路由
  // ============================================================
  {
    path: '/teacher',
    component: TeacherLayout,
    meta: { requiresAuth: true, roles: ['teacher', 'school_admin'] },
    children: [
      {
        path: 'profile',
        name: 'TeacherProfile',
        component: () => import('@/views/ProfileView.vue'),
        meta: { title: '个人中心' },
      },
      {
        path: 'dashboard',
        name: 'TeacherDashboard',
        component: () => import('@/views/teacher/DashboardView.vue'),
        meta: { title: '教师工作台' },
      },
      {
        path: 'projects',
        name: 'ProjectList',
        component: () => import('@/views/teacher/ProjectListView.vue'),
        meta: { title: '项目列表' },
      },
      {
        path: 'projects/new',
        name: 'ProjectCreateWizard',
        component: () => import('@/views/teacher/project-workspace/ProjectCreateWizard.vue'),
        meta: { title: '创建项目' },
      },
      {
        path: 'projects/:id',
        component: () => import('@/views/teacher/project-workspace/ProjectWorkspaceLayout.vue'),
        redirect: (to) => ({ name: 'ProjectOverview', params: to.params }),
        meta: { title: '项目工作区' },
        children: [
          {
            path: 'overview',
            name: 'ProjectOverview',
            component: () => import('@/views/teacher/project-workspace/ProjectOverviewView.vue'),
            meta: { title: '项目总览' },
          },
          {
            // 阶段1：学情诊断（Task 4 建立空壳，Task 6 实现业务）
            path: 'diagnosis',
            name: 'ProjectDiagnosis',
            component: () => import('@/views/teacher/project-workspace/ProjectDiagnosisView.vue'),
            meta: { title: '学情诊断' },
          },
          {
            // 阶段2：跨学科设计
            path: 'design',
            name: 'ProjectDesign',
            component: () => import('@/views/teacher/project-workspace/ProjectDesignView.vue'),
            meta: { title: '跨学科设计' },
          },
          {
            // 阶段3：备课与资源（Task 4 建立空壳，Task 8 实现业务）
            path: 'preparation',
            name: 'ProjectPreparation',
            component: () => import('@/views/teacher/project-workspace/ProjectPreparationView.vue'),
            meta: { title: '备课与资源' },
          },
          {
            // 阶段5：学习证据（Task 4 建立空壳，Task 10 实现业务）
            path: 'evidence',
            name: 'ProjectEvidence',
            component: () => import('@/views/teacher/project-workspace/ProjectEvidenceView.vue'),
            meta: { title: '学习证据' },
          },
          {
            // 阶段5：评价与反馈（Task 4 建立空壳，Task 11 实现业务）
            path: 'evaluation',
            name: 'ProjectEvaluation',
            component: () => import('@/views/teacher/project-workspace/ProjectEvaluationView.vue'),
            meta: { title: '评价与反馈' },
          },
          {
            // 三级资源页与递进覆盖检查（计划 Task 3.5）
            path: 'resources',
            name: 'ProjectResources',
            component: () => import('@/views/teacher/project-workspace/ProjectResourcesView.vue'),
            meta: { title: '项目资源' },
          },
          {
            // 三阶段任务链与发布预览（计划 Task 3.6）
            path: 'task-chain',
            name: 'ProjectTaskChain',
            component: () => import('@/views/teacher/project-workspace/ProjectTaskChainView.vue'),
            meta: { title: '任务链' },
          },
          {
            // 评价计划页（计划 Task 4.6）
            path: 'evaluation-plan',
            name: 'ProjectEvaluationPlan',
            component: () => import('@/views/teacher/project-workspace/ProjectEvaluationPlanView.vue'),
            meta: { title: '评价计划' },
          },
          {
            // 三栏复核工作台（计划 Task 4.6）
            path: 'review',
            name: 'ProjectReview',
            component: () => import('@/views/teacher/project-workspace/ProjectReviewView.vue'),
            meta: { title: '复核工作台' },
          },
          {
            // AI 内容治理（计划 Task 5 / 验收 3.5.6）
            path: 'ai-content',
            name: 'ProjectAiContent',
            component: () => import('@/views/teacher/project-workspace/ProjectAiContentView.vue'),
            meta: { title: 'AI 内容' },
          },
          {
            // 学情改进与二次评价（计划 Task 7 / 验收 3.7）
            path: 'insights',
            name: 'ProjectInsights',
            component: () => import('@/views/teacher/project-workspace/ProjectInsightsView.vue'),
            meta: { title: '学情' },
          },
          {
            // 结项、反思与案例归档（计划 Task 9 / 验收 3.5.9）
            path: 'closure',
            name: 'ProjectClosure',
            component: () => import('@/views/teacher/project-workspace/ProjectClosureView.vue'),
            meta: { title: '结项' },
          },
          {
            // 旧版完整详情已下线：安全重定向到项目总览，不再渲染第二套任务/资源/评价写入口
            path: 'detail',
            redirect: (to) => ({ name: 'ProjectOverview', params: to.params }),
          },
        ],
      },
      {
        path: 'lesson-plans',
        name: 'LessonPlan',
        component: () => import('@/views/teacher/LessonPlanView.vue'),
        meta: { title: '智能备课' },
      },
      {
        path: 'tasks',
        name: 'TaskList',
        component: () => import('@/views/teacher/TaskListView.vue'),
        meta: { title: '任务管理' },
      },
      {
        path: 'evaluations',
        name: 'EvaluationList',
        component: () => import('@/views/teacher/EvaluationListView.vue'),
        meta: { title: '多元评价' },
      },
      {
        path: 'grading',
        name: 'TeacherGrading',
        component: () => import('@/views/teacher/AiGradingView.vue'),
        meta: { title: 'AI 批改' },
      },
      {
        path: 'papers',
        name: 'PaperList',
        component: () => import('@/views/teacher/PaperListView.vue'),
        meta: { title: '试卷管理' },
      },
      {
        path: 'papers/:id/grading',
        name: 'PaperGrading',
        component: () => import('@/views/teacher/PaperGradingView.vue'),
        meta: { title: '试卷批改' },
      },
      {
        path: 'question-bank',
        name: 'QuestionBank',
        component: () => import('@/views/teacher/QuestionBankView.vue'),
        meta: { title: '题库管理' },
      },
      {
        path: 'question-bank/dashboard',
        name: 'QuestionBankDashboard',
        component: () => import('@/views/teacher/QuestionBankDashboard.vue'),
        meta: { title: '题库质量看板' },
      },
      {
        path: 'classes/:id/learning-profile',
        name: 'ClassLearningProfile',
        component: () => import('@/views/teacher/ClassLearningProfile.vue'),
        meta: { title: '班级学情' },
      },
      {
        path: 'papers/smart-compose',
        name: 'SmartCompose',
        component: () => import('@/views/teacher/SmartCompose.vue'),
        meta: { title: '智能组卷' },
      },
      {
        path: 'paper-generator',
        name: 'PaperGenerator',
        component: () => import('@/views/teacher/PaperGeneratorView.vue'),
        meta: { title: 'AI 出卷' },
      },
      {
        path: 'resources',
        name: 'ResourceList',
        component: () => import('@/views/teacher/ResourceListView.vue'),
        meta: { title: '资源中心' },
      },
    ],
  },

  // ============================================================
  // 学生端路由
  // ============================================================
  {
    path: '/student',
    component: StudentLayout,
    meta: { requiresAuth: true, roles: ['student', 'parent'] },
    children: [
      {
        path: 'profile',
        name: 'StudentProfile',
        component: () => import('@/views/ProfileView.vue'),
        meta: { title: '个人中心' },
      },
      {
        path: 'dashboard',
        name: 'StudentDashboard',
        component: () => import('@/views/student/DashboardView.vue'),
        meta: { title: '学生工作台' },
      },
      {
        path: 'tasks',
        name: 'StudentTaskList',
        component: () => import('@/views/student/TaskListView.vue'),
        meta: { title: '我的任务' },
      },
      {
        path: 'tasks/:id/submit',
        name: 'TaskSubmit',
        component: () => import('@/views/student/TaskSubmitView.vue'),
        meta: { title: '提交任务' },
      },
      {
        path: 'evaluations',
        name: 'StudentEvaluation',
        component: () => import('@/views/student/EvaluationView.vue'),
        meta: { title: '我的评价' },
      },
      {
        // 学生视角项目空间（计划 Task 6 / 验收 3.7.2）
        path: 'projects/:id',
        name: 'StudentProject',
        component: () => import('@/views/student/StudentProjectView.vue'),
        meta: { title: '项目空间' },
      },
      {
        // 提交反馈与订正入口（计划 Task 6）
        path: 'submissions/:id/feedback',
        name: 'SubmissionFeedback',
        component: () => import('@/views/student/SubmissionFeedbackView.vue'),
        meta: { title: '反馈与订正' },
      },
      {
        // 成长档案（计划 Task 6 / 验收 3.7.5）
        path: 'growth',
        name: 'StudentGrowth',
        component: () => import('@/views/student/GrowthPortfolioView.vue'),
        meta: { title: '成长档案' },
      },
    ],
  },

  // ============================================================
  // 管理端路由
  // ============================================================
  {
    path: '/admin',
    component: AdminLayout,
    meta: { requiresAuth: true, roles: ['admin', 'school_admin'] },
    children: [
      {
        path: 'profile',
        name: 'AdminProfile',
        component: () => import('@/views/ProfileView.vue'),
        meta: { title: '个人中心' },
      },
      {
        path: 'dashboard',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/DashboardView.vue'),
        meta: { title: '管理后台' },
      },
      {
        path: 'users',
        name: 'UserManagement',
        component: () => import('@/views/admin/UserManagementView.vue'),
        meta: { title: '用户管理' },
      },
      {
        path: 'classes',
        name: 'ClassManagement',
        component: () => import('@/views/admin/ClassManagementView.vue'),
        meta: { title: '班级管理' },
      },
      {
        path: 'settings',
        name: 'SystemSettings',
        component: () => import('@/views/admin/SystemSettingsView.vue'),
        meta: { title: '系统设置' },
      },
      {
        path: 'ai-config',
        name: 'AIConfig',
        component: () => import('@/views/admin/AIConfigView.vue'),
        meta: { title: 'AI 配置' },
      },
      {
        path: 'templates',
        name: 'TemplateManagement',
        component: () => import('@/views/admin/TemplateManagementView.vue'),
        meta: { title: '模板管理' },
      },
      {
        path: 'prompt-templates',
        name: 'PromptTemplateManagement',
        component: () => import('@/views/admin/PromptTemplateView.vue'),
        meta: { title: '提示词模板' },
      },
      {
        path: 'logs',
        name: 'AuditLogs',
        component: () => import('@/views/admin/AuditLogView.vue'),
        meta: { title: '审计日志' },
      },
      {
        // AI 治理看板（计划 Task 8 / 验收 3.5.6）
        path: 'ai-governance',
        name: 'AiGovernance',
        component: () => import('@/views/admin/AiGovernanceView.vue'),
        meta: { title: 'AI 治理' },
      },
      {
        // 运营证据中心（计划 Task 8 / 验收 3.8）
        path: 'evidence-center',
        name: 'EvidenceCenter',
        component: () => import('@/views/admin/EvidenceCenterView.vue'),
        meta: { title: '证据中心' },
      },
    ],
  },

  // ============================================================
  // 默认重定向
  // ============================================================
  {
    path: '/',
    redirect: '/teacher/dashboard',
  },

  // 404 页面
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '404 页面不存在' },
  },
]

// ============================================================
// 路由实例
// ============================================================

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

// ============================================================
// 路由守卫 - 认证检查
// ============================================================

router.beforeEach((to, _from, next) => {
  // 设置页面标题
  document.title = `${to.meta.title || '初中跨学科教学评一体化平台'} - 教学评一体化平台`

  const userStore = useUserStore()

  // 不需要认证的路由（如登录页）
  if (to.meta.requiresAuth === false) {
    // 如果已登录且访问登录页，重定向到首页
    if (userStore.isLoggedIn && to.path === '/login') {
      next(userStore.homeRoute)
      return
    }
    next()
    return
  }

  // 需要认证但未登录，重定向到登录页
  if (!userStore.isLoggedIn) {
    next(`/login?redirect=${to.path}`)
    return
  }

  // 检查角色权限
  const allowedRoles = to.meta.roles as string[] | undefined
  if (allowedRoles && !allowedRoles.includes(userStore.userRole)) {
    // 没有权限，重定向到该角色的首页
    next(userStore.homeRoute)
    return
  }

  next()
})

export default router
