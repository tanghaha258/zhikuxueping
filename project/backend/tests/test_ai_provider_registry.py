from app.modules.ai_gateway.providers import (
    create_provider,
    delete_provider,
    get_provider,
    list_providers,
    update_provider,
)
from app.schemas.ai import AiProviderCreate, AiProviderUpdate


def _provider_data() -> AiProviderCreate:
    return AiProviderCreate(
        name="Provider",
        api_url="https://provider.example/v1",
        model="model-1",
        api_key="sk-original-key",
    )


def test_provider_registry_persists_and_lists_provider(db_session):
    provider = create_provider(db_session, _provider_data())

    assert get_provider(db_session, provider.id) is provider
    assert provider.id in {item.id for item in list_providers(db_session)}


def test_provider_update_keeps_the_stored_key_when_given_a_masked_value(db_session):
    provider = create_provider(db_session, _provider_data())

    updated = update_provider(
        db_session,
        provider.id,
        AiProviderUpdate(name="Updated provider", api_key="sk-o****-key"),
    )

    assert updated.name == "Updated provider"
    assert updated.api_key == "sk-original-key"


def test_provider_registry_deletes_existing_provider(db_session):
    provider = create_provider(db_session, _provider_data())

    assert delete_provider(db_session, provider.id) is True
    assert get_provider(db_session, provider.id) is None
    assert delete_provider(db_session, provider.id) is False
