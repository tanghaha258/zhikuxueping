from pathlib import Path

from app.core.config import Settings, settings


def test_relative_sqlite_url_resolves_from_backend_root():
    configured = Settings(DATABASE_URL="sqlite:///./data/platform.db", _env_file=None)
    backend_root = Path(__file__).resolve().parents[1]

    assert configured.DATABASE_URL == f"sqlite:///{(backend_root / 'data' / 'platform.db').as_posix()}"


def test_uploaded_file_requires_login(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    (tmp_path / "private.txt").write_text("private", encoding="utf-8")

    response = client.get("/api/v1/upload/files/private.txt")

    assert response.status_code == 401


def test_logged_in_browser_can_download_uploaded_file(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    (tmp_path / "private.txt").write_text("private", encoding="utf-8")

    client.post("/api/v1/auth/register", json={
        "username": "media_user",
        "password": "test1234",
        "email": "media_user@example.com",
        "display_name": "Media User",
        "role": "teacher",
    })
    login = client.post("/api/v1/auth/login", json={"username": "media_user", "password": "test1234"})

    assert login.cookies.get(settings.MEDIA_SESSION_COOKIE)
    response = client.get("/api/v1/upload/files/private.txt")
    assert response.status_code == 200
    assert response.content == b"private"


def test_uploaded_file_path_cannot_escape_upload_directory(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    client.post("/api/v1/auth/register", json={
        "username": "traversal_user",
        "password": "test1234",
        "email": "traversal_user@example.com",
        "display_name": "Traversal User",
        "role": "teacher",
    })
    login = client.post("/api/v1/auth/login", json={"username": "traversal_user", "password": "test1234"})
    token = login.json()["data"]["access_token"]

    response = client.get(
        "/api/v1/upload/files/..%2Foutside.txt",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404
