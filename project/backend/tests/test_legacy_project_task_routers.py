def test_legacy_project_and_task_routers_reexport_module_routers():
    from app.api.v1 import projects, tasks
    from app.modules.projects.router import router as projects_router
    from app.modules.tasks.router import router as tasks_router

    assert projects.router is projects_router
    assert tasks.router is tasks_router
