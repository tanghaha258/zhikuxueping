from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.resource import Resource
from app.schemas.resource import ResourceCreate, ResourceUpdate


def create_resource(db: Session, data: ResourceCreate, uploaded_by: str) -> Resource:
    from app.repositories.base import BaseRepository
    obj = Resource(
        project_id=data.project_id,
        title=data.title,
        res_type=data.res_type,
        url=data.url,
        file_size=data.file_size,
        uploaded_by=uploaded_by,
    )
    return BaseRepository(db, Resource).create(obj)


def update_resource(db: Session, resource_id: str, data: ResourceUpdate) -> Resource:
    from app.repositories.base import BaseRepository
    obj = BaseRepository(db, Resource).get_by_id(resource_id)
    if not obj:
        raise ValueError("资源不存在")
    return BaseRepository(db, Resource).update(obj, data.model_dump(exclude_unset=True))


def list_resources_by_project(db: Session, project_id: str) -> list[Resource]:
    stmt = select(Resource).where(Resource.project_id == project_id).order_by(Resource.created_at.desc())
    return list(db.execute(stmt).scalars().all())


def get_resource(db: Session, resource_id: str) -> Resource | None:
    from app.repositories.base import BaseRepository
    return BaseRepository(db, Resource).get_by_id(resource_id)


def delete_resource(db: Session, resource_id: str) -> bool:
    from app.repositories.base import BaseRepository
    return BaseRepository(db, Resource).delete(resource_id)
