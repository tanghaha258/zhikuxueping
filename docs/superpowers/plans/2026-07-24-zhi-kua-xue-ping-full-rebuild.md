# 智跨学评全项目重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将现有功能平铺的平台重构为“跨学科项目主线 + 独立教学能力中心”，完整打通学情诊断、项目设计、任务实施、学习证据、多元评价、反馈订正、教学改进和项目归档。

**Architecture:** `Project` 是正式教学业务的聚合根，任务、资源、提交、评价、学情、改进和AI产出都通过项目上下文关联；独立工具使用相同领域服务，通过可选上下文链接加入项目，不复制业务数据。实施采用 expand-and-contract：先增加新表/字段和兼容读，再迁移与校验数据，随后切换写入和页面，最后下线旧入口与旧写入。

**Tech Stack:** Vue 3、TypeScript、Element Plus、Pinia、Vue Router、SCSS；FastAPI、SQLAlchemy 2、Pydantic、Alembic；Pytest、Vitest、Playwright。

---

## 0. 权威输入与执行约束

本计划以以下文件为权威输入：

- `docs/superpowers/specs/2026-07-24-zhi-kua-xue-ping-redesign.md`
- `00_项目总览.md`
- `01_PRD_产品需求说明.md`
- `02_业务流程与信息架构.md`

本计划替代全部历史实施计划作为后续重构的唯一执行计划。历史计划、旧原型和旧交付说明已移出工作区，不得从备份恢复后参与开发决策。

执行时遵守以下约束：

1. 先测试、后实现；每个任务单独提交，不将多个阶段混在一次提交中。
2. 不删除历史数据；所有破坏性表结构清理推迟到新流程稳定运行至少一个发布周期后。
3. 不保留生产随机数据、前端硬编码学情、模拟AI分数、假保存或假成功提示。
4. 新功能只能写统一数据模型；旧表只读兼容，不允许新增双写。
5. 每个阶段通过对应验收门禁后才能进入下一阶段。
6. 业务页面必须使用本计划定义的通用UI组件和交互状态，不允许各页面自行创造样式与反馈模式。

### 0.1 多会话与子代理执行规则

本计划允许多会话执行，但必须采用“一个集成会话 + 最多三个工作会话”的受控方式：

1. **先完成Task 0。** 当前工作区在基线提交完成前不得创建并行worktree；未提交文件不会自动出现在其他会话中。
2. **每个工作会话使用独立worktree和独立分支。** 分支建议为 `task/01-shared-ui`、`task/06-project-diagnosis`；禁止多个会话直接写同一工作区或同一分支。
3. **每个会话一次只领取一个Task。** 必须从最新集成分支创建，严格限制在该Task的Files范围；需要越界时先由集成会话确认。
4. **会话内可以调用子代理。** 子代理应分别承担不重叠的后端、前端、测试或审查工作；同一文件只能由一个写入者负责。
5. **集成会话独占合并权。** 它负责审查提交、处理冲突、更新Alembic head、运行波次回归和决定下一波是否放行；工作会话不得自行合并到集成分支。
6. **每个Task交付固定回执。** 必须报告Task编号、提交SHA、修改文件、迁移影响、测试命令与结果、遗留风险；未提交或验证失败不进入集成。
7. **每波集成后重新同步。** 下一波所有worktree都从新的集成提交创建或变基，禁止长期分支跨越多个波次继续开发。

推荐并行波次如下；同一行可以并行，不同行必须等待上一行集成并通过指定验收：

| 波次 | 可执行Task | 并行上限 | 放行条件 |
| --- | --- | --- | --- |
| W0 | Task 0 | 1 | 远程历史、基线提交和重构集成分支可用 |
| W1 | Task 1、Task 2 | 2 | UI基础与增量表结构分别测试通过 |
| W2 | Task 3 | 1 | Task 2已集成，项目上下文合同通过 |
| W3 | Task 4 | 1 | Task 1和Task 3已集成，路由及工作区外壳稳定 |
| W4 | Task 5、Task 6、Task 7 | 3 | Phase 1页面与接口联合回归通过 |
| W5 | Task 8、Task 9 | 2 | 工具上下文与任务实施互不产生重复事实 |
| W6 | Task 10、Task 13 | 2 | Task 9与Task 8分别已集成；学生证据链和测评工具回归通过 |
| W7 | Task 11 | 1 | 学生提交与任务模型稳定，统一评价写入通过 |
| W8 | Task 12、Task 14 | 2 | Task 11与Task 13已集成；改进闭环和AI治理联合回归通过 |
| W9 | Task 15 | 1 | 结项阻断、学校作用域和管理动作通过 |
| W10 | Task 16 | 1 | 全量备份完成，迁移校验与读写切换演练通过 |
| W11 | Task 17 | 1 | 所有功能合并后执行全链路E2E和发布验收 |

不得并行的高冲突工作包括：Alembic迁移链、共享UI入口、主路由、统一评价写入、数据切换和最终E2E。它们必须由表中对应单任务波次完成。

## 1. 交付阶段总览

| 阶段 | 对应任务 | 可独立交付的结果 |
| --- | --- | --- |
| Phase 0：工程与设计基础 | Task 0-3 | Git基线、通用UI、增量数据模型、统一项目上下文API |
| Phase 1：项目主线骨架 | Task 4-7 | 新导航、项目工作区、教师工作台、学情诊断与跨学科设计 |
| Phase 2：教学实施闭环 | Task 8-10 | 备课资源、任务分配、学生草稿/提交/学习证据 |
| Phase 3：评价与智能改进 | Task 11-14 | 统一评价、反馈订正、学情改进、独立工具、AI治理 |
| Phase 4：结项、迁移与发布 | Task 15-17 | 结项管理、旧功能切换、全链路自动化与正式验收 |

## 2. 通用UI设计规范

### 2.1 视觉原则

- 定位为安静、专业、可重复操作的教师工作台，不使用营销式大标题、装饰渐变、悬浮大卡片或卡片嵌套。
- 主背景使用中性浅灰，内容区白色；蓝色仅用于主操作，绿色用于完成，琥珀用于待处理，红色用于阻断或危险操作。
- 页面圆角统一为 `4px` 或 `6px`，工具卡和模态框最大 `8px`；不使用药丸形文字按钮。
- 图标优先使用 Element Plus Icons，图标按钮必须提供 `aria-label` 和 tooltip。
- 字号固定为 `12/14/16/20/24px`，不得随视口宽度缩放；字间距为 `0`。

### 2.2 设计令牌

Create: `project/frontend/src/styles/tokens.scss`

```scss
:root {
  --ui-bg-app: #f4f6f8;
  --ui-bg-surface: #ffffff;
  --ui-bg-subtle: #f8f9fb;
  --ui-text-primary: #1f2933;
  --ui-text-secondary: #52606d;
  --ui-text-muted: #7b8794;
  --ui-border: #d9dee5;
  --ui-border-light: #e8ebef;
  --ui-primary: #2463a7;
  --ui-success: #2f7d4a;
  --ui-warning: #a86412;
  --ui-danger: #b43a3a;
  --ui-radius-sm: 4px;
  --ui-radius-md: 6px;
  --ui-space-1: 4px;
  --ui-space-2: 8px;
  --ui-space-3: 12px;
  --ui-space-4: 16px;
  --ui-space-6: 24px;
  --ui-space-8: 32px;
  --ui-header-height: 56px;
  --ui-sidebar-width: 224px;
  --ui-content-max: 1440px;
}
```

### 2.3 页面骨架

所有教师与管理页面必须按以下层次组织：

```text
ApplicationShell
├── GlobalHeader（产品名、通知、用户）
├── PrimarySidebar（主线与能力中心）
└── PageCanvas
    ├── PageHeader（面包屑、标题、状态、主操作）
    ├── ContextBar（项目/班级/学科/时间范围，仅需要时出现）
    ├── InlineAlert（阻断、警告、失败）
    ├── PageBody（全宽分区，不在卡片内再放卡片）
    └── StickyActionBar（长表单保存、发布、取消）
```

