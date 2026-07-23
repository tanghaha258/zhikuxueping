"""资源持久化操作。

约定（与 project_designs.repository 一致）：仓库只负责读写 ORM，
不调用 `db.commit()`，提交由服务层统一控制。

核心闭环扩展（计划 4.1/3.5/3.7）：
- `list_by_project` 支持 tier/stage/review_status 过滤。
- `list_published_for_student` 学生侧仅返回 PUBLISHED/APPROVED 资源。
- `count_published_by_tier` 递进覆盖统计：每层至少一项已发布资源。
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import ReviewStatus
from app.models.resource import Resource


class ResourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, resource_id: str) -> Resource | None:
        return self.db.scalar(select(Resource).where(Resource.id == resource_id))

    def list_by_project(
        self,
        project_id: str,
        *,
        tier: str | None = None,
        stage: str | None = None,
        review_status: str | None = None,
    ) -> list[Resource]:
        """教师/管理员视角：按层级/阶段/审核状态过滤。"""
        statement = select(Resource).where(Resource.project_id == project_id)
        if tier:
            statement = statement.where(Resource.tier == tier)
        if stage:
            statement = statement.where(Resource.stage == stage)
        if review_status:
            statement = statement.where(Resource.review_status == review_status)
        statement = statement.order_by(Resource.created_at.desc())
        return list(self.db.scalars(statement).all())

    def list_published_for_student(self, project_id: str) -> list[Resource]:
        """学生侧：仅返回审核已发布/已通过的资源（计划 3.7）。

        历史未分层资源若 review_status 为 PUBLISHED/APPROVED 仍可见，
        避免迁移后学生看不到既有资源。
        """
        statement = (
            select(Resource)
            .where(Resource.project_id == project_id)
            .where(
                Resource.review_status.in_(
                    [ReviewStatus.PUBLISHED, ReviewStatus.APPROVED]
                )
            )
            .order_by(Resource.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def count_by_tier(self, project_id: str) -> dict[str, int]:
        """统计各层资源总数（含未分层），用于资源页展示。"""
        rows = self.db.execute(
            select(Resource.tier, func.count())
            .where(Resource.project_id == project_id)
            .group_by(Resource.tier)
        ).all()
        result = {"foundation": 0, "enhancement": 0, "extension": 0, "unassigned": 0}
        for tier_val, cnt in rows:
            if tier_val is None:
                result["unassigned"] = int(cnt)
            elif tier_val.value in result:
                result[tier_val.value] = int(cnt)
        return result

    def count_published_by_tier(self, project_id: str) -> dict[str, int]:
        """统计各层已发布（PUBLISHED）资源数量，用于递进覆盖判定。

        仅 PUBLISHED 计入覆盖（APPROVED 表示审核通过但未发布，学生不可见）。
        """
        rows = self.db.execute(
            select(Resource.tier, func.count())
            .where(Resource.project_id == project_id)
            .where(Resource.review_status == ReviewStatus.PUBLISHED)
            .group_by(Resource.tier)
        ).all()
        result = {"foundation": 0, "enhancement": 0, "extension": 0}
        for tier_val, cnt in rows:
            if tier_val is not None and tier_val.value in result:
                result[tier_val.value] = int(cnt)
        return result

    def list_published_by_stage_tier(
        self, project_id: str, stage: str | None, tier: str | None
    ) -> list[Resource]:
        """按 stage+tier 查询已发布资源，用于任务发布预览关联资源展示。"""
        statement = (
            select(Resource)
            .where(Resource.project_id == project_id)
            .where(Resource.review_status == ReviewStatus.PUBLISHED)
        )
        if stage is not None:
            statement = statement.where(Resource.stage == stage)
        if tier is not None:
            statement = statement.where(Resource.tier == tier)
        statement = statement.order_by(Resource.created_at.desc())
        return list(self.db.scalars(statement).all())

    def add(self, resource: Resource) -> None:
        self.db.add(resource)

    def delete(self, resource: Resource) -> None:
        self.db.delete(resource)
