import http from './index'
import type { ApiResponse, LessonPlanRequest, LessonPlanResponse, AiProvider } from '@/types'

/** 调用后端 AI 备课 API */
export function generateLessonPlanApi(data: LessonPlanRequest) {
  return http.post<ApiResponse<LessonPlanResponse>>('/ai/lesson-plan', data)
}

/** 获取 AI Provider 列表 */
export function listProvidersApi() {
  return http.get<ApiResponse<AiProvider[]>>('/ai/providers')
}

/** 创建 AI Provider */
export function createProviderApi(data: { name: string; api_url: string; model: string; api_key: string }) {
  return http.post<ApiResponse<AiProvider>>('/ai/providers', data)
}

/** 更新 AI Provider */
export function updateProviderApi(id: string, data: Record<string, unknown>) {
  return http.put<ApiResponse<AiProvider>>(`/ai/providers/${id}`, data)
}

/** 删除 AI Provider */
export function deleteProviderApi(id: string) {
  return http.delete<ApiResponse<null>>(`/ai/providers/${id}`)
}

/** 测试 AI Provider 连接 */
export function testProviderApi(id: string) {
  return http.post<ApiResponse<null>>(`/ai/providers/${id}/test`)
}

/** 教案持久化接口 ============ */

export interface SavedLessonPlan {
  id: string
  userId: string
  title: string
  content: string
  subject: string
  grade: string
  topic: string
  duration: number
  createdAt: string
  updatedAt: string
}

export function listLessonPlansApi() {
  return http.get<ApiResponse<SavedLessonPlan[]>>('/ai/lesson-plans')
}

export function createLessonPlanApi(data: {
  title: string; content: string; subject: string; grade: string; topic: string; duration: number
}) {
  return http.post<ApiResponse<SavedLessonPlan>>('/ai/lesson-plans', data)
}

export function updateLessonPlanApi(id: string, data: { title?: string; content?: string }) {
  return http.put<ApiResponse<SavedLessonPlan>>(`/ai/lesson-plans/${id}`, data)
}

export function deleteLessonPlanApi(id: string) {
  return http.delete<ApiResponse<null>>(`/ai/lesson-plans/${id}`)
}