### 2.4 通用组件清单

Create under `project/frontend/src/shared/ui/`：

| 组件 | 职责 | 统一规则 |
| --- | --- | --- |
| `PageHeader.vue` | 标题、面包屑、状态、主次操作 | 页面最多一个主按钮 |
| `ContextBar.vue` | 项目/班级/学科上下文 | 选择变化前提示未保存内容 |
| `AsyncState.vue` | loading/error/empty/content | 失败必须有重试；空态给下一步 |
| `InlineAlert.vue` | blocker/warning/info | blocker使用红色并给修复入口 |
| `StatusBadge.vue` | 业务状态映射 | 文案和颜色由中央映射提供 |
| `ProjectPhaseStepper.vue` | 七阶段进度与导航 | 支持当前、完成、警告、阻断 |
| `MetricStrip.vue` | 紧凑指标行 | 不使用装饰性统计卡片墙 |
| `EvidenceLink.vue` | 展示评价所依赖证据 | 可打开提交、量规或AI调用记录 |
| `ContextPicker.vue` | 独立/关联项目模式 | 关联项目时必选项目位置 |
| `StickyActionBar.vue` | 长页面保存和发布 | 禁用态必须说明原因 |
| `ConfirmActionDialog.vue` | 发布、归档、删除确认 | 展示影响范围，不只问“确定吗” |

### 2.5 响应式与可访问性

- `>= 1200px`：224px侧栏 + 最大1440px内容区；项目阶段导航可横向完整显示。
- `768-1199px`：侧栏默认折叠为64px；表格隐藏低优先级列，筛选进入抽屉。
- `< 768px`：单列布局；项目阶段改为下拉选择；固定操作栏不遮挡内容。
- 所有可点击控件最小高度40px；纯图标按钮最小40x40px。
- 表单错误同时提供颜色、图标和文字；焦点顺序与页面视觉顺序一致。
- 表格在窄屏可水平滚动，操作列固定，不允许文字覆盖或按钮换行挤压数据列。

### 2.6 通用交互状态

每个页面必须实现并测试：

1. 首次加载骨架或加载提示。
2. 有数据的正常状态。
3. 无数据且可执行下一步的空状态。
4. 请求失败并可重试。
5. 无权限状态，不以空数据伪装。
6. 保存中、保存成功、保存失败。
7. 离开未保存页面的确认。
8. 发布/删除/归档的影响确认。

## 3. 页面展开清单

### 3.1 教师端

| 路由 | 页面 | 主要区域 | 主操作 | 关键状态 |
| --- | --- | --- | --- | --- |
| `/teacher/dashboard` | 教师工作台 | 当前项目、待发布、待评价、临期任务、AI待确认、学情提醒 | 继续下一项工作 | 无待办、接口失败、跨项目筛选 |
| `/teacher/projects` | 智跨学评项目列表 | 状态筛选、班级筛选、项目阶段、阻断数量 | 创建跨学科项目 | 无项目、归档项目、权限受限 |
| `/teacher/projects/new` | 项目创建向导 | 基础信息、班级学科、真实问题、样板/空白创建 | 创建草稿 | 分步校验、保存草稿、重复名称 |
| `/teacher/projects/:id/overview` | 项目总览 | 阶段进度、唯一下一步、参与情况、阻断、时间线 | 执行下一步 | 设计未完成、评价未发布、归档只读 |
| `/teacher/projects/:id/diagnosis` | 学情诊断 | 数据来源、班级画像、分层、薄弱点、AI建议 | 确认诊断 | 无学习证据、AI失败、人工诊断 |
| `/teacher/projects/:id/design` | 跨学科设计 | 真实问题、学科贡献、目标、指标、证据计划 | 保存并进入备课 | 核心学科缺失、证据断链、只读 |
| `/teacher/projects/:id/preparation` | 备课与资源 | 教学设计、活动方案、分层资源、AI产出版本 | 采纳并保存 | AI生成中、失败、待审核、已采纳 |
| `/teacher/projects/:id/tasks` | 任务实施 | 课前/课中/课后任务链、依赖、分层、接收学生 | 预览并发布 | 无学生、依赖未满足、定时发布 |
| `/teacher/projects/:id/evidence` | 学习证据 | 学生/小组提交、版本、缺失证据、附件预览 | 进入评价 | 未提交、逾期、证据缺失 |
| `/teacher/projects/:id/evaluation` | 评价与反馈 | 量规、AI建议、教师评分、自评互评、发布状态 | 发布反馈 | AI草稿、待确认、已发布、差异原因 |
| `/teacher/projects/:id/improvement` | 改进与再评价 | 达成度、共性问题、学生分层、改进任务、前后对比 | 发布改进任务 | 无证据、无改进建议、待再评价 |
| `/teacher/projects/:id/closure` | 结项与归档 | 完整度、反思、典型案例、脱敏预览、资产沉淀 | 归档项目 | 未发布评价、开放阻断、归档只读 |

### 3.2 独立能力中心

| 路由 | 页面 | 上下文模式 | 保存去向 |
| --- | --- | --- | --- |
| `/teacher/tools/lesson-plans` | 智能备课 | 独立或关联项目 | 个人教案/项目备课 |
| `/teacher/assessment/questions` | 题库管理 | 学校、学科、年级 | 题库资产 |
| `/teacher/assessment/compose` | 智能组卷 | 独立或项目的前/中/后测 | 试卷/项目测评 |
| `/teacher/assessment/papers` | 试卷管理 | 班级或项目 | 发布测评、导出 |
| `/teacher/assessment/grading` | 智能批改 | 独立试卷或项目提交 | 批改草稿/项目评价草稿 |
| `/teacher/tasks` | 任务中心 | 跨项目聚合 | 返回项目任务实施页处理 |
| `/teacher/evaluations` | 评价中心 | 跨项目聚合 | 返回项目评价页确认发布 |
| `/teacher/resources` | 资源中心 | 独立或关联项目 | 资源资产/项目引用 |
| `/teacher/learning` | 学情中心 | 班级、项目、学生 | 诊断快照/项目改进 |

### 3.3 学生端

| 路由 | 页面 | 核心内容 |
| --- | --- | --- |
| `/student/dashboard` | 学生工作台 | 当前项目、待完成任务、最近反馈、订正提醒 |
| `/student/projects` | 我的项目 | 进行中、已完成项目及个人进度 |
| `/student/projects/:id` | 项目空间 | 真实问题、共同成果、阶段、我的任务与资源 |
| `/student/tasks/:id/submit` | 任务提交 | 目标、量规、资源、草稿、附件、次数、截止时间 |
| `/student/submissions/:id/feedback` | 反馈与订正 | 已发布反馈、证据链接、订正要求、再次提交 |
| `/student/growth` | 成长记录 | 项目维度成长、首次/再次评价、个人成果 |

### 3.4 管理端

| 路由 | 页面 | 重构重点 |
| --- | --- | --- |
| `/admin/dashboard` | 数据驾驶舱 | 真实数据、学校范围、口径与更新时间 |
| `/admin/users` | 用户管理 | 停用优先、删除引用校验、审计 |
| `/admin/settings` | 系统设置 | 真实保存与Logo上传 |
| `/admin/ai-config` | AI Provider | 密钥掩码、连接测试、启停 |
| `/admin/ai-governance` | AI治理 | 调用来源、失败、质量问题、教师采纳 |
| `/admin/evidence-center` | 证据中心 | 脱敏案例、真实运营证据、导出 |

## 4. 数据迁移顺序

### M0：建立可恢复基线

1. 同步远程 `origin/main`，创建 `feat/zhi-kua-xue-ping-rebuild`。
2. 提交当前代码、规格和计划作为重构前基线。
3. 对数据库和 `uploads` 做带时间戳备份，并记录行数。
4. 在副本数据库演练所有迁移，不直接在唯一开发库上首次执行。

### M1：扩展新结构，不改旧读写

新增：

