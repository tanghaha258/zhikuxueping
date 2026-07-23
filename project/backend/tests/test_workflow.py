"""
任务/项目状态流转 API 测试
"""
import pytest


def _teacher_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "wf_teacher", "password": "wf1234",
        "email": "wf_teacher@test.com", "display_name": "WF教师", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "wf_teacher", "password": "wf1234",
    })
    return resp.json()["data"]["access_token"]


def _admin_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "wf_admin", "password": "wf1234",
        "email": "wf_admin@test.com", "display_name": "WF管理员", "role": "admin",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "wf_admin", "password": "wf1234",
    })
    return resp.json()["data"]["access_token"]


def _student_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "wf_student", "password": "wf1234",
        "email": "wf_student@test.com", "display_name": "WF学生", "role": "student",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "wf_student", "password": "wf1234",
    })
    return resp.json()["data"]["access_token"]


class TestProjectWorkflow:
    def _create_project(self, client, token):
        resp = client.post("/api/v1/projects", json={
            "title": "流转测试项目", "grade": "七年级",
        }, headers={"Authorization": f"Bearer {token}"})
        return resp.json()["data"]["id"]

    def _complete_design(self, client, token, pid):
        """构造通过完整性检查的项目设计（核心+支撑+问题+目标+指标+证据计划）。

        依据计划 4.3 状态机：draft -> pending_review -> active，
        activate 前必须通过完整性检查，故测试需先补齐设计。
        """
        h = {"Authorization": f"Bearer {token}"}
        client.put(f"/api/v1/projects/{pid}/design/problem",
                   json={"context": "测试情境"}, headers=h)
        client.post(f"/api/v1/projects/{pid}/design/contributions",
                    json={"subject_id": "sub-core", "role": "core",
                          "knowledge": "k", "thinking": "t", "inquiry": "i"}, headers=h)
        client.post(f"/api/v1/projects/{pid}/design/contributions",
                    json={"subject_id": "sub-support", "role": "support",
                          "knowledge": "k", "thinking": "t", "inquiry": "i"}, headers=h)
        r = client.post(f"/api/v1/projects/{pid}/design/goals",
                        json={"goal_type": "ability", "name": "目标"}, headers=h)
        goal_id = r.json()["data"]["id"]
        r = client.post(f"/api/v1/projects/{pid}/design/indicators",
                        json={"goal_id": goal_id, "observable_behavior": "行为"}, headers=h)
        indicator_id = r.json()["data"]["id"]
        client.post(f"/api/v1/projects/{pid}/design/evidence-plans",
                    json={"indicator_id": indicator_id, "stage": "in_class",
                          "evidence_type": "artifact", "collector": "student",
                          "required": True}, headers=h)

    def _submit_and_activate(self, client, token, pid):
        """完整项目：draft -> pending_review -> active。"""
        h = {"Authorization": f"Bearer {token}"}
        client.post(f"/api/v1/projects/{pid}/submit-for-review", headers=h)
        return client.post(f"/api/v1/projects/{pid}/activate", headers=h)

    def test_activate_project(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        self._complete_design(client, token, pid)
        resp = self._submit_and_activate(client, token, pid)
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "active"

    def test_complete_project(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        self._complete_design(client, token, pid)
        self._submit_and_activate(client, token, pid)
        resp = client.post(f"/api/v1/projects/{pid}/complete",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "completed"

    def test_archive_project(self, client):
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        self._complete_design(client, token, pid)
        self._submit_and_activate(client, token, pid)
        client.post(f"/api/v1/projects/{pid}/complete",
                    headers={"Authorization": f"Bearer {token}"})
        resp = client.post(f"/api/v1/projects/{pid}/archive",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "archived"

    def test_activate_from_draft_without_submit_returns_409(self, client):
        """draft -> active 直接激活被拒，必须先 submit_for_review。"""
        token = _teacher_token(client)
        pid = self._create_project(client, token)
        self._complete_design(client, token, pid)
        resp = client.post(f"/api/v1/projects/{pid}/activate",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 409


class TestTaskWorkflow:
    def _create_project_and_task(self, client, token):
        pid = client.post("/api/v1/projects", json={"title": "任务流转"},
                          headers={"Authorization": f"Bearer {token}"}).json()["data"]["id"]
        tid = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "流转任务", "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"}).json()["data"]["id"]
        return pid, tid

    def test_publish_task(self, client):
        token = _teacher_token(client)
        _, tid = self._create_project_and_task(client, token)
        resp = client.post(f"/api/v1/tasks/{tid}/publish",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "in_progress"

    def test_close_task(self, client):
        token = _teacher_token(client)
        _, tid = self._create_project_and_task(client, token)
        client.post(f"/api/v1/tasks/{tid}/publish",
                    headers={"Authorization": f"Bearer {token}"})
        resp = client.post(f"/api/v1/tasks/{tid}/close",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "evaluated"

    def test_student_cannot_publish(self, client):
        t_token = _teacher_token(client)
        s_token = _student_token(client)
        _, tid = self._create_project_and_task(client, t_token)
        resp = client.post(f"/api/v1/tasks/{tid}/publish",
                           headers={"Authorization": f"Bearer {s_token}"})
        assert resp.status_code == 403

    def test_publish_already_published(self, client):
        token = _teacher_token(client)
        _, tid = self._create_project_and_task(client, token)
        client.post(f"/api/v1/tasks/{tid}/publish",
                    headers={"Authorization": f"Bearer {token}"})
        resp = client.post(f"/api/v1/tasks/{tid}/publish",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400
        assert "不允许" in resp.json()["message"]

    def test_close_not_published(self, client):
        token = _teacher_token(client)
        _, tid = self._create_project_and_task(client, token)
        resp = client.post(f"/api/v1/tasks/{tid}/close",
                           headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 400


class TestTaskStats:
    def _create_project_and_task(self, client, token):
        pid = client.post("/api/v1/projects", json={"title": f"统计项目"},
                          headers={"Authorization": f"Bearer {token}"}).json()["data"]["id"]
        tid = client.post("/api/v1/tasks", json={
            "project_id": pid, "title": "统计任务", "student_ids": [],
        }, headers={"Authorization": f"Bearer {token}"}).json()["data"]["id"]
        return pid, tid

    def test_stats_endpoint(self, client):
        token = _teacher_token(client)
        resp = client.get("/api/v1/tasks/stats",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "active_projects" in data
        assert "pending_evaluation" in data
        assert "total_resources" in data
        assert "upcoming_deadlines" in data
