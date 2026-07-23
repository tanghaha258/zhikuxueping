from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import Optional

from app.core.deps import get_current_user, require_roles
from app.core.exceptions import AppException
from app.core.response import success_response
from app.db.session import get_db
from app.models.user import User
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt_template import (
    PromptTemplateCreate, PromptTemplateUpdate, PromptTemplateResponse,
)

router = APIRouter(prefix="/prompt-templates", tags=["提示词模板管理"])


def _get_template_or_404(db: Session, template_id: str) -> PromptTemplate:
    tpl = db.get(PromptTemplate, template_id)
    if not tpl:
        raise AppException(code=40401, message="模板不存在", status_code=404)
    return tpl


@router.get("", summary="提示词模板列表")
def list_templates(
    subject: Optional[str] = Query(None, description="按学科筛选"),
    exam_type: Optional[str] = Query(None, description="按考试类型筛选"),
    is_active: Optional[bool] = Query(None, description="按启用状态筛选"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    q = select(PromptTemplate).order_by(PromptTemplate.created_at.desc())
    if subject:
        q = q.where(PromptTemplate.subject == subject)
    if exam_type:
        q = q.where(PromptTemplate.exam_type == exam_type)
    if is_active is not None:
        q = q.where(PromptTemplate.is_active == is_active)
    items = db.scalars(q.offset(skip).limit(limit)).all()
    return success_response(data=[PromptTemplateResponse.model_validate(t) for t in items])


@router.get("/active", summary="获取当前可用模板（按学科+考试类型）")
def get_active_template(
    subject: str = Query(..., description="学科"),
    exam_type: str = Query("quiz", description="考试类型"),
    db: Session = Depends(get_db),
):
    tpl = db.scalars(
        select(PromptTemplate)
        .where(PromptTemplate.subject == subject)
        .where(PromptTemplate.exam_type == exam_type)
        .where(PromptTemplate.is_active == True)
        .order_by(PromptTemplate.updated_at.desc())
        .limit(1)
    ).first()
    if not tpl:
        return success_response(data=None)
    return success_response(data=PromptTemplateResponse.model_validate(tpl))


@router.post("", summary="创建提示词模板")
def create_template(
    data: PromptTemplateCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin"])),
):
    tpl = PromptTemplate(
        name=data.name,
        subject=data.subject,
        exam_type=data.exam_type,
        template=data.template,
        description=data.description,
        is_active=data.is_active,
    )
    db.add(tpl)
    db.commit()
    db.refresh(tpl)
    return success_response(data=PromptTemplateResponse.model_validate(tpl), message="创建成功")


@router.put("/{template_id}", summary="更新提示词模板")
def update_template(
    template_id: str,
    data: PromptTemplateUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin"])),
):
    tpl = _get_template_or_404(db, template_id)
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(tpl, k, v)
    db.commit()
    db.refresh(tpl)
    return success_response(data=PromptTemplateResponse.model_validate(tpl), message="更新成功")


@router.delete("/{template_id}", summary="删除提示词模板")
def delete_template(
    template_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(["admin"])),
):
    tpl = _get_template_or_404(db, template_id)
    db.delete(tpl)
    db.commit()
    return success_response(message="删除成功")
