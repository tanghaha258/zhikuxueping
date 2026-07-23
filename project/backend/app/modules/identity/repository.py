from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.user import User


class IdentityRepository:
    """User persistence queries. Transaction ownership stays with services."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: str) -> User | None:
        return self.db.scalar(select(User).where(User.id == user_id))

    def get_by_username(self, username: str) -> User | None:
        return self.db.scalar(select(User).where(User.username == username))

    def get_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def search(
        self,
        *,
        keyword: str,
        role: str,
        is_active: bool | None,
        visibility_filter,
        skip: int,
        limit: int,
    ) -> list[User]:
        statement = self._filtered_statement(keyword, role, is_active, visibility_filter)
        statement = statement.order_by(User.created_at.desc()).offset(skip).limit(limit)
        return list(self.db.scalars(statement).all())

    def count(
        self,
        *,
        keyword: str,
        role: str,
        is_active: bool | None,
        visibility_filter,
    ) -> int:
        statement = self._filtered_statement(keyword, role, is_active, visibility_filter)
        return self.db.scalar(select(func.count()).select_from(statement.subquery())) or 0

    def add(self, user: User) -> None:
        self.db.add(user)

    @staticmethod
    def _filtered_statement(keyword: str, role: str, is_active: bool | None, visibility_filter):
        statement = select(User)
        if visibility_filter is not None:
            statement = statement.where(visibility_filter)
        if keyword:
            like = f"%{keyword}%"
            statement = statement.where(User.username.ilike(like) | User.display_name.ilike(like))
        if role:
            statement = statement.where(User.role == role)
        if is_active is not None:
            statement = statement.where(User.is_active == is_active)
        return statement
