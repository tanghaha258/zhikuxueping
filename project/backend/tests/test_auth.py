"""
Auth API 测试
"""
import pytest


class TestRegister:
    def test_register_success(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "testuser",
            "password": "test1234",
            "email": "test@example.com",
            "display_name": "测试用户",
            "role": "teacher",
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["username"] == "testuser"
        assert data["display_name"] == "测试用户"
        assert data["role"] == "teacher"
        assert data["is_active"] is True

    def test_register_duplicate_username(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "dupuser", "password": "test1234",
            "email": "dup@example.com", "display_name": "重复用户", "role": "teacher",
        })
        resp = client.post("/api/v1/auth/register", json={
            "username": "dupuser", "password": "test1234",
            "email": "dup2@example.com", "display_name": "重复用户", "role": "teacher",
        })
        assert resp.status_code in (400, 409)

    def test_register_short_password(self, client):
        resp = client.post("/api/v1/auth/register", json={
            "username": "shortpwd", "password": "123",
            "email": "short@example.com", "display_name": "短密码", "role": "teacher",
        })
        assert resp.status_code == 422


class TestLogin:
    LOGIN_DATA = {"username": "loginuser", "password": "login1234"}

    def setup_user(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "loginuser", "password": "login1234",
            "email": "login@example.com", "display_name": "登录用户", "role": "admin",
        })

    def test_login_success(self, client):
        self.setup_user(client)
        resp = client.post("/api/v1/auth/login", json=self.LOGIN_DATA)
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["username"] == "loginuser"

    def test_login_wrong_password(self, client):
        self.setup_user(client)
        resp = client.post("/api/v1/auth/login", json={
            "username": "loginuser", "password": "wrongpwd",
        })
        assert resp.status_code == 401


class TestMe:
    def _register_and_login(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "meuser", "password": "me123456",
            "email": "me@example.com", "display_name": "Me用户", "role": "teacher",
        })
        resp = client.post("/api/v1/auth/login", json={
            "username": "meuser", "password": "me123456",
        })
        return resp.json()["data"]["access_token"]

    def test_get_me(self, client):
        token = self._register_and_login(client)
        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["username"] == "meuser"
        assert data["role"] == "teacher"

    def test_get_me_unauthorized(self, client):
        resp = client.get("/api/v1/auth/me")
        assert resp.status_code in (401, 403)

    def test_get_me_invalid_token(self, client):
        resp = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
        assert resp.status_code == 401

    def test_refresh_token_cannot_access_protected_route(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "refreshonlyuser",
            "password": "refresh1234",
            "email": "refreshonly@example.com",
            "display_name": "Refresh Only",
            "role": "teacher",
        })
        login = client.post("/api/v1/auth/login", json={
            "username": "refreshonlyuser",
            "password": "refresh1234",
        })
        refresh_token = login.json()["data"]["refresh_token"]

        resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})

        assert resp.status_code == 401


class TestRefresh:
    def _register_and_login(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "refreshuser", "password": "rf123456",
            "email": "rf@example.com", "display_name": "刷新用户", "role": "teacher",
        })
        resp = client.post("/api/v1/auth/login", json={
            "username": "refreshuser", "password": "rf123456",
        })
        return resp.json()["data"]

    def test_refresh_success(self, client):
        data = self._register_and_login(client)
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": data["refresh_token"],
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "access_token" in body["data"]

    def test_refresh_invalid(self, client):
        resp = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid_token_here",
        })
        assert resp.status_code == 401


class TestProfile:
    def _setup(self, client):
        client.post("/api/v1/auth/register", json={
            "username": "profileuser", "password": "pf123456",
            "email": "pf@example.com", "display_name": "资料用户", "role": "teacher",
        })
        resp = client.post("/api/v1/auth/login", json={
            "username": "profileuser", "password": "pf123456",
        })
        return resp.json()["data"]["access_token"]

    def test_update_profile(self, client):
        token = self._setup(client)
        resp = client.put("/api/v1/auth/me", json={
            "display_name": "新名字",
            "email": "new@example.com",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["display_name"] == "新名字"
        assert data["email"] == "new@example.com"

    def test_change_password(self, client):
        token = self._setup(client)
        resp = client.put("/api/v1/auth/me/password", json={
            "old_password": "pf123456",
            "new_password": "newpwd789",
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

        # verify can login with new password
        resp = client.post("/api/v1/auth/login", json={
            "username": "profileuser", "password": "newpwd789",
        })
        assert resp.status_code == 200
