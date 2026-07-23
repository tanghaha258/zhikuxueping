from uuid import uuid4


def _setup(client):
    suffix = uuid4().hex
    client.post("/api/v1/auth/register", json={
        "username": f"tc_admin_{suffix}", "password": "12345678",
        "email": f"tc_admin_{suffix}@test.com", "display_name": "TCAdmin", "role": "admin",
    })
    token = client.post("/api/v1/auth/login", json={"username": f"tc_admin_{suffix}", "password": "12345678"}).json()["data"]["access_token"]

    school = client.post("/api/v1/schools", json={"name": "TC School"},
                         headers={"Authorization": f"Bearer {token}"}).json()["data"]
    cls = client.post(f"/api/v1/schools/{school['id']}/classes", json={
        "school_id": school["id"], "grade": "七年级", "name": "1班",
    }, headers={"Authorization": f"Bearer {token}"}).json()["data"]

    client.post("/api/v1/auth/register", json={
        "username": f"tc_teacher_{suffix}", "password": "12345678",
        "email": f"tc_teacher_{suffix}@test.com", "display_name": "TCTeacher", "role": "teacher",
        "school_id": school["id"],
    })
    login_resp = client.post("/api/v1/auth/login", json={"username": f"tc_teacher_{suffix}", "password": "12345678"}).json()["data"]
    return token, login_resp["user"]["id"], cls["id"]


class TestTeacherClass:
    def test_bind(self, client):
        token, tid, cid = _setup(client)
        resp = client.post("/api/v1/schools/teacher-classes", json={
            "teacher_id": tid, "class_id": cid,
        }, headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200

    def test_list_teacher_classes(self, client):
        token, tid, cid = _setup(client)
        client.post("/api/v1/schools/teacher-classes", json={
            "teacher_id": tid, "class_id": cid,
        }, headers={"Authorization": f"Bearer {token}"})
        resp = client.get(f"/api/v1/schools/teachers/{tid}/classes", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data) >= 1

    def test_unbind(self, client):
        token, tid, cid = _setup(client)
        client.post("/api/v1/schools/teacher-classes", json={
            "teacher_id": tid, "class_id": cid,
        }, headers={"Authorization": f"Bearer {token}"})
        resp = client.delete(f"/api/v1/schools/teacher-classes?teacher_id={tid}&class_id={cid}",
                             headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
