import json
import pytest


@pytest.fixture
def teacher_token(client):
    """Create a teacher user and return token."""
    client.post("/api/v1/auth/register", json={
        "username": "testteacher", "password": "123456", "email": "tt@test.com",
        "display_name": "测试教师", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={"username": "testteacher", "password": "123456"})
    return resp.json()["data"]["access_token"]


@pytest.fixture
def admin_token(client):
    """Create an admin user and return token."""
    client.post("/api/v1/auth/register", json={
        "username": "testadmin", "password": "123456", "email": "ta@test.com",
        "display_name": "测试管理员", "role": "admin",
    })
    resp = client.post("/api/v1/auth/login", json={"username": "testadmin", "password": "123456"})
    return resp.json()["data"]["access_token"]


@pytest.fixture
def other_teacher_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "otherpaperteacher", "password": "123456", "email": "other-paper@test.com",
        "display_name": "Other paper teacher", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={"username": "otherpaperteacher", "password": "123456"})
    return resp.json()["data"]["access_token"]


@pytest.fixture
def student_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "paperstudent", "password": "123456", "email": "paper-student@test.com",
        "display_name": "Paper student", "role": "student",
    })
    resp = client.post("/api/v1/auth/login", json={"username": "paperstudent", "password": "123456"})
    return resp.json()["data"]["access_token"]


