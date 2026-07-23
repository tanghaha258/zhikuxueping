from uuid import uuid4

from app.core.config import settings
from app.core.security import create_access_token, hash_password
from app.models.school import Class, School
from app.models.user import Role, User


def _create_user(db, *, role: Role, school_id: str | None = None, class_id: str | None = None) -> User:
    suffix = uuid4().hex
    user = User(
        username=f"identity_{suffix}",
        email=f"identity_{suffix}@example.com",
        display_name=f"Identity {suffix}",
        hashed_password=hash_password("12345678"),
        role=role,
        school_id=school_id,
        class_id=class_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _headers(user: User) -> dict[str, str]:
    token = create_access_token(data={"sub": user.id})
    return {"Authorization": f"Bearer {token}"}


def _school(db, label: str) -> School:
    school = School(name=f"Identity School {label}")
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def _class(db, school: School, label: str) -> Class:
    cls = Class(school_id=school.id, grade="七年级", name=f"Identity Class {label}")
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return cls


def test_production_registration_rejects_privileged_payload(client, db_session, monkeypatch):
    monkeypatch.setattr(settings, "TESTING", False)
    before = db_session.query(User).count()

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"public_admin_{uuid4().hex}",
            "password": "12345678",
            "email": f"public_admin_{uuid4().hex}@example.com",
            "display_name": "Public Admin",
            "role": "admin",
        },
    )

    assert response.status_code == 403
    assert db_session.query(User).count() == before


def test_test_registration_persists_requested_school_id(client, db_session, monkeypatch):
    assert hasattr(settings, "TESTING")
    monkeypatch.setattr(settings, "TESTING", True)
    school_id = f"registration-school-{uuid4().hex}"
    suffix = uuid4().hex

    response = client.post(
        "/api/v1/auth/register",
        json={
            "username": f"registered_{suffix}",
            "password": "12345678",
            "email": f"registered_{suffix}@example.com",
            "display_name": "Registered User",
            "role": "school_admin",
            "school_id": school_id,
        },
    )

    assert response.status_code == 200
    user_id = response.json()["data"]["id"]
    db_session.expire_all()
    assert db_session.get(User, user_id).school_id == school_id


def test_school_admin_cannot_manage_cross_school_user(client, db_session):
    own_school = _school(db_session, "own")
    other_school = _school(db_session, "other")
    manager = _create_user(db_session, role=Role.SCHOOL_ADMIN, school_id=own_school.id)
    other_user = _create_user(db_session, role=Role.TEACHER, school_id=other_school.id)

    assert client.get(f"/api/v1/users/{other_user.id}", headers=_headers(manager)).status_code == 403
    assert client.patch(
        f"/api/v1/users/{other_user.id}",
        json={"display_name": "Cross School"},
        headers=_headers(manager),
    ).status_code == 403
    assert client.patch(
        f"/api/v1/users/{other_user.id}/status",
        headers=_headers(manager),
    ).status_code == 403

    create_response = client.post(
        "/api/v1/users",
        json={
            "username": f"cross_{uuid4().hex}",
            "password": "12345678",
            "email": f"cross_{uuid4().hex}@example.com",
            "display_name": "Cross School User",
            "role": "teacher",
            "school_id": other_school.id,
        },
        headers=_headers(manager),
    )
    assert create_response.status_code == 403


def test_school_admin_can_create_own_teacher_but_not_admin_or_cross_school_student(client, db_session):
    own_school = _school(db_session, "manager")
    other_school = _school(db_session, "foreign")
    other_class = _class(db_session, other_school, "foreign")
    manager = _create_user(db_session, role=Role.SCHOOL_ADMIN, school_id=own_school.id)

    own_teacher = client.post(
        "/api/v1/users",
        json={
            "username": f"teacher_{uuid4().hex}",
            "password": "12345678",
            "email": f"teacher_{uuid4().hex}@example.com",
            "display_name": "Own Teacher",
            "role": "teacher",
        },
        headers=_headers(manager),
    )
    assert own_teacher.status_code == 200
    assert own_teacher.json()["data"]["school_id"] == own_school.id

    forbidden_admin = client.post(
        "/api/v1/users",
        json={
            "username": f"promoted_{uuid4().hex}",
            "password": "12345678",
            "email": f"promoted_{uuid4().hex}@example.com",
            "display_name": "Forbidden Admin",
            "role": "admin",
        },
        headers=_headers(manager),
    )
    assert forbidden_admin.status_code == 403

    foreign_student = client.post(
        "/api/v1/users",
        json={
            "username": f"student_{uuid4().hex}",
            "password": "12345678",
            "email": f"student_{uuid4().hex}@example.com",
            "display_name": "Foreign Student",
            "role": "student",
            "class_id": other_class.id,
        },
        headers=_headers(manager),
    )
    assert foreign_student.status_code == 400


def test_legacy_identity_router_imports_reexport_module_routers():
    from app.api.v1 import auth, users
    from app.modules.identity import auth_router, users_router

    assert auth.router is auth_router.router
    assert users.router is users_router.router
