from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.deps import require_roles
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.modules.learning_profiles.policy import (
    ensure_can_access_class_learning_profile,
)
from app.modules.learning_profiles.service import (
    generate_class_learning_profile,
    generate_class_report,
    get_class_reports,
)

router = APIRouter(prefix="/learning-profile", tags=["学情分析"])


@router.get("/classes/{class_id}", summary="获取班级学情画像")
def get_class_profile(
    class_id: str,
    subject: str = "math",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    ensure_can_access_class_learning_profile(db, current_user, class_id)
    data = generate_class_learning_profile(db, class_id, subject)
    return success_response(data=data)


@router.post("/classes/{class_id}/report", summary="生成班级学情报告")
def create_report(
    class_id: str,
    subject: str = "math",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    ensure_can_access_class_learning_profile(db, current_user, class_id)
    data = generate_class_report(db, class_id, subject)
    return success_response(data=data, message="报告已生成")


@router.get("/classes/{class_id}/reports", summary="班级学情报告列表")
def list_reports(
    class_id: str,
    subject: str = "math",
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["teacher", "school_admin", "admin"])),
):
    ensure_can_access_class_learning_profile(db, current_user, class_id)
    data = get_class_reports(db, class_id, subject)
    return success_response(data=data)
