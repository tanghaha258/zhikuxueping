"""
项目/任务/提交/评价/资源 API 测试
"""
import pytest


def _admin_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "biz_admin", "password": "biz1234",
        "email": "biz@test.com", "display_name": "业务管理员", "role": "admin",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "biz_admin", "password": "biz1234",
    })
    return resp.json()["data"]["access_token"]


def _teacher_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "teacher1", "password": "tch1234",
        "email": "teacher1@test.com", "display_name": "教师1", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "teacher1", "password": "tch1234",
    })
    return resp.json()["data"]["access_token"]


def _student_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "student1", "password": "stu1234",
        "email": "student1@test.com", "display_name": "学生1", "role": "student",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "student1", "password": "stu1234",
    })
    return resp.json()["data"]["access_token"]


class TestProjects:
    def test_create_project(self, client):
        token = _teacher_token(client)
        resp = client.post("/api/v1/projects", json={
            "title": "校园垃圾分类调查报告",
            "description": "跨学科项目：统计校园垃圾产生量并提出改进方案",
            "grade": "七年级",
            "subject_ids": [],
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "校园垃圾分类调查报告"
        assert data["status"] == "draft"

    def test_list_projects(self, client):
        token = _teacher_token(client)
        client.post("/api/v1/projects", json={"title": "项目A"},
                    headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/api/v1/projects", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["total"] >= 1

    def test_search_projects(self, client):
        token = _teacher_token(client)
        client.post("/api/v1/projects", json={"title": "环保项目"},
                    headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/api/v1/projects?keyword=环保",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] >= 1

    def test_get_project(self, client):
        token = _teacher_token(client)
        create_resp = client.post("/api/v1/projects", json={"title": "详情项目"},
                                  headers={"Authorization": f"Bearer {token}"})
        pid = create_resp.json()["data"]["id"]
        resp = client.get(f"/api/v1/projects/{pid}",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "详情项目"

    def test_update_project(self, client):
        token = _teacher_token(client)
        create_resp = client.post("/api/v1/projects", json={"title": "原项目"},
                                  headers={"Authorization": f"Bearer {token}"})
        pid = create_resp.json()["data"]["id"]
        resp = client.put(f"/api/v1/projects/{pid}", json={"title": "改后项目"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "改后项目"

    def test_delete_project(self, client):
        token = _teacher_token(client)
        create_resp = client.post("/api/v1/projects", json={"title": "待删除"},
                                  headers={"Authorization": f"Bearer {token}"})
        pid = create_resp.json()["data"]["id"]
        resp = client.delete(f"/api/v1/projects/{pid}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestTasks:
    def _create_project(self, client, token):
        resp = client.post("/api/v1/projects", json={"title": "任务测试项目"},
                           headers={"Authorization": f"Bearer {token}"})
        return resp.json()["data"]["id"]

    def test_create_task(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        resp = client.post("/api/v1/tasks", json={
            "project_id": pid,
            "title": "数据收集任务",
            "description": "收集一周的垃圾数据",
            "task_type": "individual",
            "max_score": 100,
            "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["title"] == "数据收集任务"
        assert data["project_id"] == pid

    def test_list_tasks(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "任务1", "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"})
        resp = client.get(f"/api/v1/tasks?project_id={pid}",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["total"] >= 1

    def test_get_task(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        create_resp = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "单个任务", "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"})
        tid = create_resp.json()["data"]["id"]
        resp = client.get(f"/api/v1/tasks/{tid}",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "单个任务"

    def test_update_task(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        create_resp = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "旧标题", "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"})
        tid = create_resp.json()["data"]["id"]
        resp = client.put(f"/api/v1/tasks/{tid}", json={"title": "新标题"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "新标题"

    def test_delete_task(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        create_resp = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "待删除", "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"})
        tid = create_resp.json()["data"]["id"]
        resp = client.delete(f"/api/v1/tasks/{tid}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200


class TestSubmissions:
    def _create_project_and_task(self, client, token):
        pid = client.post("/api/v1/projects", json={"title": "提交测试"},
                          headers={"Authorization": f"Bearer {token}"}).json()["data"]["id"]
        tid = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "提交任务", "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"}).json()["data"]["id"]
        return pid, tid

    def test_submit(self, client):
        t_token = _teacher_token(client)
        s_token = _student_token(client)
        _, tid = self._create_project_and_task(client, t_token)
        resp = client.post("/api/v1/submissions", json={
            "task_id": tid,
            "content": "这是我的作业内容",
            "file_urls": [],
        }, headers={"Authorization": f"Bearer {s_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["content"] == "这是我的作业内容"
        assert data["status"] == "submitted"

    def test_get_my_submission(self, client):
        t_token = _teacher_token(client)
        s_token = _student_token(client)
        _, tid = self._create_project_and_task(client, t_token)
        client.post("/api/v1/submissions", json={"task_id": tid, "content": "我的作业"},
                    headers={"Authorization": f"Bearer {s_token}"})
        resp = client.get(f"/api/v1/submissions/task/{tid}/my",
                          headers={"Authorization": f"Bearer {s_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["content"] == "我的作业"

    def test_teacher_grade_submission(self, client):
        t_token = _teacher_token(client)
        s_token = _student_token(client)
        _, tid = self._create_project_and_task(client, t_token)
        sub_resp = client.post("/api/v1/submissions", json={"task_id": tid, "content": "作业"},
                               headers={"Authorization": f"Bearer {s_token}"})
        sid = sub_resp.json()["data"]["id"]
        resp = client.patch(f"/api/v1/submissions/{sid}", json={"score": 85, "comment": "做得好"},
                            headers={"Authorization": f"Bearer {t_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["score"] == 85

    def test_list_submissions_by_task(self, client):
        t_token = _teacher_token(client)
        s_token = _student_token(client)
        _, tid = self._create_project_and_task(client, t_token)
        client.post("/api/v1/submissions", json={"task_id": tid, "content": "作业1"},
                    headers={"Authorization": f"Bearer {s_token}"})
        resp = client.get(f"/api/v1/submissions/task/{tid}",
                          headers={"Authorization": f"Bearer {t_token}"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1


class TestEvaluations:
    def _create_project_and_task(self, client, token):
        pid = client.post("/api/v1/projects", json={"title": "评价测试"},
                          headers={"Authorization": f"Bearer {token}"}).json()["data"]["id"]
        tid = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "评价任务", "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"}).json()["data"]["id"]
        return pid, tid

    def test_create_evaluation(self, client, db_session):
        """旧写入入口已弃用：POST /evaluations 返回 410，不写入旧表。

        新评价请使用 POST /api/v1/evaluation-plans/records 创建 EvaluationRecord。
        """
        t_token = _teacher_token(client)
        _, tid = self._create_project_and_task(client, t_token)
        resp = client.post("/api/v1/evaluations", json={
            "task_id": tid,
            "student_id": "student1",
            "score": 90,
            "comment": "非常优秀",
            "eval_type": "teacher",
        }, headers={"Authorization": f"Bearer {t_token}"})
        assert resp.status_code == 410
        # 未写入旧表
        from app.models.evaluation import Evaluation
        assert db_session.query(Evaluation).filter_by(task_id=tid).count() == 0

    def test_list_evaluations_by_task(self, client, db_session):
        """只读路径保留：直接 DB 播种旧版评价后仍可读取。"""
        from app.models.evaluation import Evaluation
        t_token = _teacher_token(client)
        _, tid = self._create_project_and_task(client, t_token)
        # 直接构造旧版评价（绕过已弃用的 POST /evaluations）
        db_session.add(Evaluation(
            task_id=tid,
            student_id="s1",
            evaluator_id="legacy-teacher",
            score=80,
            comment="legacy",
            eval_type="teacher",
            is_legacy=True,
        ))
        db_session.commit()
        resp = client.get(
            f"/api/v1/evaluations/task/{tid}",
            headers={"Authorization": f"Bearer {t_token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1


class TestResources:
    def _create_project(self, client, token):
        resp = client.post("/api/v1/projects", json={"title": "资源测试项目"},
                           headers={"Authorization": f"Bearer {token}"})
        return resp.json()["data"]["id"]

    def test_create_resource(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        resp = client.post("/api/v1/resources", json={
            "project_id": pid,
            "title": "教学文档.pdf",
            "res_type": "document",
            "url": "/uploads/doc.pdf",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "教学文档.pdf"

    def test_list_resources(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        client.post("/api/v1/resources", json={
            "project_id": pid, "title": "资源1", "res_type": "document",
        }, headers={"Authorization": f"Bearer {token}"})
        resp = client.get(
            f"/api/v1/resources?project_id={pid}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert len(resp.json()["data"]) >= 1

    def test_delete_resource(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        create_resp = client.post("/api/v1/resources", json={
            "project_id": pid, "title": "待删除", "res_type": "image",
        }, headers={"Authorization": f"Bearer {token}"})
        rid = create_resp.json()["data"]["id"]
        resp = client.delete(f"/api/v1/resources/{rid}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
