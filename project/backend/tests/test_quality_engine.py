"""
题库质量引擎 & 学情分析 & 批改反馈 测试
"""
import json
import pytest


@pytest.fixture
def teacher_token(client):
    client.post("/api/v1/auth/register", json={
        "username": "qcteacher", "password": "123456", "email": "qc@test.com",
        "display_name": "质量测试教师", "role": "teacher",
    })
    resp = client.post("/api/v1/auth/login", json={"username": "qcteacher", "password": "123456"})
    return resp.json()["data"]["access_token"]


@pytest.fixture
def auth_headers(teacher_token):
    return {"Authorization": f"Bearer {teacher_token}"}


@pytest.fixture
def sample_question():
    return {
        "subject": "math", "grade": "7", "question_type": "choice",
        "content": "质量测试题 2+3=?", "answer": "B", "difficulty": 3, "score": 5,
        "knowledge_points": '["加法"]',
    }


class TestQuestionQuality:
    """题库质量统计"""

    def test_quality_stats_empty(self, client, auth_headers):
        resp = client.get("/api/v1/question-bank/quality/stats", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "total_questions" in data
        assert "quality_distribution" in data
        assert "avg_difficulty" in data

    def test_quality_stats_with_subject(self, client, auth_headers, sample_question):
        client.post("/api/v1/question-bank/questions", json=sample_question, headers=auth_headers)
        resp = client.get("/api/v1/question-bank/quality/stats?subject=math", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_questions"] >= 1

    def test_question_quality_detail(self, client, auth_headers, sample_question):
        create_resp = client.post("/api/v1/question-bank/questions", json=sample_question, headers=auth_headers)
        qid = create_resp.json()["data"]["id"]
        resp = client.get(f"/api/v1/question-bank/questions/{qid}/quality", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "quality_score" in data
        assert "quality_level" in data
        assert "usage_count" in data

    def test_question_quality_not_found(self, client, auth_headers):
        resp = client.get("/api/v1/question-bank/questions/nonexistent/quality", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["code"] != 0

    def test_update_question_quality(self, client, auth_headers, sample_question):
        create_resp = client.post("/api/v1/question-bank/questions", json=sample_question, headers=auth_headers)
        qid = create_resp.json()["data"]["id"]
        resp = client.put(f"/api/v1/question-bank/questions/{qid}/quality",
                          json={"quality_score": 85, "quality_level": "excellent"},
                          headers=auth_headers)
        assert resp.status_code == 200


class TestLearningProfile:
    """学情分析"""

    def test_class_profile_empty(self, client, auth_headers):
        resp = client.get("/api/v1/learning-profile/classes/nonexistent?subject=math", headers=auth_headers)
        assert resp.status_code == 404

    def test_generate_report(self, client, auth_headers):
        resp = client.post("/api/v1/learning-profile/classes/nonexistent/report?subject=math", headers=auth_headers)
        assert resp.status_code == 404

    def test_list_reports(self, client, auth_headers):
        resp = client.get("/api/v1/learning-profile/classes/nonexistent/reports?subject=math", headers=auth_headers)
        assert resp.status_code == 404


class TestPaperFeedback:
    """批改反馈回流"""

    def test_generate_smart_placeholder(self, client, auth_headers):
        resp = client.post("/api/v1/papers/generate-smart", headers=auth_headers, json={})
        assert resp.status_code == 200
        assert resp.json()["code"] == 0

    def test_process_feedback_not_found(self, client, auth_headers):
        resp = client.post("/api/v1/papers/nonexistent/process-feedback", headers=auth_headers)
        assert resp.status_code == 404
