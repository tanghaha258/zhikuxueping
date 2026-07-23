import importlib.util

import pytest

from app.core.exceptions import AppException
from app.schemas.resource import ResourceCreate


def test_legacy_resource_router_reexports_module_router():
    assert importlib.util.find_spec("app.modules.resources.router") is not None

    from app.api.v1 import resources
    from app.modules.resources import router

    assert resources.router is router.router


def test_resource_service_rejects_missing_resource(db_session):
    from app.modules.resources import service

    with pytest.raises(AppException) as error:
        service.get_resource(db_session, "missing-resource")

    assert error.value.code == 40401
    assert error.value.status_code == 404


def test_resource_service_persists_creator_and_payload(db_session):
    from app.modules.resources import service

    resource = service.create_resource(
        db_session,
        ResourceCreate(
            project_id=None,
            title="Module resource",
            res_type="link",
            url="https://example.com/module-resource",
            file_size=128,
        ),
        uploaded_by="resource-module-owner",
    )

    loaded = service.get_resource(db_session, resource.id)
    assert loaded.id == resource.id
    assert loaded.uploaded_by == "resource-module-owner"
    assert loaded.title == "Module resource"
    assert loaded.url == "https://example.com/module-resource"
    assert loaded.file_size == 128
