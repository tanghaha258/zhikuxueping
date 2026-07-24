"""工具上下文链接持久化（Task 8）。

约定（与 project_designs.repository / resources.repository 一致）：
仓库只负责读写 ORM，不调用 ``db.commit()``，提交由服务层统一控制。
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tool_context import ToolContextLink


class ToolContextRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, link: ToolContextLink) -> None:
        self.db.add(link)
        self.db.flush()

    def get(self, link_id: str) -> Optional[ToolContextLink]:
        return self.db.get(ToolContextLink, link_id)

    def find(
        self,
        *,
        artifact_type: str,
        artifact_id: str,
        project_id: str,
        placement: str,
    ) -> Optional[ToolContextLink]:
        """按 (artifact_type, artifact_id, project_id, placement) 唯一约束查找。"""
        return self.db.scalar(
            select(ToolContextLink).where(
                ToolContextLink.artifact_type == artifact_type,
                ToolContextLink.artifact_id == artifact_id,
                ToolContextLink.project_id == project_id,
                ToolContextLink.placement == placement,
            )
        )

    def list_by_project(
        self, project_id: str, *, artifact_type: str | None = None
    ) -> list[ToolContextLink]:
        statement = select(ToolContextLink).where(
            ToolContextLink.project_id == project_id
        )
        if artifact_type:
            statement = statement.where(
                ToolContextLink.artifact_type == artifact_type
            )
        statement = statement.order_by(ToolContextLink.created_at.desc())
        return list(self.db.scalars(statement).all())

    def list_by_artifact(
        self, artifact_type: str, artifact_id: str
    ) -> list[ToolContextLink]:
        statement = (
            select(ToolContextLink)
            .where(
                ToolContextLink.artifact_type == artifact_type,
                ToolContextLink.artifact_id == artifact_id,
            )
            .order_by(ToolContextLink.created_at.desc())
        )
        return list(self.db.scalars(statement).all())

    def delete(self, link: ToolContextLink) -> None:
        self.db.delete(link)
        self.db.flush()
