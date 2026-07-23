"""
学校/班级管理 API 测试
"""
import pytest


def _admin_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "school_admin_test", "password": "school1234",
        "email": "schooladmin@test.com", "display_name": "学校管理员", "role": "admin",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "school_admin_test", "password": "school1234",
    })
    return resp.json()["data"]["access_token"]


class TestSchools:
    def test_create_school(self, client):
        token = _admin_token(client)
        resp = client.post("/api/v1/schools", json={
            "name": "测试中学",
            "code": "TEST001",
            "region": "测试区",
            "address": "测试路1号",
            "contact_name": "联系人",
            "contact_phone": "13800138000",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "测试中学"
        assert data["code"] == "TEST001"

    def test_list_schools(self, client):
        token = _admin_token(client)
        client.post("/api/v1/schools", json={"name": "学校A"},
                    headers={"Authorization": f"Bearer {token}"})
        client.post("/api/v1/schools", json={"name": "学校B"},
                    headers={"Authorization": f"Bearer {token}"})
        resp = client.get("/api/v1/schools", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 2

    def test_get_school(self, client):
        token = _admin_token(client)
        create_resp = client.post("/api/v1/schools", json={"name": "获取测试学校"},
                                  headers={"Authorization": f"Bearer {token}"})
        school_id = create_resp.json()["data"]["id"]
        resp = client.get(f"/api/v1/schools/{school_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "获取测试学校"

    def test_update_school(self, client):
        token = _admin_token(client)
        create_resp = client.post("/api/v1/schools", json={"name": "旧名字"},
                                  headers={"Authorization": f"Bearer {token}"})
        school_id = create_resp.json()["data"]["id"]
        resp = client.put(f"/api/v1/schools/{school_id}", json={"name": "新名字"},
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "新名字"

    def test_delete_school(self, client):
        token = _admin_token(client)
        create_resp = client.post("/api/v1/schools", json={"name": "待删除学校"},
                                  headers={"Authorization": f"Bearer {token}"})
        school_id = create_resp.json()["data"]["id"]
        resp = client.delete(f"/api/v1/schools/{school_id}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        resp = client.get(f"/api/v1/schools/{school_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404


class TestClasses:
    def _setup_school(self, client, token):
        resp = client.post("/api/v1/schools", json={"name": "班级测试学校"},
                           headers={"Authorization": f"Bearer {token}"})
        return resp.json()["data"]["id"]

    def test_create_class(self, client):
        token = _admin_token(client)
        school_id = self._setup_school(client, token)
        resp = client.post(f"/api/v1/schools/{school_id}/classes", json={
            "school_id": school_id,
            "name": "七年级（1）班",
            "grade": "七年级",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["name"] == "七年级（1）班"
        assert data["grade"] == "七年级"
        assert data["school_id"] == school_id

    def test_list_classes(self, client):
        token = _admin_token(client)
        school_id = self._setup_school(client, token)
        client.post(f"/api/v1/schools/{school_id}/classes", json={
            "school_id": school_id,
            "name": "八年级（2）班", "grade": "八年级",
        }, headers={"Authorization": f"Bearer {token}"})
        resp = client.get(f"/api/v1/schools/{school_id}/classes", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1

    def test_get_class(self, client):
        token = _admin_token(client)
        school_id = self._setup_school(client, token)
        create_resp = client.post(f"/api/v1/schools/{school_id}/classes", json={
            "school_id": school_id,
            "name": "九年级（3）班", "grade": "九年级",
        }, headers={"Authorization": f"Bearer {token}"})
        class_id = create_resp.json()["data"]["id"]
        resp = client.get(f"/api/v1/schools/classes/{class_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "九年级（3）班"

    def test_update_class(self, client):
        token = _admin_token(client)
        school_id = self._setup_school(client, token)
        create_resp = client.post(f"/api/v1/schools/{school_id}/classes", json={
            "school_id": school_id,
            "name": "旧班名", "grade": "七年级",
        }, headers={"Authorization": f"Bearer {token}"})
        class_id = create_resp.json()["data"]["id"]
        resp = client.put(f"/api/v1/schools/classes/{class_id}", json={
            "name": "新班名",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "新班名"

    def test_delete_class(self, client):
        token = _admin_token(client)
        school_id = self._setup_school(client, token)
        create_resp = client.post(f"/api/v1/schools/{school_id}/classes", json={
            "school_id": school_id,
            "name": "待删除班级", "grade": "七年级",
        }, headers={"Authorization": f"Bearer {token}"})
        class_id = create_resp.json()["data"]["id"]
        resp = client.delete(f"/api/v1/schools/classes/{class_id}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        resp = client.get(f"/api/v1/schools/classes/{class_id}", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404
