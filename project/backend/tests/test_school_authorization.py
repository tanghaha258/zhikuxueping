from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models.school import Class, School
from app.models.user import Role, User


def _school(db, label: str) -> School:
    school = School(name=f"Authorization School {label}-{uuid4().hex}")
    db.add(school)
    db.commit()
    db.refresh(school)
    return school


def _class(db, school: School, label: str, head_teacher_id: str | None = None) -> Class:
    cls = Class(
        school_id=school.id,
        grade="七年级",
        name=f"Authorization Class {label}-{uuid4().hex}",
        head_teacher_id=head_teacher_id,
    )
    db.add(cls)
    db.commit()
    db.refresh(cls)
    return cls


def _user(db, *, role: Role, school_id: str | None = None, class_id: str | None = None) -> User:
    suffix = uuid4().hex
    user = User(
        username=f"school_auth_{suffix}",
        email=f"school_auth_{suffix}@example.com",
        display_name=f"School Auth {suffix}",
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
    return {"Authorization": f"Bearer {create_access_token(data={'sub': user.id})}"}


def test_school_and_roster_reads_require_authentication(client, db_session):
    school = _school(db_session, "anonymous")
    cls = _class(db_session, school, "anonymous")
    teacher = _user(db_session, role=Role.TEACHER, school_id=school.id)

    paths = [
        "/api/v1/schools",
        f"/api/v1/schools/{school.id}",
        f"/api/v1/schools/{school.id}/classes",
        f"/api/v1/schools/classes/{cls.id}",
        f"/api/v1/schools/teachers/{teacher.id}/classes",
        f"/api/v1/schools/classes/{cls.id}/students",
    ]

    for path in paths:
        assert client.get(path).status_code == 401


def test_students_and_parents_cannot_list_schools(client, db_session):
    school = _school(db_session, "role-deny")
    student = _user(db_session, role=Role.STUDENT, school_id=school.id)
    parent = _user(db_session, role=Role.PARENT, school_id=school.id)

    assert client.get("/api/v1/schools", headers=_headers(student)).status_code == 403
    assert client.get("/api/v1/schools", headers=_headers(parent)).status_code == 403


def test_school_admin_cannot_manage_other_school(client, db_session):
    own_school = _school(db_session, "own")
    other_school = _school(db_session, "other")
    manager = _user(db_session, role=Role.SCHOOL_ADMIN, school_id=own_school.id)
    other_class = _class(db_session, other_school, "other")
    own_teacher = _user(db_session, role=Role.TEACHER, school_id=own_school.id)

    assert client.get(f"/api/v1/schools/{other_school.id}", headers=_headers(manager)).status_code == 403
    assert client.post(
        f"/api/v1/schools/{other_school.id}/classes",
        json={"school_id": other_school.id, "name": "Forbidden", "grade": "七年级"},
        headers=_headers(manager),
    ).status_code == 403
    assert client.put(
        f"/api/v1/schools/classes/{other_class.id}",
        json={"name": "Forbidden"},
        headers=_headers(manager),
    ).status_code == 403
    assert client.delete(
        f"/api/v1/schools/classes/{other_class.id}",
        headers=_headers(manager),
    ).status_code == 403
    assert client.post(
        "/api/v1/schools/teacher-classes",
        json={"teacher_id": own_teacher.id, "class_id": other_class.id},
        headers=_headers(manager),
    ).status_code == 403


def test_teacher_can_read_only_assigned_class_and_its_students(client, db_session):
    school = _school(db_session, "teacher")
    teacher = _user(db_session, role=Role.TEACHER, school_id=school.id)
    assigned_class = _class(db_session, school, "assigned", head_teacher_id=teacher.id)
    other_class = _class(db_session, school, "other")
    _user(db_session, role=Role.STUDENT, school_id=school.id, class_id=assigned_class.id)

    assert client.get(
        f"/api/v1/schools/classes/{assigned_class.id}", headers=_headers(teacher)
    ).status_code == 200
    assert client.get(
        f"/api/v1/schools/classes/{assigned_class.id}/students", headers=_headers(teacher)
    ).status_code == 200
    assert client.get(
        f"/api/v1/schools/classes/{other_class.id}", headers=_headers(teacher)
    ).status_code == 403
    assert client.get(
        f"/api/v1/schools/classes/{other_class.id}/students", headers=_headers(teacher)
    ).status_code == 403


def test_invalid_binding_and_referenced_class_deletion_are_rejected(client, db_session):
    school_a = _school(db_session, "binding-a")
    school_b = _school(db_session, "binding-b")
    admin = _user(db_session, role=Role.ADMIN)
    teacher = _user(db_session, role=Role.TEACHER, school_id=school_a.id)
    foreign_class = _class(db_session, school_b, "binding-b")
    occupied_class = _class(db_session, school_a, "occupied")
    _user(db_session, role=Role.STUDENT, school_id=school_a.id, class_id=occupied_class.id)

    assert client.post(
        "/api/v1/schools/teacher-classes",
        json={"teacher_id": teacher.id, "class_id": foreign_class.id},
        headers=_headers(admin),
    ).status_code == 400

    response = client.delete(
        f"/api/v1/schools/classes/{occupied_class.id}", headers=_headers(admin)
    )
    assert response.status_code == 400
    assert db_session.get(Class, occupied_class.id) is not None


def test_legacy_school_router_import_reexports_module_router():
    from app.api.v1 import schools
    from app.modules.schools import router

    assert schools.router is router.router