- `project_stage_progress`：项目七阶段状态、完成时间、重开信息。
- `tool_context_links`：独立工具产出与项目、阶段、任务、目标的关联。
- `project_learning_insights`：项目学情诊断快照、证据截止时间、教师确认状态。
- `migration_ledger`：迁移批次、源表、目标表、数量、校验摘要和执行时间。
- `ai_jobs.context_mode`、`ai_jobs.project_phase`；将 `ai_jobs.project_id` 调整为可空，服务层校验项目模式必须有项目ID。

### M2：回填项目与阶段上下文

- 历史跨学科项目：`project_type` 为空时标记 `legacy_unspecified`，不自动伪造为跨学科。
- 有项目关联的任务/资源：根据现有 `stage` 回填阶段；缺失时标记 `unclassified`，由教师进入项目时确认。
- 为每个现有项目创建七条阶段记录；仅根据已有真实数据标记完成，不按零值推测完成。

### M3：迁移评价与学习证据

- 将旧 `Evaluation` 映射到 `EvaluationRecord`，标记 `source=LEGACY`、`status=PUBLISHED`、`is_legacy=true`，保存旧ID映射。
- 已存在的 `EvaluationRecord` 不重复插入；以源表、源ID唯一约束保证幂等。
- 为提交和修订生成/补齐 `EvidenceArtifact` 引用；不得覆盖原提交内容。
- `Submission.score/comment` 保留为只读投影，正式评价以 `EvaluationRecord` 为准。

### M4：迁移独立工具上下文

- 已有关联项目的教案、试卷、资源和AI任务创建 `ToolContextLink`。
- 无法确认项目的资产保持独立，不自动挂载到最近项目。
- 资源以引用方式加入项目，不复制文件或创建第二份资源记录。

### M5：校验并切换写入

1. 校验迁移前后记录数量、孤儿外键、学校范围和评价总分。
2. 启用新服务写入，关闭旧评价和旧任务创建写入。
3. 旧页面进入只读兼容模式，显示“历史记录”。
4. 新页面连续通过全量测试后切换默认路由。

### M6：切换读取与旧功能下线

1. 学生反馈、教师评价、学情和驾驶舱全部读取新模型。
2. 旧路由保留301/前端重定向一个发布周期。
3. 确认无调用后删除旧前端页面和旧写接口。
4. 旧表继续保留只读，不在本次重构中执行 `DROP TABLE`。

### 回滚规则

- M1-M4迁移必须幂等并支持 downgrade；downgrade不删除迁移前已有数据。
- 切换读写由配置开关控制：`NEW_PROJECT_WORKSPACE_ENABLED`、`UNIFIED_EVALUATION_WRITE_ENABLED`。
- 任何数量校验不一致、孤儿记录或跨校数据异常都阻断切换。

## 5. 详细实施任务

### Task 0: Git基线、远程历史与安全检查

**Files:**
- Modify: `.gitignore`
- Create: `.env.example`（若不存在）
- Modify only for a verified baseline blocker: `project/frontend/src/views/teacher/ProjectDetailView.vue`
- Test: repository status and secret scan

- [ ] **Step 1: 恢复GitHub连接并同步远程历史。**

Run:

```text
gh auth login -h github.com
git fetch origin main
git reset --mixed origin/main
git branch --set-upstream-to=origin/main main
```

Expected: `git log main -2 --oneline` 显示远程已有2次提交；本地工作区文件仍完整保留，`main` 与 `origin/main` 已建立共同历史。

- [ ] **Step 2: 创建重构分支并确认忽略项。**

Run:

```text
git switch -c feat/zhi-kua-xue-ping-rebuild
git check-ignore project/backend/.env project/backend/venv project/frontend/node_modules project/backend/data/platform.db
```

Expected: 四个路径均被忽略。

- [ ] **Step 3: 检查待提交内容中没有密钥和运行数据库。**

Run:

```text
git add .
git diff --cached --name-only
git diff --cached -- . ':!*.example' | rg -n -i "(api[_-]?key|secret[_-]?key|password)\s*=\s*[^<\s].+"
```

Expected: 暂存清单不含 `.env`、数据库、日志、上传文件；密钥检查无真实值。若 `rg` 命中，必须逐条确认并从暂存区移除敏感文件后才能继续。

- [ ] **Step 4: 运行重构前完整基线。**

Run:

```text
cd project/backend && .\venv\Scripts\python.exe -m pytest -q
cd project/frontend && npm test && npm run typecheck && npm run build
```

Expected: 后端、前端测试、类型检查和构建全部通过。若只命中旧 `ProjectDetailView.vue` 对已下线 `createEvaluationApi` 的未使用导入，删除该导入，不得恢复旧评价写接口；出现其他失败立即停止并报告，不得让W1工作会话把基线失败当作自身回归。

- [ ] **Step 5: 创建重构前基线提交。**

```text
git add .
git commit -m "chore: establish pre-rebuild baseline"
```

- [ ] **Step 6: 推送集成分支，作为所有worktree的唯一起点。**

Run: `git push -u origin feat/zhi-kua-xue-ping-rebuild`

Expected: 远程可见基线提交；所有W1分支均从该提交创建。

### Task 1: 建立通用UI设计系统

**Files:**
- Create: `project/frontend/src/styles/tokens.scss`
- Create: `project/frontend/src/styles/layout.scss`
- Modify: `project/frontend/src/styles/global.scss`
- Modify: `project/frontend/src/main.ts`
- Create: `project/frontend/src/shared/ui/{PageHeader,ContextBar,AsyncState,InlineAlert,StatusBadge,ProjectPhaseStepper,MetricStrip,EvidenceLink,ContextPicker,StickyActionBar,ConfirmActionDialog}.vue`
- Create: `project/frontend/src/shared/ui/index.ts`
- Create: `project/frontend/src/shared/ui/ui-contract.test.ts`

- [ ] **Step 1: 写通用UI契约失败测试。**

```ts
import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AsyncState from './AsyncState.vue'
import PageHeader from './PageHeader.vue'

describe('shared UI contracts', () => {
  it('renders one primary action in PageHeader', () => {
    const wrapper = mount(PageHeader, {
      props: { title: '学情诊断', primaryLabel: '确认诊断' },
    })
    expect(wrapper.findAll('[data-ui="primary-action"]')).toHaveLength(1)
  })

  it('offers retry when AsyncState is failed', async () => {
    const wrapper = mount(AsyncState, { props: { state: 'error', message: '加载失败' } })
    await wrapper.get('[data-ui="retry"]').trigger('click')
    expect(wrapper.emitted('retry')).toHaveLength(1)
  })
})
```

- [ ] **Step 2: 运行测试确认组件尚未实现。**

Run: `npm test -- src/shared/ui/ui-contract.test.ts` in `project/frontend`

Expected: FAIL because shared UI components do not exist.

- [ ] **Step 3: 实现设计令牌、页面骨架和11个通用组件。** 组件必须使用具名props/emits，禁止页面通过深层CSS覆盖组件内部结构。

```ts
export type AsyncStateName = 'loading' | 'ready' | 'empty' | 'error' | 'forbidden'
export type ProjectPhase =
  | 'diagnosis' | 'design' | 'preparation' | 'implementation'
  | 'evaluation' | 'improvement' | 'closure'
```

- [ ] **Step 4: 运行组件测试、类型检查和构建。**

Run: `npm test -- src/shared/ui/ui-contract.test.ts && npm run typecheck && npm run build`

Expected: PASS；构建无新增CSS或TypeScript错误。

- [ ] **Step 5: Commit.**

```text
git add project/frontend/src/styles project/frontend/src/shared/ui project/frontend/src/main.ts
git commit -m "feat: add shared UI system for teaching workflows"
```

### Task 2: 新领域结构与增量迁移

**Files:**
- Create: `project/backend/app/models/project_stage.py`
- Create: `project/backend/app/models/tool_context.py`
- Create: `project/backend/app/models/project_learning_insight.py`
- Create: `project/backend/app/models/migration_ledger.py`
- Modify: `project/backend/app/models/ai_job.py`
- Modify: `project/backend/app/models/__init__.py`
- Create: `project/backend/alembic/versions/h1a2b3c4d5e6_add_rebuild_context_domain.py`
- Create: `project/backend/tests/test_rebuild_context_migration.py`

