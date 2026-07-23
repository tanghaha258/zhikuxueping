"""
用户数据访问层（Repository）

提供基础 CRUD 操作，使用 SQLAlchemy 2.0 style（select() 风格查询）。
与业务逻辑层（Service）和模型层（Model）解耦。
"""

from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    """用户仓储，封装用户表的所有数据库操作。"""

    def __init__(self, db: Session):
        self.db = db

    # ── 查询 ────────────────────────────────────────────────────

    def get_by_id(self, user_id: str) -> Optional[User]:
        """
        按主键 ID 查询用户。

        Args:
            user_id: 用户 UUID。

        Returns:
            匹配的 User 对象，未找到返回 None。
        """
        stmt = select(User).where(User.id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_username(self, username: str) -> Optional[User]:
        """
        按用户名查询用户（精确匹配）。

        Args:
            username: 用户名。

        Returns:
            匹配的 User 对象，未找到返回 None。
        """
        stmt = select(User).where(User.username == username)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        """
        按邮箱查询用户（精确匹配）。

        Args:
            email: 电子邮箱。

        Returns:
            匹配的 User 对象，未找到返回 None。
        """
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def search(
        self,
        keyword: str = "",
        role: str = "",
        is_active: bool | None = None,
        skip: int = 0,
        limit: int = 20,
    ) -> list[User]:
        stmt = select(User)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                User.username.ilike(like) | User.display_name.ilike(like)
            )
        if role:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        stmt = stmt.order_by(User.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def count_search(
        self,
        keyword: str = "",
        role: str = "",
        is_active: bool | None = None,
    ) -> int:
        stmt = select(func.count()).select_from(User)
        if keyword:
            like = f"%{keyword}%"
            stmt = stmt.where(
                User.username.ilike(like) | User.display_name.ilike(like)
            )
        if role:
            stmt = stmt.where(User.role == role)
        if is_active is not None:
            stmt = stmt.where(User.is_active == is_active)
        return self.db.execute(stmt).scalar() or 0

    def list_all(self, skip: int = 0, limit: int = 100) -> list[User]:
        """
        分页查询所有用户。

        Args:
            skip: 跳过记录数。
            limit: 返回记录数上限。

        Returns:
            用户列表。
        """
        stmt = select(User).offset(skip).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    # ── 写入 ────────────────────────────────────────────────────

    def create(self, user: User) -> User:
        """
        创建新用户记录。

        Args:
            user: 待创建的 User ORM 对象（尚未持久化）。

        Returns:
            已持久化并刷新后的 User 对象。
        """
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, db_obj: User, update_data: dict) -> User:
        """
        部分更新用户字段。

        Args:
            db_obj: 数据库中已存在的 User 对象。
            update_data: 需更新的字段字典（key: 属性名, value: 新值）。

        Returns:
            更新并刷新后的 User 对象。
        """
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        self.db.commit()
        self.db.refresh(db_obj)
        return db_obj

    def delete(self, user_id: str) -> bool:
        """
        删除用户（物理删除）。

        Args:
            user_id: 用户 UUID。

        Returns:
            是否成功删除。
        """
        user = self.get_by_id(user_id)
        if not user:
            return False
        self.db.delete(user)
        self.db.commit()
        return True
