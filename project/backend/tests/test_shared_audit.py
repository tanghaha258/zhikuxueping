import importlib.util


def test_legacy_audit_service_reexports_shared_implementation():
    assert importlib.util.find_spec("app.shared.audit") is not None

    from app.services import audit
    from app.shared import audit as shared_audit

    assert audit.log_action is shared_audit.log_action