- [ ] **Step 1: 写空库升级、历史库升级、重复升级和降级恢复测试。**

```python
def test_rebuild_migration_is_idempotent_and_preserves_legacy_rows(alembic_cfg, seeded_legacy_db):
    before = seeded_legacy_db.counts(["projects", "tasks", "evaluations", "submissions"])
    command.upgrade(alembic_cfg, "h1a2b3c4d5e6")
    command.upgrade(alembic_cfg, "head")
    after = seeded_legacy_db.counts(["projects", "tasks", "evaluations", "submissions"])
    assert after == before
    assert seeded_legacy_db.table_exists("project_stage_progress")
    assert seeded_legacy_db.table_exists("tool_context_links")
```

- [ ] **Step 2: 运行迁移测试确认失败。**

Run: `pytest tests/test_rebuild_context_migration.py -q` in `project/backend`

Expected: FAIL because new tables and revision do not exist.

- [ ] **Step 3: 实现模型与迁移。**

```python
class ProjectStageProgress(Base, TimestampMixin):
    __tablename__ = "project_stage_progress"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    phase: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="not_started")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
```

`project_id + phase` 增加唯一约束；`ToolContextLink` 以 `artifact_type + artifact_id + project_id + placement` 唯一；`ProjectLearningInsight` 保存证据截止时间和教师确认字段；`MigrationLedger` 保存迁移校验摘要。

- [ ] **Step 4: 运行迁移和全量模型测试。**

Run: `pytest tests/test_rebuild_context_migration.py tests/test_project_design_migration.py -q`

Expected: PASS；历史四类记录数量不变。

- [ ] **Step 5: Commit.**

```text
git add project/backend/app/models project/backend/alembic/versions project/backend/tests
git commit -m "feat: add project stages and tool context domain"
```

### Task 3: 统一项目上下文与阶段服务

**Files:**
- Create: `project/backend/app/schemas/project_workspace.py`
- Create: `project/backend/app/modules/project_workspace/{router.py,service.py,repository.py,policy.py}`
- Modify: `project/backend/app/api/v1/__init__.py`
- Create: `project/backend/tests/test_project_workspace_context.py`
- Create: `project/frontend/src/features/project-context/{types.ts,api.ts,store.ts}`
- Create: `project/frontend/src/features/project-context/project-context.test.ts`

- [ ] **Step 1: 写项目工作区上下文与权限失败测试。**

```python
def test_workspace_context_returns_single_next_action(client, teacher_token, project):
    data = client.get(f"/api/v1/project-workspace/{project.id}/context", headers=teacher_token).json()["data"]
    assert data["project"]["id"] == project.id
    assert len([a for a in data["actions"] if a["primary"]]) == 1
    assert [p["phase"] for p in data["phases"]] == [
        "diagnosis", "design", "preparation", "implementation", "evaluation", "improvement", "closure"
    ]
```

- [ ] **Step 2: 实现上下文API。**

Endpoints:

```text
GET  /api/v1/project-workspace/{project_id}/context
GET  /api/v1/project-workspace/{project_id}/timeline
POST /api/v1/project-workspace/{project_id}/phases/{phase}/complete
POST /api/v1/project-workspace/{project_id}/phases/{phase}/reopen
```

阶段服务根据真实数据计算 blockers、warnings、counts 和唯一 next_action；权限复用项目读写策略，学校范围必须参与查询。

- [ ] **Step 3: 实现前端上下文store。** store只缓存当前项目上下文，所有子页通过同一store读取项目、阶段、权限和下一步，不重复请求项目详情。

- [ ] **Step 4: 运行接口、前端store和类型检查。**

Run: `pytest tests/test_project_workspace_context.py -q` and `npm test -- src/features/project-context/project-context.test.ts && npm run typecheck`

Expected: PASS；跨校访问403；每个上下文最多一个主操作。

- [ ] **Step 5: Commit.**

```text
git add project/backend/app/modules/project_workspace project/backend/app/schemas/project_workspace.py project/backend/app/api/v1 project/backend/tests project/frontend/src/features/project-context
git commit -m "feat: add unified project workspace context"
```

### Task 4: 重构导航与项目工作区外壳

**Files:**
- Modify: `project/frontend/src/layouts/TeacherLayout.vue`
- Modify: `project/frontend/src/router/index.ts`
- Rewrite: `project/frontend/src/views/teacher/project-workspace/ProjectWorkspaceLayout.vue`
- Create: `project/frontend/src/views/teacher/project-workspace/ProjectDiagnosisView.vue`
- Create: `project/frontend/src/views/teacher/project-workspace/ProjectPreparationView.vue`
- Create: `project/frontend/src/views/teacher/project-workspace/ProjectEvidenceView.vue`
- Create: `project/frontend/src/views/teacher/project-workspace/ProjectEvaluationView.vue`
- Create: `project/frontend/src/router/router-contract.test.ts`
- Delete after redirect test passes: `project/frontend/src/views/teacher/ProjectDetailView.vue`

- [ ] **Step 1: 写路由层级和旧路由重定向测试。**

```ts
it('keeps project phases under one workspace and redirects legacy detail', async () => {
  expect(router.resolve('/teacher/projects/p1/diagnosis').name).toBe('ProjectDiagnosis')
  expect(router.resolve('/teacher/projects/p1/evaluation').name).toBe('ProjectEvaluation')
  await router.push('/teacher/projects/p1/detail')
  expect(router.currentRoute.value.name).toBe('ProjectOverview')
})
```

- [ ] **Step 2: 实现教师一级导航。** 一级菜单按“工作台、智跨学评、备课与设计、题库与测评、教学实施”分组；能力中心入口保留，项目阶段不出现在一级侧栏。

- [ ] **Step 3: 实现工作区外壳。** 使用 `PageHeader + ProjectPhaseStepper + AsyncState + router-view`；顶部固定项目状态、班级、阶段和唯一主操作；归档状态下所有编辑操作进入只读。

- [ ] **Step 4: 建立四个新阶段页面空壳并移除旧详情实现。** 空壳必须使用真实上下文、正确空态和错误态，不放模拟业务数据；旧 `/detail` 路由通过重定向测试后删除 `ProjectDetailView.vue`，不再保留第二套任务、资源和评价写页面。

- [ ] **Step 5: 运行路由、组件、类型与构建测试。**

Run: `npm test -- src/router/router-contract.test.ts src/features/project-context/project-context.test.ts && npm run typecheck && npm run build`

Expected: PASS；旧链接安全重定向；项目子页共享上下文。

- [ ] **Step 6: Commit.**

```text
git add project/frontend/src/layouts project/frontend/src/router project/frontend/src/views/teacher/project-workspace
git commit -m "feat: rebuild navigation around project workflow"
```

### Task 5: 教师工作台与项目总览

**Files:**
- Modify: `project/backend/app/api/v1/dashboard.py`
- Create: `project/backend/tests/test_teacher_workbench.py`
- Create: `project/backend/tests/test_dashboard_scope.py`
- Rewrite: `project/frontend/src/views/teacher/DashboardView.vue`
- Rewrite: `project/frontend/src/views/teacher/project-workspace/ProjectOverviewView.vue`
- Create: `project/frontend/src/views/teacher/teacher-workbench.test.ts`

- [ ] **Step 1: 写真实待办和学校范围测试。** 工作台返回 `active_projects`、`tasks_to_publish`、`submissions_to_review`、`feedback_to_publish`、`ai_to_review`、`deadlines`、`learning_alerts`；所有数字来自当前教师可管理范围。

```python
def test_teacher_workbench_contains_only_actionable_items(client, teacher_token, own_task, other_teacher_task):
    data = client.get("/api/v1/dashboard/teacher-workbench", headers=teacher_token).json()["data"]
    ids = {item["id"] for item in data["tasks_to_publish"]}
    assert own_task.id in ids
    assert other_teacher_task.id not in ids
```

