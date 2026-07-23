"""Provider registration and connectivity operations for the AI gateway."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai_provider import AiProvider
from app.modules.ai_gateway.client import complete_async
from app.repositories.base import BaseRepository
from app.schemas.ai import AiProviderCreate, AiProviderUpdate


def list_providers(db: Session) -> list[AiProvider]:
    statement = select(AiProvider).order_by(AiProvider.created_at.desc())
    return list(db.execute(statement).scalars().all())


def create_provider(db: Session, data: AiProviderCreate) -> AiProvider:
    provider = AiProvider(
        name=data.name,
        api_url=data.api_url,
        model=data.model,
        api_key=data.api_key,
    )
    return BaseRepository(db, AiProvider).create(provider)


def update_provider(
    db: Session,
    provider_id: str,
    data: AiProviderUpdate,
) -> AiProvider:
    repository = BaseRepository(db, AiProvider)
    provider = repository.get_by_id(provider_id)
    if not provider:
        raise ValueError("Provider \u4e0d\u5b58\u5728")

    update_data = data.model_dump(exclude_unset=True)
    if "api_key" in update_data and "****" in str(update_data["api_key"]):
        del update_data["api_key"]
    return repository.update(provider, update_data)


def delete_provider(db: Session, provider_id: str) -> bool:
    return BaseRepository(db, AiProvider).delete(provider_id)


def get_provider(db: Session, provider_id: str) -> AiProvider | None:
    return BaseRepository(db, AiProvider).get_by_id(provider_id)


async def test_provider_connection(api_url: str, api_key: str, model: str) -> bool:
    try:
        await complete_async(
            api_url,
            api_key,
            model,
            [{"role": "user", "content": "Hello"}],
            temperature=0.0,
            max_tokens=5,
            timeout=15.0,
        )
        return True
    except Exception:
        return False
