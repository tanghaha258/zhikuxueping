# 初中跨学科教学评一体化平台

面向初中跨学科主题学习的“智跨学评”平台。正式教学以跨学科项目为主线，智能备课、题库组卷、智能批改、资源、评价和学情能力也可以独立使用并关联项目。

## 开发入口

所有智能体和开发者按以下顺序开始工作：

1. 阅读 `AGENTS.md`，确认任务所有权和多会话规则。
2. 阅读 `docs/superpowers/plans/2026-07-24-zhi-kua-xue-ping-full-rebuild.md` 中的执行约束、所属Task和验收标准。
3. 产品决策以 `docs/superpowers/specs/2026-07-24-zhi-kua-xue-ping-redesign.md` 为准。
4. `00_项目总览.md`、`01_PRD_产品需求说明.md`、`02_业务流程与信息架构.md` 仅作为原始产品背景，冲突时以后两份重构文档为准。

项目目录外的清理备份只用于误删恢复，禁止作为需求、设计或实施依据。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Element Plus、Pinia、Vue Router、SCSS
- 后端：FastAPI、SQLAlchemy 2、Pydantic、Alembic
- 数据库：开发环境默认SQLite，生产环境支持PostgreSQL
- 测试：Pytest、Vitest；Playwright将在总计划Task 17接入

## 项目结构

```text
├─ AGENTS.md
├─ 00_项目总览.md
├─ 01_PRD_产品需求说明.md
├─ 02_业务流程与信息架构.md
├─ docs/superpowers/
│  ├─ specs/2026-07-24-zhi-kua-xue-ping-redesign.md
│  └─ plans/2026-07-24-zhi-kua-xue-ping-full-rebuild.md
└─ project/
   ├─ backend/
   └─ frontend/
```

## 本地启动

Windows可在项目根目录运行 `start.bat`。手动启动方式如下。

后端：

```powershell
cd project/backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe -m database.seed
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 2358
```

前端：

```powershell
cd project/frontend
npm install
npm run dev
```

- 前端：`http://localhost:1800`
- 后端：`http://localhost:2358`
- API文档：`http://localhost:2358/docs`

## 基线验证

后端：

```powershell
cd project/backend
.\venv\Scripts\python.exe -m pytest -q
```

前端：

```powershell
cd project/frontend
npm test
npm run typecheck
npm run build
```

多会话开发必须先完成总计划Task 0并创建可共享的Git基线；在此之前不要创建并行worktree。