- [ ] **Step 2: 实现教师工作台API与页面。** 页面使用紧凑待办分区，不显示静态待办；每项操作直接进入所属项目和阶段。

- [ ] **Step 3: 重写项目总览。** 显示阶段进度、下一步、学生参与、未发布评价、AI待确认、阻断清单和真实时间线；删除“后续Task实现”类页面文案。

- [ ] **Step 4: 运行后端与前端测试。**

Run: `pytest tests/test_teacher_workbench.py tests/test_dashboard_scope.py -q` and `npm test -- src/views/teacher/teacher-workbench.test.ts`

Expected: PASS；无静态待办；跨教师和跨校数据不可见。

- [ ] **Step 5: Commit.**

```text
git add project/backend/app/api/v1/dashboard.py project/backend/tests project/frontend/src/views/teacher
git commit -m "feat: add real teacher workbench and project overview"
```

### Task 6: 项目学情诊断

**Files:**
- Create: `project/backend/app/schemas/project_learning_insight.py`
- Create: `project/backend/app/modules/project_learning_insights/{router.py,service.py,repository.py,policy.py}`
- Modify: `project/backend/app/api/v1/__init__.py`
- Create: `project/backend/tests/test_project_learning_insights.py`
- Implement: `project/frontend/src/views/teacher/project-workspace/ProjectDiagnosisView.vue`
- Create: `project/frontend/src/features/project-diagnosis/{types.ts,api.ts}`
- Create: `project/frontend/src/views/teacher/project-workspace/project-diagnosis.test.ts`

- [ ] **Step 1: 写“无证据不生成确定结论”和教师确认测试。**

```python
def test_diagnosis_without_evidence_returns_insufficient_state(client, teacher_token, project):
    data = client.post(f"/api/v1/projects/{project.id}/insights/generate", headers=teacher_token).json()["data"]
    assert data["status"] == "insufficient_evidence"
    assert data["segments"] == []
```

- [ ] **Step 2: 实现诊断聚合和确认接口。** 数据来源只包含项目班级、前测、提交、已发布评价和题目作答；保存 evidence_cutoff 与 source_counts。

Endpoints:

```text
GET  /api/v1/projects/{project_id}/insights/latest
POST /api/v1/projects/{project_id}/insights/generate
POST /api/v1/projects/{project_id}/insights/{insight_id}/confirm
```

- [ ] **Step 3: 实现诊断页面。** 页面先显示数据来源和更新时间，再显示整体掌握、薄弱点、分层建议和教学建议；无证据时只提供“导入前测/先发布任务”入口。

- [ ] **Step 4: 运行合同、权限和页面状态测试。**

Run: `pytest tests/test_project_learning_insights.py tests/test_learning_profile_authorization.py -q` and `npm test -- project-diagnosis.test.ts`

Expected: PASS；无随机画像；AI失败可转人工诊断且不显示成功。

- [ ] **Step 5: Commit.**

```text
git add project/backend/app/modules/project_learning_insights project/backend/app/schemas project/backend/app/api/v1 project/backend/tests project/frontend/src/features/project-diagnosis project/frontend/src/views/teacher/project-workspace
git commit -m "feat: add evidence-based project diagnosis"
```

### Task 7: 跨学科设计与完整性校验

**Files:**
- Modify: `project/backend/app/modules/project_designs/*`
- Modify: `project/backend/app/modules/projects/validators.py`
- Modify: `project/frontend/src/views/teacher/project-workspace/ProjectDesignView.vue`
- Modify: `project/frontend/src/features/project-workspace/{api.ts,types.ts}`
- Create: `project/backend/tests/test_project_designs.py`
- Test: `project/frontend/src/features/project-workspace/project-workspace.test.ts`

- [ ] **Step 1: 写跨学科真实性失败测试。** 至少一个核心学科、一个支持学科、每个学科有贡献说明、真实问题有最终成果、目标到指标到证据可追踪；缺项必须返回具体field和修复路由。

```python
def test_design_validation_rejects_subject_without_contribution(client, teacher_token, project):
    result = client.post(f"/api/v1/projects/{project.id}/validate-activation", headers=teacher_token).json()["data"]
    assert any(b["code"] == "SUBJECT_CONTRIBUTION_MISSING" for b in result["blockers"])
```

- [ ] **Step 2: 完成已有贡献、目标、指标和证据计划的原地编辑。** 不通过删除重建模拟编辑；删除有关联时返回引用影响并要求显式确认。

- [ ] **Step 3: 重排设计页面。** 顺序固定为“真实问题 → 学科贡献 → 学习目标 → 评价指标 → 证据计划”；右侧仅显示紧凑完整度和问题清单，不嵌套卡片。

- [ ] **Step 4: 运行项目设计与迁移回归。**

Run: `pytest tests/test_project_designs.py tests/test_project_design_migration.py -q` and `npm test -- src/features/project-workspace/project-workspace.test.ts`

Expected: PASS；每个阻断能定位到具体编辑区；已有设计记录不丢失。

- [ ] **Step 5: Commit.**

```text
git add project/backend/app/modules/project_designs project/backend/app/modules/projects project/backend/tests project/frontend/src/features/project-workspace project/frontend/src/views/teacher/project-workspace/ProjectDesignView.vue
git commit -m "feat: complete traceable cross-subject design"
```

### Task 8: 备课、资源与工具上下文

**Files:**
- Modify: `project/backend/app/modules/lesson_plans/*`
- Modify: `project/backend/app/modules/resources/*`
- Create: `project/backend/app/modules/tool_context/{service.py,repository.py,policy.py}`
- Create: `project/backend/tests/test_tool_context_links.py`
- Modify: `project/backend/tests/test_resource_permissions.py`
- Implement: `project/frontend/src/views/teacher/project-workspace/ProjectPreparationView.vue`
- Refactor: `project/frontend/src/views/teacher/LessonPlanView.vue`
- Refactor: `project/frontend/src/views/teacher/ResourceListView.vue`
- Create: `project/frontend/src/features/tool-context/{types.ts,api.ts}`
- Create: `project/frontend/src/features/tool-context/tool-context.test.ts`

- [ ] **Step 1: 写独立/项目两种上下文测试。** 项目模式必须提供 project_id 和 placement；独立模式不得伪造项目ID；跨校项目拒绝关联。

- [ ] **Step 2: 实现 `ContextPicker` 数据合同。**

```ts
export type ToolContext =
  | { mode: 'independent' }
  | { mode: 'project'; projectId: string; phase: ProjectPhase; taskId?: string; goalId?: string }
```

- [ ] **Step 3: 让备课和资源使用统一上下文服务。** 保存时创建一次业务资产和一条项目引用；取消关联只删除引用，不删除原资产或文件。

- [ ] **Step 4: 实现项目备课页和独立工具页。** 项目进入时上下文锁定；独立进入时可选择“添加到项目”；AI生成内容先进入待审核版本。

- [ ] **Step 5: 运行上下文、资源权限和页面测试。**

Run: `pytest tests/test_tool_context_links.py tests/test_resource_permissions.py -q` and `npm test -- src/features/tool-context/tool-context.test.ts`

Expected: PASS；同一资源没有重复文件；项目页能回到独立资产；跨校关联403。

- [ ] **Step 6: Commit.**

```text
git add project/backend/app/modules project/backend/tests project/frontend/src/features/tool-context project/frontend/src/views/teacher
git commit -m "feat: connect lesson plans and resources to project context"
```

### Task 9: 任务实施与跨项目任务中心

**Files:**
- Modify: `project/backend/app/modules/tasks/{router.py,service.py,repository.py,policy.py}`
- Modify: `project/backend/app/schemas/task.py`
- Modify: `project/frontend/src/views/teacher/project-workspace/ProjectTaskChainView.vue`
- Rewrite: `project/frontend/src/views/teacher/TaskListView.vue`
- Modify: `project/frontend/src/api/tasks.ts`
- Test: `project/backend/tests/{test_task_chain.py,test_task_permissions.py}`
- Create: `project/frontend/src/views/teacher/task-center.test.ts`

