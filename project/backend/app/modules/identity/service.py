from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.core.security import hash_password, verify_password
from app.models.user import Role, User
from app.modules.identity import policy
from app.modules.identity.repository import IdentityRepository
from app.schemas.user import PasswordChange, ProfileUpdate, UserCreate, UserUpdate


def get_user_by_id(db: Session, user_id: str) -> User | None:
    return IdentityRepository(db).get_by_id(user_id)


def authenticate_user(db: Session, username: str, password: str) -> User:
    repository = IdentityRepository(db)
    user = repository.get_by_username(username)
    if not user:
        raise AppException(code=40001, message="用户名或密码错误", status_code=401)
    if not user.is_active:
        raise AppException(code=40003, message="账号已被停用", status_code=403)
    if not verify_password(password, user.hashed_password):
        user.failed_attempts = (user.failed_attempts or 0) + 1
        _commit(db)
        raise AppException(code=40001, message="用户名或密码错误", status_code=401)
    if user.failed_attempts:
        user.failed_attempts = 0
        _commit(db)
        db.refresh(user)
    return user


def register_test_user(db: Session, data: UserCreate) -> User:
    school_id, class_id = policy.resolve_school_and_class(
        db,
        None,
        requested_school_id=data.school_id,
        class_id=data.class_id,
    )
    return _create_user(db, data, school_id=school_id, class_id=class_id)


def create_user(db: Session, actor: User, data: UserCreate) -> User:
    policy.ensure_can_assign_role(actor, data.role)
    school_id, class_id = policy.resolve_school_and_class(
        db,
        actor,
        requested_school_id=data.school_id,
        class_id=data.class_id,
    )
    return _create_user(db, data, school_id=school_id, class_id=class_id)


def search_users(
    db: Session,
    actor: User,
    *,
    keyword: str,
    role: str,
    is_active: bool | None,
    skip: int,
    limit: int,
) -> list[User]:
    return IdentityRepository(db).search(
        keyword=keyword,
        role=role,
        is_active=is_active,
        visibility_filter=policy.user_visibility_filter(actor),
        skip=skip,
        limit=limit,
    )


def count_users(
    db: Session,
    actor: User,
    *,
    keyword: str,
    role: str,
    is_active: bool | None,
) -> int:
    return IdentityRepository(db).count(
        keyword=keyword,
        role=role,
        is_active=is_active,
        visibility_filter=policy.user_visibility_filter(actor),
    )


def get_managed_user(db: Session, actor: User, user_id: str) -> User:
    user = _require_user(IdentityRepository(db), user_id)
    policy.ensure_can_view_user(db, actor, user)
    return user


def update_managed_user(db: Session, actor: User, user_id: str, data: UserUpdate) -> User:
    user = _require_user(IdentityRepository(db), user_id)
    policy.ensure_can_manage_user(db, actor, user)
    values = data.model_dump(exclude_unset=True)
    role = values.get("role", user.role)
    policy.ensure_can_assign_role(actor, role)

    requested_school_id = values.get("school_id", user.school_id)
    if actor.role == Role.SCHOOL_ADMIN:
        if "school_id" in values and values["school_id"] != actor.school_id:
            raise AppException(code=40301, message="权限不足", status_code=403)
        requested_school_id = actor.school_id
    requested_class_id = values.get("class_id", user.class_id)
    school_id, class_id = policy.resolve_school_and_class(
        db,
        actor if actor.role == Role.SCHOOL_ADMIN else None,
        requested_school_id=requested_school_id,
        class_id=requested_class_id,
    )
    values["school_id"] = school_id
    values["class_id"] = class_id
    for field, value in values.items():
        setattr(user, field, value)
    _commit(db)
    db.refresh(user)
    return user


def toggle_user_status(db: Session, actor: User, user_id: str) -> User:
    user = _require_user(IdentityRepository(db), user_id)
    policy.ensure_can_manage_user(db, actor, user)
    if actor.id == user.id:
        raise AppException(code=40001, message="不能停用自己的账号", status_code=400)
    user.is_active = not user.is_active
    _commit(db)
    db.refresh(user)
    return user


def update_profile(db: Session, user: User, data: ProfileUpdate) -> User:
    values = data.model_dump(exclude_unset=True)
    for field, value in values.items():
        if value is not None:
            setattr(user, field, value)
    _commit(db)
    db.refresh(user)
    return user


def change_password(db: Session, user: User, data: PasswordChange) -> None:
    if not verify_password(data.old_password, user.hashed_password):
        raise AppException(code=40001, message="原密码错误", status_code=400)
    user.hashed_password = hash_password(data.new_password)
    _commit(db)


def _create_user(db: Session, data: UserCreate, *, school_id: str | None, class_id: str | None) -> User:
    repository = IdentityRepository(db)
    if repository.get_by_username(data.username):
        raise AppException(code=40001, message="用户名已被注册", status_code=409)
    if repository.get_by_email(data.email):
        raise AppException(code=40001, message="邮箱已被注册", status_code=409)
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        display_name=data.display_name,
        role=data.role,
        school_id=school_id,
        class_id=class_id,
    )
    repository.add(user)
    _commit(db)
    db.refresh(user)
    return user


def _require_user(repository: IdentityRepository, user_id: str) -> User:
    user = repository.get_by_id(user_id)
    if not user:
        raise AppException(code=40401, message="用户不存在", status_code=404)
    return user


def _commit(db: Session) -> None:
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
