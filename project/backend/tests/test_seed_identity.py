from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.user import Role, User
import app.models  # noqa: F401
from database import seed


def test_seed_creates_organization_scoped_demo_accounts():
    assert hasattr(seed, "create_seed_organization")

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        school, cls = seed.create_seed_organization(session)
        seed.create_seed_users(session, school.id, cls.id)

        users = {user.username: user for user in session.scalars(select(User)).all()}
        assert users["admin"].role == Role.ADMIN
        assert users["admin"].school_id is None
        assert users["schooladmin"].school_id == school.id
        assert users["zhanglaoshi"].school_id == school.id
        assert users["lixiaoming"].school_id == school.id
        assert users["lixiaoming"].class_id == cls.id
        assert users["wangfang"].school_id == school.id
        assert users["wangfang"].class_id == cls.id
    finally:
        session.close()
        engine.dispose()
