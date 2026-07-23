from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models.subject import Subject
from app.models.user import Role, User


def _user(db, role: Role) -> User:
    suffix = uuid4().hex
    user = User(
        username=f"subject_auth_{suffix}",
        email=f"subject_auth_{suffix}@example.com",
        display_name=f"Subject Auth {suffix}",
        hashed_password=hash_password("12345678"),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(data={'sub': user.id})}"}


def _subject(db) -> Subject:
    subject = Subject(name=f"Subject {uuid4().hex}", code=f"code-{uuid4().hex}")
    db.add(subject)
    db.commit()
    db.refresh(subject)
    return subject


def test_subject_reads_require_authentication(client, db_session):
    subject = _subject(db_session)
    assert client.get("/api/v1/subjects").status_code == 401
    assert client.get(f"/api/v1/subjects/{subject.id}").status_code == 401


def test_all_authenticated_roles_can_read_subjects(client, db_session):
    subject = _subject(db_session)
    for role in (Role.ADMIN, Role.SCHOOL_ADMIN, Role.TEACHER, Role.STUDENT, Role.PARENT):
        user = _user(db_session, role)
        assert client.get("/api/v1/subjects", headers=_headers(user)).status_code == 200
        assert client.get(f"/api/v1/subjects/{subject.id}", headers=_headers(user)).status_code == 200


def test_non_admin_roles_cannot_mutate_subjects(client, db_session):
    subject = _subject(db_session)
    for role in (Role.SCHOOL_ADMIN, Role.TEACHER, Role.STUDENT, Role.PARENT):
        user = _user(db_session, role)
        headers = _headers(user)
        assert client.post("/api/v1/subjects", json={"name": "Blocked"}, headers=headers).status_code == 403
        assert client.put(f"/api/v1/subjects/{subject.id}", json={"name": "Blocked"}, headers=headers).status_code == 403
        assert client.delete(f"/api/v1/subjects/{subject.id}", headers=headers).status_code == 403
        db_session.expire(subject)
        assert subject.name != "Blocked"


def test_legacy_subject_router_reexports_module_router():
    from app.api.v1 import subjects
    from app.modules.subjects import router

    assert subjects.router is router.router
