from types import SimpleNamespace

from app.core.request_context import require_request_scope

from pytest import raises as reraises
from fastapi import HTTPException

def test_missing_tenant_id_require_request_scope() -> None:
    request = SimpleNamespace(state=SimpleNamespace(tenant_id=None, org_id="org0"))
    with reraises(HTTPException) as exc_info:
        require_request_scope(request)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["message"] == "Tenant context is required."
    assert exc_info.value.detail["details"]["reason_code"] == "TENANT_CONTEXT_MISSING"


def test_missing_org_id_require_request_scope() -> None:
    request = SimpleNamespace(state=SimpleNamespace(tenant_id="tenant0", org_id=None))
    with reraises(HTTPException) as exc_info:
        require_request_scope(request)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["message"] == "Organization context is required."
    assert exc_info.value.detail["details"]["reason_code"] == "ORG_CONTEXT_MISSING"


def test_success_require_request_scope() -> None:
    request = SimpleNamespace(state=SimpleNamespace(tenant_id="tenant0", org_id="org0"))
    require_request_scope(request)