- [ ] **Step 1: 写任务分配、依赖和发布阻断测试。** 无接收学生、跨项目学生、前置任务未满足、归档项目均不得发布。

- [ ] **Step 2: 统一任务状态。** `publish_status` 决定发布生命周期；学生个人执行进度不得继续写回任务全局 `status`，执行进度从分配与提交聚合计算。

- [ ] **Step 3: 实现项目任务实施页。** 按课前/课中/课后展示任务链；任务编辑包含目标、量规、分层、接收学生、资源、依赖、截止和提交次数；发布前显示影响预览。

- [ ] **Step 4: 将独立任务管理重构为任务中心。** 默认展示所有可管理项目的待发布、进行中、临期、未提交和待关闭任务；编辑动作跳回项目，不保留独立创建正式任务入口。

- [ ] **Step 5: 运行任务测试和类型检查。**

Run: `pytest tests/test_task_chain.py tests/test_task_permissions.py -q` and `npm test -- src/views/teacher/task-center.test.ts && npm run typecheck`

Expected: PASS；目标学生可见，其他学生不可见；任务中心无第二套编辑逻辑。

- [ ] **Step 6: Commit.**

```text
git add project/backend/app/modules/tasks project/backend/app/schemas/task.py project/backend/tests project/frontend/src/views/teacher project/frontend/src/api/tasks.ts
git commit -m "feat: unify project tasks and cross-project task center"
```

### Task 10: 学生项目空间与版本化学习证据

**Files:**
- Modify: `project/backend/app/modules/student_submissions/*`
- Modify: `project/backend/app/modules/submissions/*`
- Modify: `project/backend/app/models/submission_revision.py`
- Test: `project/backend/tests/{test_submission_revisions.py,test_submission_authorization.py}`
- Create: `project/backend/tests/test_student_submissions.py`
- Rewrite: `project/frontend/src/views/student/{DashboardView,StudentProjectView,TaskSubmitView}.vue`
- Modify: `project/frontend/src/features/student-space/*`
- Test: `project/frontend/src/views/student/student-learning-flow.test.ts`

- [ ] **Step 1: 写草稿、幂等提交、次数限制和版本保留测试。** 每次正式提交创建修订版本；再次提交不得覆盖首次证据；重复请求使用幂等键返回同一结果。

- [ ] **Step 2: 实现学生项目聚合接口。** 仅返回已发布任务、已发布资源、学生本人或必要小组信息以及已发布评价。

- [ ] **Step 3: 重构学生工作台与项目空间。** 学生先看项目真实问题、共同成果和自己的下一项任务；不复制教师端十个页面。

- [ ] **Step 4: 重构提交页。** 固定展示目标、量规、资源、截止、剩余次数；支持本地草稿恢复、附件预览、提交确认和版本列表。

- [ ] **Step 5: 运行提交授权与前端流程测试。**

Run: `pytest tests/test_submission_revisions.py tests/test_submission_authorization.py tests/test_student_submissions.py -q` and `npm test -- src/views/student/student-learning-flow.test.ts`

Expected: PASS；学生不能访问他人证据；第一次提交始终可追溯。

- [ ] **Step 6: Commit.**

```text
git add project/backend/app/modules/student_submissions project/backend/app/modules/submissions project/backend/app/models project/backend/tests project/frontend/src/views/student project/frontend/src/features/student-space
git commit -m "feat: add student project flow and versioned evidence"
```

### Task 11: 统一评价、反馈与订正

**Files:**
- Modify: `project/backend/app/modules/evaluation_plans/*`
- Modify: `project/backend/app/modules/evaluations/*`
- Modify: `project/backend/app/modules/submissions/service.py`
- Test: `project/backend/tests/{test_evaluation_service.py,test_evaluation_permissions.py,test_ai_submission_grading.py}`
- Implement: `project/frontend/src/views/teacher/project-workspace/ProjectEvaluationView.vue`
- Rewrite: `project/frontend/src/views/teacher/EvaluationListView.vue`
- Rewrite: `project/frontend/src/views/student/{EvaluationView,SubmissionFeedbackView}.vue`
- Modify: `project/frontend/src/features/evaluation-plan/*`

- [ ] **Step 1: 写单一评价事实与学生可见性测试。** AI只创建DRAFT；教师确认后REVIEWED；发布后PUBLISHED；订正完成后FINALIZED。学生旧入口与反馈页必须显示同一正式记录。

```python
def test_student_reads_same_published_record_from_all_feedback_endpoints(client, student_token, published_record):
    a = client.get("/api/v1/evaluation-plans/records", headers=student_token).json()["data"]
    b = client.get(f"/api/v1/submissions/{published_record.submission_id}/feedback", headers=student_token).json()["data"]
    assert a[0]["id"] == b["evaluation"]["id"] == published_record.id
```

- [ ] **Step 2: 停止新写入旧 `Evaluation` 和直接写 `Submission.score/comment`。** 保留历史读取适配器，并在响应中标记 `legacy=true`。

- [ ] **Step 3: 实现项目评价页。** 左侧提交队列，中间证据与作品，右侧量规和AI建议；教师修改AI建议分数时记录差异原因；发布前显示学生可见预览。

- [ ] **Step 4: 将独立评价页改为评价中心。** 聚合待评价和待发布反馈，点击后进入项目评价页；不提供第二套保存逻辑。

- [ ] **Step 5: 重构学生反馈与订正。** 只显示PUBLISHED/FINALIZED，明确“反馈依据”和订正入口；AI来源标签不能替代教师确认标签。

- [ ] **Step 6: 运行评价、权限、AI批改和学生流程测试。**

Run: `pytest tests/test_evaluation_service.py tests/test_evaluation_permissions.py tests/test_ai_submission_grading.py tests/test_submission_revisions.py -q` and `npm test -- src/views/student/student-learning-flow.test.ts`

Expected: PASS；不存在新旧分数不一致；草稿不可见；跨学生访问403。

- [ ] **Step 7: Commit.**

```text
git add project/backend/app/modules/evaluation_plans project/backend/app/modules/evaluations project/backend/app/modules/submissions project/backend/tests project/frontend/src/views project/frontend/src/features/evaluation-plan
git commit -m "feat: consolidate evaluation feedback and revision"
```

### Task 12: 学情改进、改进任务与再评价

**Files:**
- Modify: `project/backend/app/modules/improvements/*`
- Modify: `project/backend/app/modules/learning_profiles/*`
- Test: `project/backend/tests/test_improvement_loop.py`
- Create: `project/backend/tests/test_learning_profile_contract.py`
- Rewrite: `project/frontend/src/views/teacher/project-workspace/ProjectInsightsView.vue`
- Refactor: `project/frontend/src/views/teacher/ClassLearningProfile.vue`
- Modify: `project/frontend/src/features/learning-improvement/*`
- Create: `project/frontend/src/views/teacher/project-improvement.test.ts`

- [ ] **Step 1: 写“无评价证据不产生改进建议”和前后评价保留测试。** 改进任务必须追溯到原评价和原任务；二次评价不得覆盖第一次评价。

- [ ] **Step 2: 统一学情DTO。** 后端固定输出 `student_count`、`average_score`、`overall_mastery`、`mastery_distribution`、`knowledge_points`、`evidence_cutoff`、`generated_at`；前端API层统一转camelCase。

- [ ] **Step 3: 实现项目改进页。** 展示目标达成、共性问题、学生分层、证据引用、建议决策、生成改进任务和前后对比。

- [ ] **Step 4: 重构独立学情中心。** 班级/项目/学生三种视图共享真实聚合服务；无证据时显示来源缺口，不回退模拟数据。

- [ ] **Step 5: 运行改进、学情合同和页面测试。**

Run: `pytest tests/test_improvement_loop.py tests/test_learning_profile_contract.py tests/test_learning_profile_authorization.py -q` and `npm test -- project-improvement.test.ts`

