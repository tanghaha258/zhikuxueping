from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.subjects import service
from app.schemas.subject import SubjectCreate, SubjectResponse, SubjectUpdate


router = APIRouter(prefix="/subjects", tags=["Subjects"])


@router.get("", summary="List subjects")
def list_subjects_api(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    items = service.list_subjects(db, skip, limit)
    return success_response(data=[SubjectResponse.model_validate(subject) for subject in items])


@router.post("", summary="Create subject")
def create_subject_api(
    data: SubjectCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin"])),
):
    subject = service.create_subject(db, data)
    return success_response(data=SubjectResponse.model_validate(subject), message="Created successfully")


@router.get("/{subject_id}", summary="Get subject")
def get_subject_api(
    subject_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    subject = service.get_subject(db, subject_id)
    return success_response(data=SubjectResponse.model_validate(subject))


@router.put("/{subject_id}", summary="Update subject")
def update_subject_api(
    subject_id: str,
    data: SubjectUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin"])),
):
    subject = service.update_subject(db, subject_id, data)
    return success_response(data=SubjectResponse.model_validate(subject), message="Updated successfully")


@router.delete("/{subject_id}", summary="Delete subject")
def delete_subject_api(
    subject_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin"])),
):
    service.delete_subject(db, subject_id)
    return success_response(message="Deleted successfully")
