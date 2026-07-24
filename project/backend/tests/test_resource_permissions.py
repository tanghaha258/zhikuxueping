import uuid


def _register(client, username: str) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": username,
            "password": "12345678",
            "email": f"{username}@test.com",
            "display_name": username,
            "role": "teacher",
        },
    )
    assert response.status_code == 200


def _login(client, username: str) -> str:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "12345678"},
    )
    return response.json()["data"]["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_resource_in_project(client):
    suffix = uuid.uuid4().hex[:8]
    owner_name = f"resource_owner_{suffix}"
    other_name = f"resource_other_{suffix}"
    _register(client, owner_name)
    _register(client, other_name)
    owner_token = _login(client, owner_name)
    other_token = _login(client, other_name)
    project_response = client.post(
        "/api/v1/projects",
        json={"title": "Protected resource project"},
        headers=_headers(owner_token),
    )
    project_id = project_response.json()["data"]["id"]
    resource_response = client.post(
        "/api/v1/resources",
        json={
            "project_id": project_id,
            "title": "Protected resource",
            "res_type": "link",
            "url": "https://example.com/private",
        },
        headers=_headers(owner_token),
    )
    return project_id, resource_response.json()["data"]["id"], other_token


def test_resource_endpoints_require_authentication(client):
    project_id, resource_id, _ = _create_resource_in_project(client)

    list_response = client.get(f"/api/v1/resources?project_id={project_id}")
    detail_response = client.get(f"/api/v1/resources/{resource_id}")

    assert list_response.status_code == 401
    assert detail_response.status_code == 401


def test_teacher_cannot_access_another_teachers_project_resource(client):
    project_id, resource_id, other_token = _create_resource_in_project(client)
    headers = _headers(other_token)

    responses = [
        client.get(f"/api/v1/resources?project_id={project_id}", headers=headers),
        client.get(f"/api/v1/resources/{resource_id}", headers=headers),
        client.put(f"/api/v1/resources/{resource_id}", json={"title": "changed"}, headers=headers),
        client.delete(f"/api/v1/resources/{resource_id}", headers=headers),
    ]

    assert [response.status_code for response in responses] == [403, 403, 403, 403]


# ============================================================
# Task 8：资源上下文链接权限
# - 跨校教师/管理员不能将独立资源关联到他人项目（403）
# - 同校管理员可以关联
# - 取消关联只删引用，资源资产本体（标题/URL/文件大小）保留
# - 取消关联后 Resource.project_id 解耦，资源回到独立状态
# - 跨校取消关联被拒绝（403）
# ============================================================
import uuid

from sqlalchemy import select


def _register_with_school(client, username: str, role: str = "teacher", school_id: str | None = None):
    payload = {
        "username": username,
        "password": "12345678",
        "email": f"{username}@test.com",
        "display_name": username,
        "role": role,
    }
    if school_id:
        payload["school_id"] = school_id
    resp = client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _login_user(client, username: str) -> str:
    resp = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "12345678"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["access_token"]


def _auth_h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_two_schools(client):
    """建立两所学校与系统管理员，返回 (sys_token, school_a_id, school_b_id)。"""
    tag = uuid.uuid4().hex[:8]
    _register_with_school(client, f"sysadmin_{tag}", "admin")
    sys_token = _login_user(client, f"sysadmin_{tag}")
    school_a = client.post(
        "/api/v1/schools", json={"name": f"A校 {tag}"}, headers=_auth_h(sys_token)
    ).json()["data"]
    school_b = client.post(
        "/api/v1/schools", json={"name": f"B校 {tag}"}, headers=_auth_h(sys_token)
    ).json()["data"]
    return sys_token, school_a["id"], school_b["id"], tag


def _create_project_api(client, token: str, title: str) -> str:
    resp = client.post("/api/v1/projects", json={"title": title}, headers=_auth_h(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _create_independent_resource(client, token: str, title: str = "独立资源") -> str:
    resp = client.post(
        "/api/v1/resources",
        json={
            "title": title,
            "res_type": "link",
            "url": "https://example.com/independent",
        },
        headers=_auth_h(token),
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]["id"]


def _link_context(client, token: str, *, artifact_id: str, project_id: str, placement: str = "resource"):
    return client.post(
        "/api/v1/resources/context-links",
        json={
            "artifact_type": "resource",
            "artifact_id": artifact_id,
            "project_id": project_id,
            "placement": placement,
        },
        headers=_auth_h(token),
    )


class TestResourceContextLinkCrossSchool:
    """资源跨校关联必须拒绝；同校管理员可关联。"""

    def test_cross_school_teacher_cannot_link_resource(self, client):
        _, school_a, school_b, tag = _create_two_schools(client)
        _register_with_school(client, f"ta_{tag}", "teacher", school_id=school_a)
        _register_with_school(client, f"tb_{tag}", "teacher", school_id=school_b)
        ta_token = _login_user(client, f"ta_{tag}")
        tb_token = _login_user(client, f"tb_{tag}")

        project_id = _create_project_api(client, ta_token, f"A校项目 {tag}")
        tb_resource = _create_independent_resource(client, tb_token)

        resp = _link_context(
            client, tb_token, artifact_id=tb_resource, project_id=project_id
        )
        assert resp.status_code == 403

    def test_cross_school_admin_cannot_link(self, client):
        _, school_a, school_b, tag = _create_two_schools(client)
        _register_with_school(client, f"ta_{tag}", "teacher", school_id=school_a)
        _register_with_school(client, f"sb_{tag}", "school_admin", school_id=school_b)
        ta_token = _login_user(client, f"ta_{tag}")
        sb_token = _login_user(client, f"sb_{tag}")

        project_id = _create_project_api(client, ta_token, f"A校项目 {tag}")
        # B 校管理员用任意资产 id 试图关联到 A 校项目
        resp = _link_context(
            client, sb_token, artifact_id="any-asset-id", project_id=project_id
        )
        assert resp.status_code == 403

    def test_same_school_admin_can_link_resource(self, client):
        _, school_a, _, tag = _create_two_schools(client)
        _register_with_school(client, f"t_{tag}", "teacher", school_id=school_a)
        _register_with_school(client, f"sa_{tag}", "school_admin", school_id=school_a)
        t_token = _login_user(client, f"t_{tag}")
        sa_token = _login_user(client, f"sa_{tag}")

        project_id = _create_project_api(client, t_token, f"同校项目 {tag}")
        resource_id = _create_independent_resource(client, t_token)

        resp = _link_context(
            client, sa_token, artifact_id=resource_id, project_id=project_id
        )
        assert resp.status_code == 200, resp.text


class TestResourceUnlinkPreservesAsset:
    """取消关联只删引用，资源资产本体与文件保留；project_id 解耦。"""

    def test_unlink_keeps_resource_asset_and_url(self, client, db_session):
        from app.models.resource import Resource
        from app.models.tool_context import ToolContextLink

        tag = uuid.uuid4().hex[:8]
        _register_with_school(client, f"t_{tag}", "teacher")
        token = _login_user(client, f"t_{tag}")
        project_id = _create_project_api(client, token, f"项目 {tag}")
        # 带项目创建资源，触发自动建立默认引用
        resp = client.post(
            "/api/v1/resources",
            json={
                "project_id": project_id,
                "title": "保留资产测试",
                "res_type": "link",
                "url": "https://example.com/keep",
            },
            headers=_auth_h(token),
        )
        assert resp.status_code == 200, resp.text
        resource_id = resp.json()["data"]["id"]

        links = list(
            db_session.execute(
                select(ToolContextLink).where(ToolContextLink.artifact_id == resource_id)
            ).scalars().all()
        )
        assert len(links) == 1
        link_id = links[0].id

        unlink_resp = client.delete(
            f"/api/v1/resources/context-links/{link_id}", headers=_auth_h(token)
        )
        assert unlink_resp.status_code == 200, unlink_resp.text
        body = unlink_resp.json()["data"]
        assert body["preserved"] is True
        assert body["artifact_type"] == "resource"
        assert body["artifact_id"] == resource_id

        # 引用已删除
        assert db_session.get(ToolContextLink, link_id) is None

        # 资产仍存在，关键字段保留
        resource = db_session.get(Resource, resource_id)
        assert resource is not None
        assert resource.title == "保留资产测试"
        assert resource.url == "https://example.com/keep"
        # project_id 被解耦，回到独立状态
        assert resource.project_id is None

    def test_unlink_cross_school_rejected(self, client):
        from app.models.tool_context import ToolContextLink

        _, school_a, school_b, tag = _create_two_schools(client)
        _register_with_school(client, f"ta_{tag}", "teacher", school_id=school_a)
        _register_with_school(client, f"tb_{tag}", "teacher", school_id=school_b)
        ta_token = _login_user(client, f"ta_{tag}")
        tb_token = _login_user(client, f"tb_{tag}")

        project_id = _create_project_api(client, ta_token, f"A校项目 {tag}")
        ta_resource = _create_independent_resource(client, ta_token)
        link_resp = _link_context(
            client, ta_token, artifact_id=ta_resource, project_id=project_id
        )
        assert link_resp.status_code == 200, link_resp.text
        link_id = link_resp.json()["data"]["id"]

        # B 校教师试图解关联 A 校项目的引用
        resp = client.delete(
            f"/api/v1/resources/context-links/{link_id}", headers=_auth_h(tb_token)
        )
        assert resp.status_code == 403

    def test_unlink_nonexistent_link_returns_404(self, client):
        tag = uuid.uuid4().hex[:8]
        _register_with_school(client, f"t_{tag}", "teacher")
        token = _login_user(client, f"t_{tag}")

        resp = client.delete(
            "/api/v1/resources/context-links/nonexistent-id",
            headers=_auth_h(token),
        )
        assert resp.status_code == 404