Expected: PASS；所有改进建议可打开来源证据；前后评价均保留。

- [ ] **Step 6: Commit.**

```text
git add project/backend/app/modules/improvements project/backend/app/modules/learning_profiles project/backend/tests project/frontend/src/views/teacher project/frontend/src/features/learning-improvement
git commit -m "feat: connect learning insights to improvement loop"
```

### Task 13: 题库、组卷、试卷和智能批改能力中心

**Files:**
- Modify: `project/backend/app/modules/question_bank/*`
- Modify: `project/backend/app/modules/paper_generation/*`
- Modify: `project/backend/app/api/v1/{papers.py,paper_generator.py}`
- Test: `project/backend/tests/test_question_bank.py`
- Test: `project/backend/tests/{test_paper_generator.py,test_paper_exporting.py,test_paper_ai_grading.py}`
- Refactor: `project/frontend/src/views/teacher/{QuestionBankView,QuestionBankDashboard,SmartCompose,PaperGeneratorView,PaperListView,PaperGradingView,AiGradingView}.vue`
- Modify: `project/frontend/src/router/index.ts`

- [ ] **Step 1: 写独立/项目测评上下文和真实题库统计测试。** 覆盖率由题目与知识点真实关系计算；分母为零返回null；项目测评结果可回流学情。

- [ ] **Step 2: 将题库、组卷、试卷和批改放入“题库与测评”路由组。** 页面统一使用 `ContextPicker`；组卷结果可保存为独立试卷或项目的前/中/后测。

- [ ] **Step 3: 接通Word/PDF/HTML导出和实际下载状态。** 删除“开发中”提示；导出失败可重试并保留错误信息。

- [ ] **Step 4: 智能批改只生成批改草稿。** 项目上下文下通过统一评价服务创建AI草稿，教师仍在项目评价页确认；独立试卷保留其自身批改流程。

- [ ] **Step 5: 运行题库、组卷、批改、导出和构建测试。**

Run: `pytest tests/test_question_bank.py tests/test_paper_generator.py tests/test_paper_exporting.py tests/test_paper_ai_grading.py -q` and `npm test -- src/__tests__/paper-format.test.ts && npm run build`

Expected: PASS；无硬编码85%覆盖率；导出文件可打开；项目批改草稿进入统一评价。

- [ ] **Step 6: Commit.**

```text
git add project/backend/app/modules/question_bank project/backend/app/modules/paper_generation project/backend/app/api/v1 project/backend/tests project/frontend/src/views/teacher project/frontend/src/router
git commit -m "feat: rebuild assessment tools as context-aware capabilities"
```

### Task 14: AI治理与五类AI能力

**Files:**
- Modify: `project/backend/app/modules/ai_jobs/*`
- Modify: `project/backend/app/api/v1/ai.py`
- Modify: `project/backend/app/modules/{lesson_plans,evaluations,paper_generation}/`
- Create: `project/backend/app/modules/ai_scenes/{diagnosis.py,project_design.py,task_differentiation.py,evaluation_advice.py,reflection.py}`
- Create: `project/backend/tests/test_ai_governance.py`
- Create: `project/backend/tests/test_ai_scene_contracts.py`
- Refactor: `project/frontend/src/views/teacher/project-workspace/ProjectAiContentView.vue`
- Refactor: `project/frontend/src/views/admin/AiGovernanceView.vue`
- Modify: `project/frontend/src/features/ai-content/*`

- [ ] **Step 1: 为五类场景写输入输出合同和失败测试。** 每个请求含项目上下文摘要、prompt版本和provider；失败不产生输出版本或业务分数。

```python
@pytest.mark.parametrize("scene", ["diagnosis", "project_design", "task_differentiation", "evaluation_advice", "reflection"])
def test_ai_scene_failure_never_creates_adopted_output(scene, failing_provider, service):
    job = service.run(scene=scene, provider=failing_provider)
    assert job.status.name == "FAILED"
    assert job.adopted_version_id is None
```

- [ ] **Step 2: 实现五个场景适配器。** 适配器只负责构造结构化输入、校验输出和记录质量问题；业务写入只发生在教师采纳服务中。

- [ ] **Step 3: 移除生产随机回退和伪成功。** 开发演示数据必须由显式配置开启并标记“演示样例，非AI结果”，且不得发布到正式项目。

- [ ] **Step 4: 重构项目AI页面和管理治理页。** 教师页展示版本、来源、质量问题、审核与采纳；管理员页按学校范围展示成功率、失败原因和采纳率。

- [ ] **Step 5: 运行AI合同、治理、评价和出卷测试。**

Run: `pytest tests/test_ai_governance.py tests/test_ai_scene_contracts.py tests/test_ai_submission_grading.py tests/test_paper_generation_module.py -q`

Expected: PASS；Provider失败无业务结果；所有采纳记录可追溯到教师。

- [ ] **Step 6: Commit.**

```text
git add project/backend/app/modules project/backend/app/api/v1/ai.py project/backend/tests project/frontend/src/features/ai-content project/frontend/src/views
git commit -m "feat: govern AI across the teaching evaluation loop"
```

### Task 15: 结项归档、管理功能与运营证据

**Files:**
- Modify: `project/backend/app/modules/projects/service.py`
- Modify: `project/backend/app/modules/operational_evidence/*`
- Modify: `project/backend/app/api/v1/dashboard.py`
- Test: `project/backend/tests/{test_project_closure.py,test_operational_metrics.py,test_dashboard_scope.py}`
- Create: `project/backend/tests/test_identity_service.py`
- Rewrite: `project/frontend/src/views/teacher/project-workspace/ProjectClosureView.vue`
- Refactor: `project/frontend/src/views/admin/{DashboardView,EvidenceCenterView,SystemSettingsView,UserManagementView}.vue`

- [ ] **Step 1: 写结项阻断、学校范围、设置持久化和用户停用测试。** 未发布评价、开放blocker、未确认反思均不能归档；school_admin只见本校；用户有业务引用时停用而非硬删。

- [ ] **Step 2: 实现结项页。** 显示完整度、反思、学生参与、评价、订正、AI使用、脱敏案例和可沉淀资产；归档确认列出只读影响。

- [ ] **Step 3: 完成管理真实动作。** 系统设置真实保存、Logo上传、用户停用和审计；删除假成功按钮。

- [ ] **Step 4: 修复驾驶舱统一作用域。** 所有列表、图表、最近活动和导出共享同一school scope服务。

- [ ] **Step 5: 运行结项、运营和权限测试。**

Run: `pytest tests/test_project_closure.py tests/test_operational_metrics.py tests/test_dashboard_scope.py tests/test_identity_service.py -q`

Expected: PASS；跨校数据为零泄漏；归档后项目只读；管理操作真实持久化。

- [ ] **Step 6: Commit.**

```text
git add project/backend/app/modules/projects project/backend/app/modules/operational_evidence project/backend/app/api/v1/dashboard.py project/backend/tests project/frontend/src/views
git commit -m "feat: complete closure and scoped operational evidence"
```

### Task 16: 数据回填、读写切换与旧入口下线

**Files:**
- Create: `project/backend/alembic/versions/h2a3b4c5d6e7_backfill_rebuild_context.py`
- Create: `project/backend/app/maintenance/verify_rebuild_migration.py`
- Create: `project/backend/tests/test_rebuild_data_backfill.py`
- Modify: `project/backend/app/core/config.py`
- Modify: `project/frontend/src/router/index.ts`
- Delete after verified cutover: `project/frontend/src/e2e/core-teaching-loop.spec.ts`

- [ ] **Step 1: 写幂等回填和数量一致性测试。** 两次执行产生相同目标数量；所有新记录能回到源ID；评价总分和提交版本不变。

- [ ] **Step 2: 实现M2-M4回填迁移与校验脚本。** 校验脚本输出JSON：源/目标数量、孤儿记录、跨校异常、未分类任务资源、评价差异。

- [ ] **Step 3: 在数据库副本执行迁移和校验。**

Run:

