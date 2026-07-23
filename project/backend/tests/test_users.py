"""
用户管理 API 测试
"""
import pytest


def _admin_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "admin_user", "password": "admin1234",
        "email": "admin@test.com", "display_name": "管理员", "role": "admin",
    })
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin_user", "password": "admin1234",
    })
    return resp.json()["data"]["access_token"]


class TestListUsers:
    def test_list_users(self, client):
        token = _admin_token(client)
        resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert "items" in data
        assert "total" in data

    def test_list_users_unauthorized(self, client):
        resp = client.get("/api/v1/users")
        assert resp.status_code in (401, 403)


class TestCreateUser:
    def test_create_user_success(self, client):
        token = _admin_token(client)
        resp = client.post("/api/v1/users", json={
            "username": "newteacher",
            "password": "pass1234",
            "email": "newteacher@test.com",
            "display_name": "新老师",
            "role": "teacher",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "newteacher"
        assert data["role"] == "teacher"

    def test_create_user_duplicate(self, client):
        token = _admin_token(client)
        client.post("/api/v1/users", json={
            "username": "dup", "password": "pass1234",
            "email": "dup@test.com", "display_name": "重复", "role": "student",
        }, headers={"Authorization": f"Bearer {token}"})
        resp = client.post("/api/v1/users", json={
            "username": "dup", "password": "pass1234",
            "email": "dup2@test.com", "display_name": "重复", "role": "student",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code in (400, 409)


class TestUpdateUser:
    def test_update_user(self, client):
        token = _admin_token(client)
        create_resp = client.post("/api/v1/users", json={
            "username": "updatable", "password": "pass1234",
            "email": "updatable@test.com", "display_name": "可更新", "role": "teacher",
        }, headers={"Authorization": f"Bearer {token}"})
        user_id = create_resp.json()["data"]["id"]

        resp = client.patch(f"/api/v1/users/{user_id}", json={
            "display_name": "已更新",
            "email": "updated@test.com",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["display_name"] == "已更新"
        assert data["email"] == "updated@test.com"

    def test_toggle_status(self, client):
        token = _admin_token(client)
        create_resp = client.post("/api/v1/users", json={
            "username": "toggler", "password": "pass1234",
            "email": "toggler@test.com", "display_name": "开关用户", "role": "student",
        }, headers={"Authorization": f"Bearer {token}"})
        user_id = create_resp.json()["data"]["id"]

        resp = client.patch(f"/api/v1/users/{user_id}/status",
                            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is False

        resp = client.patch(f"/api/v1/users/{user_id}/status",
                            headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is True


class TestSearchUsers:
    def test_search_by_keyword(self, client):
        token = _admin_token(client)
        client.post("/api/v1/users", json={
            "username": "searchable1", "password": "pass1234",
            "email": "s1@test.com", "display_name": "张三", "role": "teacher",
        }, headers={"Authorization": f"Bearer {token}"})
        client.post("/api/v1/users", json={
            "username": "searchable2", "password": "pass1234",
            "email": "s2@test.com", "display_name": "李四", "role": "student",
        }, headers={"Authorization": f"Bearer {token}"})

        resp = client.get("/api/v1/users?keyword=张三",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        assert any(u["display_name"] == "张三" for u in data["items"])

    def test_filter_by_role(self, client):
        token = _admin_token(client)
        resp = client.get("/api/v1/users?role=admin",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        for u in data["items"]:
            assert u["role"] == "admin"

    def test_filter_by_status(self, client):
        token = _admin_token(client)
        resp = client.get("/api/v1/users?is_active=false",
                          headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        for u in data["items"]:
            assert u["is_active"] is False
