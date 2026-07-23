from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.schools import service
from app.schemas.school import ClassCreate, ClassResponse, ClassUpdate, SchoolCreate, SchoolResponse, SchoolUpdate
from app.schemas.teacher_class import TeacherClassBind, TeacherClassResponse
from app.schemas.user import UserResponse


router = APIRouter(prefix="/schools", tags=["学校管理"])


@router.post("/teacher-classes", summary="绑定教师-班级")
def bind_teacher_class_api(
    data: TeacherClassBind,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    binding = service.bind_teacher_class(db, current_user, data.teacher_id, data.class_id)
    return success_response(data=TeacherClassResponse.model_validate(binding), message="绑定成功")


@router.delete("/teacher-classes", summary="解绑教师-班级")
def unbind_teacher_class_api(
    teacher_id: str = Query(...),
    class_id: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    try:
        service.unbind_teacher_class(db, current_user, teacher_id, class_id)
    except ValueError as error:
        raise AppException(code=40401, message=str(error), status_code=404) from error
    return success_response(message="解绑成功")


@router.get("/teachers/{teacher_id}/classes", summary="教师所教班级")
def list_teacher_classes_api(
    teacher_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_teacher_classes(db, current_user, teacher_id)
    return success_response(data=[TeacherClassResponse.model_validate(item) for item in items])


@router.get("/classes/{class_id}/teachers", summary="班级的任教教师")
def list_class_teachers_api(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = service.list_class_teachers(db, current_user, class_id)
    return success_response(data=[TeacherClassResponse.model_validate(item) for item in items])


@router.get("/classes/{class_id}/students", summary="班级学生列表")
def list_students_by_class_api(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    students = service.list_students(db, current_user, class_id)
    return success_response(data=[UserResponse.model_validate(student) for student in students])


@router.get("/classes/{class_id}", summary="班级详情")
def get_class_api(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success_response(data=ClassResponse.model_validate(service.get_class(db, current_user, class_id)))


@router.put("/classes/{class_id}", summary="更新班级")
def update_class_api(
    class_id: str,
    data: ClassUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    try:
        cls = service.update_class(db, current_user, class_id, data)
    except ValueError as error:
        raise AppException(code=41001, message=str(error), status_code=400) from error
    return success_response(data=ClassResponse.model_validate(cls), message="更新成功")


@router.delete("/classes/{class_id}", summary="删除班级")
def delete_class_api(
    class_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    try:
        service.delete_class(db, current_user, class_id)
    except ValueError as error:
        raise AppException(code=41002, message=str(error), status_code=400) from error
    return success_response(message="删除成功")


@router.get("", summary="学校列表")
def list_schools_api(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    schools = service.list_schools(db, current_user, skip, limit)
    return success_response(data=[SchoolResponse.model_validate(school) for school in schools])


@router.post("", summary="创建学校")
def create_school_api(
    data: SchoolCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    school = service.create_school(db, current_user, data)
    return success_response(data=SchoolResponse.model_validate(school), message="创建成功")


@router.get("/{school_id}", summary="学校详情")
def get_school_api(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return success_response(data=SchoolResponse.model_validate(service.get_school(db, current_user, school_id)))


@router.put("/{school_id}", summary="更新学校")
def update_school_api(
    school_id: str,
    data: SchoolUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    school = service.update_school(db, current_user, school_id, data)
    return success_response(data=SchoolResponse.model_validate(school), message="更新成功")


@router.delete("/{school_id}", summary="删除学校")
def delete_school_api(
    school_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    try:
        service.delete_school(db, current_user, school_id)
    except ValueError as error:
        raise AppException(code=41002, message=str(error), status_code=400) from error
    return success_response(message="删除成功")


@router.get("/{school_id}/classes", summary="班级列表")
def list_classes_by_school_api(
    school_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    classes = service.list_classes(db, current_user, school_id, skip, limit)
    return success_response(data=[ClassResponse.model_validate(cls) for cls in classes])


@router.post("/{school_id}/classes", summary="创建班级")
def create_class_by_school_api(
    school_id: str,
    data: ClassCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "school_admin"])),
):
    cls = service.create_class(db, current_user, school_id, data)
    return success_response(data=ClassResponse.model_validate(cls), message="创建成功")