```text
python -m alembic upgrade head
python -m app.maintenance.verify_rebuild_migration --format json
python -m alembic downgrade h1a2b3c4d5e6
python -m alembic upgrade head
```

Expected: 校验无孤儿和跨校异常；降级/再升级数量一致。

- [ ] **Step 4: 按顺序切换功能开关。** 先打开新项目工作区读取，再打开统一评价写入；观察一轮测试后关闭旧写接口。不得同时启用新旧评价写入。

- [ ] **Step 5: 删除已替代前端入口并保留重定向。** 旧项目详情重定向项目总览；旧AI批改和评价写页面重定向对应能力中心或项目页。

- [ ] **Step 6: 运行全量后端、前端和迁移测试。**

Run: `pytest -q` and `npm test && npm run typecheck && npm run build`

Expected: 全部通过；无占位E2E被计入单元测试；构建无新增错误。

- [ ] **Step 7: Commit.**

```text
git add project/backend project/frontend
git commit -m "refactor: cut over to the unified teaching loop"
```

### Task 17: 真实浏览器E2E、视觉QA与发布验收

**Files:**
- Modify: `project/frontend/package.json`
- Create: `project/frontend/playwright.config.ts`
- Create: `project/frontend/e2e/{fixtures.ts,auth.setup.ts,core-loop.spec.ts,capability-context.spec.ts,permissions.spec.ts,ai-failure.spec.ts,responsive.spec.ts}`
- Create: `docs/acceptance/2026-07-24-release-acceptance.md`
- Modify: `README.md`

- [ ] **Step 1: 安装和配置Playwright。** 增加 `test:e2e` 与 `test:e2e:ui`；失败保存截图、视频和trace；测试使用独立数据库与可控AI Provider stub。

- [ ] **Step 2: 实现“保护海洋，从我做起”全链路。**

```ts
test('complete project teaching evaluation improvement loop', async ({ teacherPage, studentPage, adminPage }) => {
  const project = await teacherPage.createOceanProject()
  await teacherPage.confirmDiagnosis(project)
  await teacherPage.completeCrossSubjectDesign(project)
  await teacherPage.publishAssignedTask(project)
  await studentPage.submitEvidence(project)
  await teacherPage.publishRubricFeedback(project)
  await studentPage.reviseAndResubmit(project)
  await teacherPage.completeSecondEvaluationAndArchive(project)
  await adminPage.expectProjectEvidenceVisibleWithinSchool(project)
})
```

- [ ] **Step 3: 实现独立工具关联项目场景。** 独立智能备课和智能组卷均能在保存时关联项目，项目时间线出现一次引用且不复制原资产。

- [ ] **Step 4: 实现权限与失败场景。** 覆盖跨校看板、他人提交、未发布评价、AI超时、无接收对象发布、归档编辑、用户停用。

- [ ] **Step 5: 实现桌面、平板、移动视觉与布局检查。** 视口至少 `1440x900`、`1024x768`、`390x844`；检查文字溢出、固定栏遮挡、表格可用、阶段导航和对话框。

- [ ] **Step 6: 运行发布质量门禁。**

Run:

```text
cd project/backend && pytest -q
cd project/frontend && npm test && npm run typecheck && npm run build && npm run test:e2e
```

Expected: 全部通过；P0/P1缺陷为零；失败产物可定位到具体步骤。

- [ ] **Step 7: 更新文档并提交。**

```text
git add project/frontend/e2e project/frontend/playwright.config.ts project/frontend/package.json README.md docs/acceptance/2026-07-24-release-acceptance.md
git commit -m "test: verify complete intelligent cross-subject learning loop"
```

## 6. 逐阶段验收标准

### Phase 0：工程与设计基础

- Git远程历史已同步，重构分支可回退到基线提交。
- 通用UI组件测试、类型检查和构建通过。
- 新表和字段只做扩展，不改变历史记录数量。
- 工作区上下文API在教师、学生、学校管理员和跨校用户下权限正确。
- 所有新页面都能复用同一项目上下文和状态映射。

### Phase 1：项目主线骨架

- 一级导航明确区分“智跨学评主线”和“独立能力中心”。
- 项目内有七阶段导航和唯一下一步，不再出现旧版详情并行编辑。
- 教师工作台无静态待办，所有项目与待办来自真实接口。
- 学情无证据时不生成画像；跨学科设计缺项能定位到具体编辑区。
- 项目在设计不完整时不能进入正式实施。

### Phase 2：教学实施闭环

- 教案和资源支持独立/项目两种模式，项目引用不复制业务资产。
- 无接收学生的任务前后端均阻断发布。
- 目标学生刷新后可看到任务，其他学生不可见。
- 学生可保存草稿、提交、查看版本；重复请求不会生成重复提交。
- 首次提交与后续订正证据均可追溯。

### Phase 3：评价与智能改进

- 新评价只写 `EvaluationRecord`；教师页和学生页显示同一正式结果。
- AI建议处于草稿，教师发布前学生不可见。
- 评价可追溯到目标、量规、学生提交和证据。
- 改进建议必须有证据引用，改进任务能回到原评价。
- 题库、组卷、智能批改、资源和学情工具既可独立使用，也可关联项目。
- AI失败不产生随机内容、模拟分数或成功提示。

### Phase 4：结项、迁移与发布

- 数据回填幂等，源/目标数量、评价分数和提交版本一致。
- 学校管理员所有图表、列表、导出和活动记录均为本校数据。
- 项目归档前阻断全部处理，归档后只读。
- 旧页面不再承担写入，旧URL重定向到新页面。
- “保护海洋，从我做起”全链路由真实浏览器测试通过。
- 桌面、平板和移动端无文字重叠、遮挡、不可达操作或布局跳动。

## 7. 测试边界

| 层级 | 必测内容 | 不允许替代的验证 |
| --- | --- | --- |
| 模型/服务单元测试 | 状态机、聚合算法、证据追溯、AI失败、迁移幂等 | 接口权限与前端流程 |
| API集成测试 | 参数、响应合同、事务回滚、跨校/跨学生权限 | 浏览器交互与视觉状态 |
| 前端组件测试 | 通用UI状态、按钮禁用、上下文选择、表单保存取消 | 真实登录和跨页面数据 |
| Playwright E2E | 教师/学生/管理员完整业务、独立工具关联、失败场景 | 高并发和长时间稳定性 |
| 人工业务验收 | 文案、教学逻辑、量规可理解性、导出文件、演示流畅度 | 自动回归 |
| 数据迁移验收 | 数量、映射、孤儿、跨校、分数、版本、可回滚 | 只看迁移命令退出码 |

### 必须覆盖的反例

1. 项目没有支持学科贡献时不能通过设计完整性检查。
2. 项目没有学习证据时不能生成确定性的学生分层结论。
3. 独立工具关联项目时选择了其他学校项目，必须返回403。
4. 任务没有接收学生、依赖未满足或项目已归档时不能发布。
5. 学生不能访问他人提交、草稿、附件或未发布反馈。
6. AI Provider超时或返回非法结构时不产生业务分数或正式资产。
7. 教师修改AI建议分数而不填写差异原因时不能确认评价。
8. 评价未发布、质量blocker开放或反思未确认时不能结项。
9. 同一迁移执行两次不得重复评价、证据、上下文链接或阶段记录。
10. 旧入口不可继续写入第二套任务或评价数据。

## 8. 完成定义

本重构只有在以下条件全部成立时才算完成：

1. 教师能从一个跨学科项目完成诊断、设计、准备、实施、评价、改进和归档。
2. 学生能完成任务、提交、查看正式反馈、订正和再次提交。
3. 独立工具可以单独使用，也可以关联项目，且不复制业务事实。
4. “智、跨、学、评”四个维度均可通过真实数据和页面行为证明。
5. 数据迁移可验证、可重复、可回滚，历史数据保持可读。
6. 后端测试、前端测试、类型检查、生产构建和真实浏览器E2E全部通过。
7. P0/P1缺陷为零，所有页面符合通用UI设计规范与响应式边界。