class TestPaperTemplates:
    """模板 CRUD"""

    def test_create_template(self, client, admin_token):
        resp = client.post(
            "/api/v1/paper-generator/templates",
            json={"name": "周测", "subject": "数学", "grade": "7"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0
        assert resp.json()["data"]["name"] == "周测"

    def test_list_templates(self, client, admin_token):
        resp = client.get("/api/v1/paper-generator/templates", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert len(resp.json()["data"]["items"]) >= 1

    def test_get_template(self, client, admin_token):
        tid = client.post("/api/v1/paper-generator/templates",
                          json={"name": "X", "subject": "数学", "grade": "7"},
                          headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]["id"]
        resp = client.get(f"/api/v1/paper-generator/templates/{tid}", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == tid

    def test_update_template(self, client, admin_token):
        tid = client.post("/api/v1/paper-generator/templates",
                          json={"name": "X", "subject": "数学", "grade": "7"},
                          headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]["id"]
        resp = client.put(f"/api/v1/paper-generator/templates/{tid}", json={"name": "月考"},
                          headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "月考"

    def test_delete_template(self, client, admin_token):
        tid = client.post("/api/v1/paper-generator/templates",
                          json={"name": "X", "subject": "数学", "grade": "7"},
                          headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]["id"]
        resp = client.delete(f"/api/v1/paper-generator/templates/{tid}", headers={"Authorization": f"Bearer {admin_token}"})
        assert resp.status_code == 200

    def test_teacher_cannot_create_template(self, client, teacher_token):
        resp = client.post("/api/v1/paper-generator/templates",
                           json={"name": "测试", "subject": "数学", "grade": "7"},
                           headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 403


class TestPaperGenerator:
    """AI 出卷"""

    def _generate(self, client, teacher_token, **kw):
        default = {"subject": "数学", "grade": "7", "difficulty": "medium"}
        default.update(kw)
        return client.post("/api/v1/paper-generator/generate", json=default,
                           headers={"Authorization": f"Bearer {teacher_token}"})

    def test_generate_paper(self, client, teacher_token):
        resp = self._generate(client, teacher_token)
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "draft"
        assert resp.json()["data"]["total_score"] > 0

    def test_generate_with_knowledge_points(self, client, teacher_token):
        resp = self._generate(client, teacher_token, difficulty="hard",
                              knowledge_points=["一元一次方程", "几何图形"])
        assert resp.status_code == 200
        assert resp.json()["data"]["difficulty"] == "hard"

    def test_generate_with_template(self, client, teacher_token, admin_token):
        tid = client.post("/api/v1/paper-generator/templates",
                          json={"name": "期中", "subject": "英语", "grade": "8"},
                          headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]["id"]
        resp = self._generate(client, teacher_token, subject="英语", grade="8", template_id=tid)
        assert resp.status_code == 200
        assert resp.json()["data"]["template_id"] == tid

    def test_list_generated_papers(self, client, teacher_token):
        resp = client.get("/api/v1/paper-generator/papers", headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200

    def test_get_generated_paper(self, client, teacher_token):
        pid = self._generate(client, teacher_token).json()["data"]["id"]
        resp = client.get(f"/api/v1/paper-generator/papers/{pid}", headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == pid

    def test_update_generated_paper(self, client, teacher_token):
        pid = self._generate(client, teacher_token).json()["data"]["id"]
        resp = client.put(f"/api/v1/paper-generator/papers/{pid}", json={"title": "修改后的标题"},
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["title"] == "修改后的标题"

    def test_finalize_paper(self, client, teacher_token):
        pid = self._generate(client, teacher_token).json()["data"]["id"]
        resp = client.post(f"/api/v1/paper-generator/papers/{pid}/finalize",
                           headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["status"] == "finalized"

    def test_export_paper_html(self, client, teacher_token):
        pid = self._generate(client, teacher_token).json()["data"]["id"]
        resp = client.post(f"/api/v1/paper-generator/papers/{pid}/export", params={"format": "html"},
                           headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200

    def test_delete_generated_paper(self, client, teacher_token):
        pid = self._generate(client, teacher_token).json()["data"]["id"]
        resp = client.delete(f"/api/v1/paper-generator/papers/{pid}",
                             headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200

    def test_generate_with_sections(self, client, teacher_token):
        sections = json.dumps([
            {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 3, "score_per": 5, "total": 15},
            {"id": "sec_2", "label": "二、填空题", "type": "fill", "count": 2, "score_per": 5, "total": 10},
        ])
        resp = client.post("/api/v1/paper-generator/generate", json={
            "subject": "数学", "grade": "7", "difficulty": "medium",
            "sections": sections, "exam_type": "quiz",
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_score"] == 25

    def test_generate_with_default_sections(self, client, teacher_token):
        resp = client.post("/api/v1/paper-generator/generate", json={
            "subject": "数学", "grade": "7", "exam_type": "final",
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_score"] == 100

    def test_generate_response_has_warning_field(self, client, teacher_token):
        resp = client.post("/api/v1/paper-generator/generate", json={
            "subject": "数学", "grade": "7",
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "warning" in data

    def test_generate_with_template_sections(self, client, teacher_token, admin_token):
        sections = json.dumps([
            {"id": "sec_1", "label": "一、选择题", "type": "choice", "count": 5, "score_per": 4, "total": 20},
            {"id": "sec_2", "label": "二、简答题", "type": "essay", "count": 3, "score_per": 10, "total": 30},
        ])
        tid = client.post("/api/v1/paper-generator/templates",
            json={"name": "小测", "subject": "数学", "grade": "7", "total_score": 50, "sections": sections},
            headers={"Authorization": f"Bearer {admin_token}"}).json()["data"]["id"]
        resp = client.post("/api/v1/paper-generator/generate", json={
            "subject": "数学", "grade": "7", "template_id": tid,
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_score"] == 50

    def test_unauthorized_cannot_generate(self, client):
        resp = client.post("/api/v1/paper-generator/generate",
                           json={"subject": "数学", "grade": "7"},
                           headers={"Authorization": "Bearer invalid_token"})
        assert resp.status_code in (401, 403)


@pytest.fixture
def sample_paper(client, teacher_token):
    """Create a sample generated paper and return its id."""
    resp = client.post("/api/v1/paper-generator/generate", json={
        "subject": "数学", "grade": "7", "difficulty": "medium",
    }, headers={"Authorization": f"Bearer {teacher_token}"})
    return resp.json()["data"]["id"]


class TestFormatAPI:

    def test_format_paper(self, client, teacher_token, sample_paper):
        resp = client.post(
            f"/api/v1/paper-generator/papers/{sample_paper}/format",
            json={"template_type": "midterm", "subject": "math"},
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["template_type"] == "midterm"

    def test_get_formatted_paper(self, client, teacher_token, sample_paper):
        client.post(
            f"/api/v1/paper-generator/papers/{sample_paper}/format",
            json={"template_type": "quiz", "subject": "math"},
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        resp = client.get(f"/api/v1/paper-generator/papers/{sample_paper}/formatted", headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0

    def test_update_formatted_paper(self, client, teacher_token, sample_paper):
        client.post(
            f"/api/v1/paper-generator/papers/{sample_paper}/format",
            json={"template_type": "midterm", "subject": "math"},
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        resp = client.put(
            f"/api/v1/paper-generator/papers/{sample_paper}/formatted",
            json={"formatted_html": "<html><body>edited</body></html>"},
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["code"] == 0


class TestStreamAPI:

    def test_generate_stream_endpoint(self, client, teacher_token):
        resp = client.post(
            "/api/v1/paper-generator/generate-stream",
            json={"subject": "math", "grade": "7", "difficulty": "easy"},
            headers={"Authorization": f"Bearer {teacher_token}"},
        )
        assert resp.status_code == 200
        assert resp.headers.get("content-type", "").startswith("text/event-stream")


class TestStreamAuthorization:

    def test_student_cannot_generate_streamed_paper(self, client, student_token):
        response = client.post(
            "/api/v1/paper-generator/generate-stream",
            json={"subject": "math", "grade": "7", "difficulty": "easy"},
            headers={"Authorization": f"Bearer {student_token}"},
        )

        assert response.status_code == 403


class TestGeneratedPaperOwnership:

    def _create_paper(self, client, teacher_token):
        response = client.post("/api/v1/paper-generator/generate", json={
            "subject": "math", "grade": "7", "difficulty": "medium",
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        return response.json()["data"]["id"]

    def test_other_teacher_cannot_read_generated_paper(self, client, teacher_token, other_teacher_token):
        paper_id = self._create_paper(client, teacher_token)

        response = client.get(
            f"/api/v1/paper-generator/papers/{paper_id}",
            headers={"Authorization": f"Bearer {other_teacher_token}"},
        )

        assert response.status_code == 403

    def test_other_teacher_cannot_manage_generated_paper(self, client, teacher_token, other_teacher_token):
        paper_id = self._create_paper(client, teacher_token)
        headers = {"Authorization": f"Bearer {other_teacher_token}"}

        responses = [
            client.put(f"/api/v1/paper-generator/papers/{paper_id}", json={"title": "changed"}, headers=headers),
            client.post(f"/api/v1/paper-generator/papers/{paper_id}/finalize", headers=headers),
            client.post(f"/api/v1/paper-generator/papers/{paper_id}/export", params={"format": "html"}, headers=headers),
            client.post(f"/api/v1/paper-generator/papers/{paper_id}/format", json={"template_type": "quiz", "subject": "math"}, headers=headers),
            client.put(f"/api/v1/paper-generator/papers/{paper_id}/formatted", json={"formatted_html": "<p>changed</p>"}, headers=headers),
            client.delete(f"/api/v1/paper-generator/papers/{paper_id}", headers=headers),
        ]

        assert [response.status_code for response in responses] == [403, 403, 403, 403, 403, 403]


class TestPaperRenderer:
    """试卷排版引擎测试"""

    def test_render_basic(self):
        from app.services.paper_template_renderer import render_exam_paper
        questions = [
            {"type": "choice", "content": "1+1=?", "options": [{"label": "A", "content": "1"}, {"label": "B", "content": "2"}], "score": 5},
            {"type": "fill", "content": "中国的首都是____", "score": 4},
            {"type": "essay", "content": "论述题：解释光合作用。", "score": 10},
        ]
        html = render_exam_paper("测试试卷", questions, 100, 90, "midterm", "math")
        assert "<!DOCTYPE html>" in html
        assert "绝密" in html
        assert "1+1=?" in html
        assert "选择题" in html
        assert "katex" in html

    def test_render_quiz_a4(self):
        from app.services.paper_template_renderer import render_exam_paper
        html = render_exam_paper("周测", [{"type": "choice", "content": "测试", "score": 3}], 30, 45, "quiz", "math")
        assert "A4" in html or "@page" in html

    def test_render_chinese_essay_grid(self):
        from app.services.paper_template_renderer import render_exam_paper
        questions = [{"type": "writing", "content": "作文题", "score": 30}]
        html = render_exam_paper("语文试卷", questions, 30, 90, "final", "chinese")
        assert "essay-grid" in html

    def test_render_empty_questions(self):
        from app.services.paper_template_renderer import render_exam_paper
        html = render_exam_paper("空卷", [], 100, 90, "midterm", "math")
        assert "暂无题目" in html