/** Mock 方案：在后端 AI 接口未实现时使用 */
export function mockGenerateLessonPlan(data: LessonPlanRequest): LessonPlanResponse {
  const now = new Date().toLocaleString('zh-CN')

  function pick(items: string[]) {
    return items[Math.floor(Math.random() * items.length)]
  }

  const knowledgeGoals = [
    '理解并掌握${topic}的核心概念与基本原理',
    '能够运用${topic}的相关知识解决实际问题',
    '梳理${topic}的知识脉络，形成系统的认知结构',
    '掌握${topic}的关键术语和表述方式',
  ]

  const processGoals = [
    '通过小组合作探究，培养团队协作与沟通能力',
    '运用信息技术手段，提升信息获取与处理能力',
    '通过案例分析，培养批判性思维与问题解决能力',
    '通过实验/实践活动，培养动手操作与观察分析能力',
  ]

  const emotionGoals = [
    '激发学生对${topic}的学习兴趣，树立科学态度',
    '培养跨学科整合意识，增强综合素养',
    '引导学生关注${topic}在社会生活中的应用价值',
    '增强文化自信，培养家国情怀与社会责任感',
  ]

  const importMethods = [
    '通过播放相关视频/图片素材，创设情境导入新课',
    '以生活实例提问的方式引发学生思考，自然过渡到新课内容',
    '回顾已学相关知识，以问题链的形式引出新课题',
    '通过一个小实验/小活动，激发学生的好奇心和探究欲',
  ]

  const expansions = [
    `引导学生思考${data.subject}与其他学科之间的联系，尝试用跨学科视角分析问题。`,
    `结合生活实际，拓展${data.topic}在日常生活中的应用场景。`,
    `引入前沿科技动态，拓展学生的视野和知识面。`,
    `布置课后研究性学习任务，鼓励学生深入探索相关主题。`,
  ]

  const topic = data.topic || '本课主题'
  const sub = data.subject || '本学科'
  const grade = data.grade || '本年级'
  const minutes = data.duration || 45
  const p1 = Math.round(minutes * 0.1)
  const p2 = Math.round(minutes * 0.4)
  const p3 = Math.round(minutes * 0.25)
  const p4 = Math.round(minutes * 0.1)
  const p5 = minutes - p1 - p2 - p3 - p4

  const content = `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  .lp-wrapper { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", "Noto Sans SC", sans-serif; color: #303133; line-height: 1.8; padding: 8px; }
  .lp-wrapper h1 { font-size: 22px; color: #303133; border-bottom: 2px solid #409EFF; padding-bottom: 8px; margin-bottom: 16px; }
  .lp-wrapper h2 { font-size: 18px; color: #409EFF; margin: 20px 0 10px; padding-left: 10px; border-left: 3px solid #409EFF; }
  .lp-wrapper h3 { font-size: 15px; color: #606266; margin: 12px 0 6px; }
  .lp-wrapper ul, .lp-wrapper ol { padding-left: 22px; margin: 6px 0; }
  .lp-wrapper li { margin: 4px 0; }
  .lp-wrapper .meta { background: #f0f9ff; border-radius: 6px; padding: 12px 16px; margin-bottom: 16px; font-size: 13px; color: #606266; display: flex; flex-wrap: wrap; gap: 16px; }
  .lp-wrapper .meta span { white-space: nowrap; }
  .lp-wrapper .meta strong { color: #303133; }
  .lp-wrapper .tag { display: inline-block; background: #ecf5ff; color: #409EFF; font-size: 12px; padding: 2px 10px; border-radius: 4px; margin-right: 4px; }
  .lp-wrapper .table-wrap { overflow-x: auto; margin: 10px 0; }
  .lp-wrapper table { width: 100%; border-collapse: collapse; font-size: 13px; }
  .lp-wrapper th { background: #ecf5ff; color: #409EFF; padding: 8px 12px; border: 1px solid #e4e7ed; text-align: center; font-weight: 600; }
  .lp-wrapper td { padding: 8px 12px; border: 1px solid #e4e7ed; }
  .lp-wrapper .highlight { background: #fdf6ec; border-left: 3px solid #e6a23c; padding: 8px 12px; border-radius: 4px; margin: 8px 0; font-size: 13px; }
</style>
</head>
<body>
<div class="lp-wrapper">
  <h1>《${topic}》教案</h1>

  <div class="meta">
    <span><strong>学科：</strong>${sub}</span>
    <span><strong>年级：</strong>${grade}</span>
    <span><strong>课时：</strong>${minutes} 分钟</span>
    <span><strong>生成时间：</strong>${now}</span>
  </div>

  <h2>一、教学目标</h2>
  <h3>1. 知识与技能目标</h3>
  <ul>
    <li>${pick(knowledgeGoals).replace(/\${topic}/g, topic)}</li>
    <li>能准确识别${topic}中的关键要素，并加以分类和归纳</li>
  </ul>
  <h3>2. 过程与方法目标</h3>
  <ul>
    <li>${pick(processGoals)}</li>
    <li>通过自主学习与协作探究相结合的方式，培养综合学习能力</li>
  </ul>
  <h3>3. 情感态度与价值观目标</h3>
  <ul>
    <li>${pick(emotionGoals)}</li>
    <li>${pick(emotionGoals)}</li>
  </ul>

  <h2>二、教学重难点</h2>
  <ul>
    <li><strong>教学重点：</strong>${topic}的核心概念及其内在逻辑关系</li>
    <li><strong>教学难点：</strong>如何将${topic}与实际生活情境有效联系，实现知识的迁移与应用</li>
  </ul>

  <h2>三、教学方法与手段</h2>
  <ul>
    <li>启发式教学法：通过问题引导，激发学生主动思考</li>
    <li>小组合作学习法：分组讨论，互助探究</li>
    <li>信息技术辅助：多媒体课件 / 在线互动工具</li>
    <li>跨学科融合：融入相关学科视角，拓展思维广度</li>
  </ul>

  <h2>四、教学过程</h2>

  <div class="table-wrap">
  <table>
    <thead>
      <tr><th style="width:15%">教学环节</th><th style="width:20%">时间</th><th style="width:40%">教师活动</th><th style="width:25%">学生活动</th></tr>
    </thead>
    <tbody>
      <tr>
        <td><span class="tag">导入</span></td>
        <td>${p1} 分钟</td>
        <td>${pick(importMethods)}，展示学习目标和评价标准</td>
        <td>观看/聆听，进入学习状态，明确学习目标</td>
      </tr>
      <tr>
        <td><span class="tag">新课讲授</span></td>
        <td>${p2} 分钟</td>
        <td>系统讲授${topic}的核心知识，穿插提问与互动，利用多媒体辅助呈现</td>
        <td>听讲并记录要点，回答问题，完成随堂练习</td>
      </tr>
      <tr>
        <td><span class="tag">合作探究</span></td>
        <td>${p3} 分钟</td>
        <td>布置小组探究任务，巡回指导，组织展示交流</td>
        <td>小组分工合作，讨论探究，形成成果并展示</td>
      </tr>
      <tr>
        <td><span class="tag">课堂小结</span></td>
        <td>${p4} 分钟</td>
        <td>归纳总结本课核心知识点，梳理知识框架，布置课后任务</td>
        <td>参与小结，完善笔记，明确课后任务要求</td>
      </tr>
      <tr>
        <td><span class="tag">作业布置</span></td>
        <td>${p5} 分钟</td>
        <td>分层布置作业：基础题+拓展题，鼓励学有余力的同学完成跨学科探究</td>
        <td>记录作业内容，明确完成标准</td>
      </tr>
    </tbody>
  </table>
  </div>

  <h2>五、板书设计</h2>
  <div class="highlight">
    <strong>📌 课题：</strong>${topic}<br>
    <strong>一、</strong>核心概念 ──→ <strong>二、</strong>关键方法 ──→ <strong>三、</strong>实际应用<br>
    <strong>四、</strong>跨学科联系 ──→ <strong>五、</strong>课堂总结
  </div>

  <h2>六、教学反思与拓展</h2>
  <ul>
    <li>${pick(expansions)}</li>
    <li>根据课堂实际情况灵活调整教学节奏与活动设计</li>
    <li>关注学生个体差异，实施分层教学与个性化指导</li>
  </ul>

  <p style="text-align:center;color:#c0c4cc;font-size:12px;margin-top:24px;">
    —— AI 智能备课助手 · 教学评一体化平台 ——
  </p>
</div>
</body>
</html>`

  const title = `《${topic}》教案`

  return { content, title }
}

// ---- AI 批改评价相关接口 ----

export interface EvaluateResult {
  dimensions: { name: string; score: number; comment: string }[]
  totalScore: number
  overallComment: string
  evaluationId: string | null
}

/** 单份提交 AI 批改 */
export function evaluateSubmissionApi(submissionId: string) {
  return http.post<ApiResponse<EvaluateResult>>(`/ai/evaluate/${submissionId}`)
}

/** 批量 AI 批改 */
export function evaluateBatchApi(taskId: string) {
  return http.post<ApiResponse<{ total: number; completed: number; results: any[] }>>(`/ai/evaluate/batch?task_id=${taskId}`)
}
