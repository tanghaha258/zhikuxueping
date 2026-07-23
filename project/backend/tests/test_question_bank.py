"""
题库管理 & 智能组卷 测试
"""
import json
import pytest


@pytest.fixture
def teacher_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "qbteacher", "password": "123456", "email": "qb@test.com",
        "display_name": "题库教师", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={"username": "qbteacher", "password": "123456"})
    return resp.json()["data"]["access_token"]


@pytest.fixture
def other_teacher_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "otherqbteacher", "password": "123456", "email": "other-qb@test.com",
        "display_name": "Other question teacher", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={"username": "otherqbteacher", "password": "123456"})
    return resp.json()["data"]["access_token"]


@pytest.fixture
def sample_question():
    return {
        "subject": "math",
        "grade": "7",
        "question_type": "choice",
        "content": "1+1=?",
        "options": json.dumps([{"label": "A", "content": "1"}, {"label": "B", "content": "2"}, {"label": "C", "content": "3"}, {"label": "D", "content": "4"}]),
        "answer": "B",
        "analysis": "1+1=2",
        "difficulty": 1,
        "score": 5,
        "knowledge_points": '["加法"]',
    }


class TestQuestionCRUD:
    """题目 CRUD"""

    def test_create_question(self, client, teacher_token, sample_question):
        resp = client.post("/api/v1/question-bank/questions", json=sample_question,
                           headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["code"] == 0
        assert data["data"]["content"] == "1+1=?"

    def test_list_questions(self, client, teacher_token, sample_question):
        client.post("/api/v1/question-bank/questions", json=sample_question,
                    headers={"Authorization": f"Bearer {teacher_token}"})
        resp = client.get("/api/v1/question-bank/questions",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total"] >= 1
        assert len(data["items"]) >= 1

    def test_get_question(self, client, teacher_token, sample_question):
        qid = client.post("/api/v1/question-bank/questions", json=sample_question,
                          headers={"Authorization": f"Bearer {teacher_token}"}).json()["data"]["id"]
        resp = client.get(f"/api/v1/question-bank/questions/{qid}",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["id"] == qid

    def test_update_question(self, client, teacher_token, sample_question):
        qid = client.post("/api/v1/question-bank/questions", json=sample_question,
                          headers={"Authorization": f"Bearer {teacher_token}"}).json()["data"]["id"]
        resp = client.put(f"/api/v1/question-bank/questions/{qid}", json={"content": "2+2=?"},
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        assert resp.json()["data"]["content"] == "2+2=?"

    def test_delete_question(self, client, teacher_token, sample_question):
        qid = client.post("/api/v1/question-bank/questions", json=sample_question,
                          headers={"Authorization": f"Bearer {teacher_token}"}).json()["data"]["id"]
        resp = client.delete(f"/api/v1/question-bank/questions/{qid}",
                             headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200

    def test_get_nonexistent_question(self, client, teacher_token):
        resp = client.get("/api/v1/question-bank/questions/nonexistent-id",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        assert resp.json()["code"] != 0


class TestQuestionPermissions:

    def _create_question(self, client, teacher_token, content="owner-only-question"):
        response = client.post("/api/v1/question-bank/questions", json={
            "subject": "math", "grade": "7", "question_type": "choice",
            "content": content, "answer": "A", "difficulty": 3, "score": 5,
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        return response.json()["data"]["id"]

    def test_teacher_cannot_access_another_teachers_question(self, client, teacher_token, other_teacher_token):
        question_id = self._create_question(client, teacher_token)
        headers = {"Authorization": f"Bearer {other_teacher_token}"}

        responses = [
            client.get(f"/api/v1/question-bank/questions/{question_id}", headers=headers),
            client.put(f"/api/v1/question-bank/questions/{question_id}", json={"content": "changed"}, headers=headers),
            client.delete(f"/api/v1/question-bank/questions/{question_id}", headers=headers),
            client.get(f"/api/v1/question-bank/questions/{question_id}/quality", headers=headers),
            client.put(f"/api/v1/question-bank/questions/{question_id}/quality", json={"quality_level": "good"}, headers=headers),
        ]

        assert [response.status_code for response in responses] == [403, 403, 403, 403, 403]

    def test_teacher_list_excludes_another_teachers_questions(self, client, teacher_token, other_teacher_token):
        self._create_question(client, teacher_token, content="owner-only-list-question")

        response = client.get(
            "/api/v1/question-bank/questions",
            headers={"Authorization": f"Bearer {other_teacher_token}"},
        )

        assert all(item["content"] != "owner-only-list-question" for item in response.json()["data"]["items"])

    def test_smart_compose_does_not_use_another_teachers_question(self, client, teacher_token, other_teacher_token):
        self._create_question(client, teacher_token, content="owner-only-compose-question")

        response = client.post("/api/v1/paper-generator/smart-compose", json={
            "subject": "math", "grade": "7", "bank_ratio": 1.0,
            "sections": json.dumps([{"type": "choice", "count": 1, "score_per": 5}]),
            "total_score": 5,
        }, headers={"Authorization": f"Bearer {other_teacher_token}"})

        assert "owner-only-compose-question" not in response.json()["data"]["questions"]


class TestQuestionFilters:
    """题库筛选"""

    def _create(self, client, teacher_token, **kw):
        base = {"subject": "math", "grade": "7", "question_type": "choice",
                "content": "test", "answer": "A", "difficulty": 3, "score": 5}
        base.update(kw)
        return client.post("/api/v1/question-bank/questions", json=base,
                           headers={"Authorization": f"Bearer {teacher_token}"})

    def test_filter_by_subject(self, client, teacher_token):
        self._create(client, teacher_token, subject="math", content="math_q")
        self._create(client, teacher_token, subject="english", content="eng_q")
        resp = client.get("/api/v1/question-bank/questions?subject=math",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(i["subject"] == "math" for i in items)

    def test_filter_by_grade(self, client, teacher_token):
        self._create(client, teacher_token, grade="7", content="g7_q")
        self._create(client, teacher_token, grade="8", content="g8_q")
        resp = client.get("/api/v1/question-bank/questions?grade=8",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(i["grade"] == "8" for i in items)

    def test_filter_by_type(self, client, teacher_token):
        self._create(client, teacher_token, question_type="choice", content="choice_q")
        self._create(client, teacher_token, question_type="fill", content="fill_q")
        resp = client.get("/api/v1/question-bank/questions?question_type=fill",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(i["question_type"] == "fill" for i in items)

    def test_filter_by_difficulty_range(self, client, teacher_token):
        self._create(client, teacher_token, difficulty=1, content="easy_q")
        self._create(client, teacher_token, difficulty=5, content="hard_q")
        resp = client.get("/api/v1/question-bank/questions?difficulty_min=4&difficulty_max=5",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all(i["difficulty"] >= 4 for i in items)

    def test_filter_by_keyword(self, client, teacher_token):
        self._create(client, teacher_token, content="unique_keyword_test")
        self._create(client, teacher_token, content="other")
        resp = client.get("/api/v1/question-bank/questions?keyword=unique_keyword",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert all("unique_keyword" in i["content"] for i in items)

    def test_pagination(self, client, teacher_token):
        for i in range(5):
            self._create(client, teacher_token, content=f"page_q_{i}")
        resp = client.get("/api/v1/question-bank/questions?skip=0&limit=3",
                          headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert len(data["items"]) <= 3
        assert data["total"] >= 5


class TestBatchImport:
    """批量导入题目"""

    def test_batch_import_valid(self, client, teacher_token):
        questions = [
            {"subject": "math", "grade": "7", "question_type": "choice",
             "content": "batch_q1", "answer": "A", "difficulty": 2, "score": 5},
            {"subject": "math", "grade": "7", "question_type": "fill",
             "content": "batch_q2", "answer": "B", "difficulty": 3, "score": 5},
        ]
        resp = client.post("/api/v1/question-bank/batch-import", json={"questions": questions},
                           headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["imported"] == 2
        assert data["failed"] == 0

    def test_batch_import_empty(self, client, teacher_token):
        resp = client.post("/api/v1/question-bank/batch-import", json={"questions": []},
                           headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["imported"] == 0
        assert data["failed"] == 0

    def test_batch_import_with_errors(self, client, teacher_token):
        questions = [
            {"subject": "math", "grade": "7", "question_type": "choice", "content": "ok", "answer": "A"},
            {"subject": "", "grade": "", "question_type": "", "content": "", "answer": ""},
        ]
        resp = client.post("/api/v1/question-bank/batch-import", json={"questions": questions},
                           headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200


class TestSmartCompose:
    """智能组卷"""

    def test_smart_compose(self, client, teacher_token):
        # Create some bank questions first
        for i in range(3):
            client.post("/api/v1/question-bank/questions", json={
                "subject": "math", "grade": "7", "question_type": "choice",
                "content": f"bank_question_{i}", "answer": "A", "difficulty": 3, "score": 5,
            }, headers={"Authorization": f"Bearer {teacher_token}"})

        resp = client.post("/api/v1/paper-generator/smart-compose", json={
            "subject": "math", "grade": "7", "difficulty": "medium",
            "bank_ratio": 0.5, "total_score": 50,
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["status"] == "draft"
        assert data["total_score"] > 0

    def test_smart_compose_full_bank(self, client, teacher_token):
        for i in range(2):
            client.post("/api/v1/question-bank/questions", json={
                "subject": "math", "grade": "7", "question_type": "choice",
                "content": f"bank_q_{i}", "answer": "A", "difficulty": 3, "score": 5,
            }, headers={"Authorization": f"Bearer {teacher_token}"})

        resp = client.post("/api/v1/paper-generator/smart-compose", json={
            "subject": "math", "grade": "7", "difficulty": "medium",
            "bank_ratio": 1.0, "total_score": 50,
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200

    def test_smart_compose_no_bank(self, client, teacher_token):
        resp = client.post("/api/v1/paper-generator/smart-compose", json={
            "subject": "math", "grade": "7", "difficulty": "medium",
            "bank_ratio": 0.0, "total_score": 100,
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200

    def test_smart_compose_requires_auth(self, client):
        resp = client.post("/api/v1/paper-generator/smart-compose", json={
            "subject": "math", "grade": "7",
        })
        assert resp.status_code in (401, 403)

    def test_smart_compose_with_knowledge_points(self, client, teacher_token):
        client.post("/api/v1/question-bank/questions", json={
            "subject": "math", "grade": "7", "question_type": "choice",
            "content": "bank_q_kp", "answer": "A", "difficulty": 3, "score": 5,
            "knowledge_points": '["方程"]',
        }, headers={"Authorization": f"Bearer {teacher_token}"})

        resp = client.post("/api/v1/paper-generator/smart-compose", json={
            "subject": "math", "grade": "7", "difficulty": "medium",
            "knowledge_points": ["方程"], "bank_ratio": 0.5, "total_score": 50,
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200

    def test_smart_compose_rejects_malformed_sections(self, client, teacher_token):
        resp = client.post("/api/v1/paper-generator/smart-compose", json={
            "subject": "math", "grade": "7", "sections": "not-json",
        }, headers={"Authorization": f"Bearer {teacher_token}"})

        assert resp.status_code == 400


class TestAiGenerate:
    """AI 生成题目"""

    def test_ai_generate_no_provider(self, client, teacher_token):
        """Without AI provider configured, should return error."""
        resp = client.post("/api/v1/question-bank/ai-generate", json={
            "subject": "math", "grade": "7", "question_type": "choice", "count": 3,
        }, headers={"Authorization": f"Bearer {teacher_token}"})
        assert resp.status_code == 200
        # Should fail gracefully with error message since no AI provider
        data = resp.json()
        assert data["code"] != 0 or "错误" in data.get("message", "")


class TestUnauthorized:
    """权限测试"""

    def test_unauthorized_access(self, client):
        resp = client.get("/api/v1/question-bank/questions")
        assert resp.status_code in (401, 403)

    def test_create_without_auth(self, client, sample_question):
        resp = client.post("/api/v1/question-bank/questions", json=sample_question)
        assert resp.status_code in (401, 403)
