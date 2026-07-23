from fastapi import APIRouter
from app.api.v1 import submissions, evaluations, upload, ai, dashboard, papers, paper_generator, prompt_template, learning_profile
from app.modules.identity.auth_router import router as auth_router
from app.modules.identity.users_router import router as users_router
from app.modules.schools.router import router as schools_router
from app.modules.projects.router import router as projects_router
from app.modules.project_designs.router import router as project_designs_router
from app.modules.resources.router import router as resources_router
from app.modules.subjects.router import router as subjects_router
from app.modules.tasks.router import router as tasks_router
from app.modules.question_bank.router import router as question_bank_router
from app.modules.evaluation_plans.router import router as evaluation_plans_router
from app.modules.ai_jobs.router import router as ai_jobs_router
# 核心闭环扩展：Task 6/7/8 路由
from app.modules.submissions.student_router import router as student_submissions_router
from app.modules.improvements.router import router as improvements_router
from app.modules.operational_evidence.router import router as operational_evidence_router
# 统一项目上下文（Task 3）
from app.modules.project_workspace.router import router as project_workspace_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(schools_router)
api_router.include_router(subjects_router)
api_router.include_router(projects_router)
api_router.include_router(project_designs_router)
api_router.include_router(users_router)
api_router.include_router(tasks_router)
api_router.include_router(submissions.router)
api_router.include_router(evaluations.router)
api_router.include_router(resources_router)
api_router.include_router(upload.router)
api_router.include_router(ai.router)
api_router.include_router(dashboard.router)
api_router.include_router(papers.router)
api_router.include_router(paper_generator.router)
api_router.include_router(question_bank_router)
api_router.include_router(prompt_template.router)
api_router.include_router(learning_profile.router)
api_router.include_router(evaluation_plans_router)
api_router.include_router(ai_jobs_router)
api_router.include_router(student_submissions_router)
api_router.include_router(improvements_router)
api_router.include_router(operational_evidence_router)
api_router.include_router(project_workspace_router)

