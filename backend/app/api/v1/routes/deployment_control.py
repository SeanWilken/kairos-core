from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from urllib.parse import urlsplit
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.auth_context import AuthContext, require_authentication, require_org_access
from app.core.deployment_store import (
    DeploymentStoreConflictError,
    DeploymentStoreReferenceError,
    deployment_store,
)
from app.core.response import ok_response
from app.core.schemas import Envelope

bearer_scheme = HTTPBearer(auto_error=False)


def _deployment_bearer_doc(
    _: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
) -> None:
    return None


router = APIRouter(
    prefix="/deployment-control",
    tags=["deployment-control"],
    dependencies=[Depends(_deployment_bearer_doc)],
)
WRITE_ROLES = {"owner", "admin"}
SENSITIVE_CONFIG_KEYS = {"password", "token", "secret", "credential", "api_key", "apikey"}


def _contains_sensitive_key(value: object) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            is_reference = normalized.endswith("_ref") or normalized.endswith("_reference")
            if not is_reference and any(part in normalized for part in SENSITIVE_CONFIG_KEYS):
                return True
            if _contains_sensitive_key(item):
                return True
    if isinstance(value, list):
        return any(_contains_sensitive_key(item) for item in value)
    return False


def _validate_nonsecret_config(value: dict[str, Any]) -> dict[str, Any]:
    if _contains_sensitive_key(value):
        raise ValueError("Config cannot contain credentials or secret-shaped keys; use a secret reference.")
    return value


def _validate_secret_reference(value: str) -> str:
    reference = value.strip()
    if not reference:
        return ""
    allowed = r"(?:vault|op|env|keyring|aws-secretsmanager|azure-keyvault|gcp-secretmanager)://[^\s]+"
    if re.fullmatch(allowed, reference) is None:
        raise ValueError("Credential references must use an approved secret-reference URI.")
    return reference


def _validate_registry_url(value: str) -> str:
    registry_url = value.strip()
    parsed = urlsplit(registry_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Registry URL must be an HTTP(S) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Registry URL cannot contain credentials, query parameters, or fragments.")
    return registry_url.rstrip("/")


def _resolve_org(auth: AuthContext, requested_org_id: str | None, *, write: bool = False) -> str:
    org_id = str(requested_org_id or auth.org_id or "").strip()
    if not org_id:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Organization scope is required.",
                "details": {"reason_code": "ORG_SCOPE_REQUIRED"},
            },
        )
    require_org_access(auth, org_id=org_id, allowed_roles=WRITE_ROLES if write else None)
    return org_id


def _not_found(resource: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "message": f"{resource} not found.",
            "details": {"reason_code": f"DEPLOYMENT_{resource.upper().replace(' ', '_')}_NOT_FOUND"},
        },
    )


def _conflict(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "message": str(error),
            "details": {"reason_code": "DEPLOYMENT_CONTROL_CONFLICT"},
        },
    )


def _reference_error(error: Exception) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={
            "message": str(error),
            "details": {"reason_code": "DEPLOYMENT_CONTROL_REFERENCE_INVALID"},
        },
    )


class RegistryConnectionCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    provider: Literal["docker_hub", "ghcr", "ecr", "acr", "gcr", "custom"]
    registry_url: str = Field(min_length=1, max_length=500)
    namespace: str = Field(default="", max_length=255)
    credential_secret_ref: str = Field(default="", max_length=500)
    status: Literal["active", "disabled"] = "active"
    config: dict[str, Any] = Field(default_factory=dict)

    _config_is_nonsecret = field_validator("config")(_validate_nonsecret_config)
    _credential_is_reference = field_validator("credential_secret_ref")(_validate_secret_reference)
    _registry_is_safe_url = field_validator("registry_url")(_validate_registry_url)


class RegistryConnectionUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    provider: Literal["docker_hub", "ghcr", "ecr", "acr", "gcr", "custom"] | None = None
    registry_url: str | None = Field(default=None, min_length=1, max_length=500)
    namespace: str | None = Field(default=None, max_length=255)
    credential_secret_ref: str | None = Field(default=None, max_length=500)
    status: Literal["active", "disabled"] | None = None
    config: dict[str, Any] | None = None

    @field_validator("config")
    @classmethod
    def config_is_nonsecret(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_nonsecret_config(value) if value is not None else None

    @field_validator("credential_secret_ref")
    @classmethod
    def credential_is_reference(cls, value: str | None) -> str | None:
        return _validate_secret_reference(value) if value is not None else None

    @field_validator("registry_url")
    @classmethod
    def registry_is_safe_url(cls, value: str | None) -> str | None:
        return _validate_registry_url(value) if value is not None else None


class EnvironmentCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    environment_type: Literal["development", "staging", "production", "custom"] = "development"
    status: Literal["active", "disabled", "archived"] = "active"
    config: dict[str, Any] = Field(default_factory=dict)

    _config_is_nonsecret = field_validator("config")(_validate_nonsecret_config)


class EnvironmentUpdatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=120)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)
    environment_type: Literal["development", "staging", "production", "custom"] | None = None
    status: Literal["active", "disabled", "archived"] | None = None
    config: dict[str, Any] | None = None

    @field_validator("config")
    @classmethod
    def config_is_nonsecret(cls, value: dict[str, Any] | None) -> dict[str, Any] | None:
        return _validate_nonsecret_config(value) if value is not None else None


class MigrationPlanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    strategy: Literal["none", "expand", "migrate", "contract"] = "none"
    migration_ids: list[str] = Field(default_factory=list)
    backward_compatible: bool = True
    requires_backup: bool = False
    export_offered: bool = False
    confirmation_required: bool = False
    stabilization_release: str = ""
    mapper_artifacts: list[str] = Field(default_factory=list)
    validation_checks: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_contract_safety(self) -> MigrationPlanPayload:
        if self.strategy == "contract":
            if not self.requires_backup or not self.export_offered or not self.confirmation_required:
                raise ValueError("Contract migrations require backup, export offer, and explicit confirmation.")
            if not self.stabilization_release:
                raise ValueError("Contract migrations require a prior stabilization release.")
        if self.strategy in {"expand", "migrate"} and not self.backward_compatible:
            raise ValueError("Expand and migrate phases must remain backward compatible.")
        return self


class ReleaseCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    registry_connection_id: str | None = None
    component: str = Field(pattern=r"^[a-z][a-z0-9-]*$", max_length=120)
    version: str = Field(min_length=1, max_length=120)
    artifact_type: Literal["container", "static"] = "container"
    artifact_ref: str = Field(min_length=1, max_length=1000)
    artifact_digest: str = Field(pattern=r"^sha256:[a-fA-F0-9]{64}$")
    channel: Literal["preview", "candidate", "stable"] = "candidate"
    contract_version: str = Field(default="v1", min_length=1, max_length=120)
    migration_plan: MigrationPlanPayload = Field(default_factory=MigrationPlanPayload)
    rollback_instructions: str = Field(default="", max_length=10000)
    status: Literal["candidate", "stable", "withdrawn"] = "candidate"
    metadata: dict[str, Any] = Field(default_factory=dict)

    _metadata_is_nonsecret = field_validator("metadata")(_validate_nonsecret_config)

    @model_validator(mode="after")
    def validate_immutable_artifact(self) -> ReleaseCreatePayload:
        if self.artifact_type == "container":
            expected_suffix = f"@{self.artifact_digest.lower()}"
            if not self.artifact_ref.lower().endswith(expected_suffix):
                raise ValueError("Container artifact_ref must end with its matching immutable digest.")
        return self


class DeploymentCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    environment_id: str = Field(min_length=1)
    release_id: str = Field(min_length=1)
    desired_state: dict[str, Any] = Field(default_factory=dict)
    notes: str = Field(default="", max_length=10000)

    _desired_state_is_nonsecret = field_validator("desired_state")(_validate_nonsecret_config)


class RuntimeCheckCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    org_id: str = Field(min_length=1)
    status: Literal["pass", "fail", "pending", "unknown"]
    checks: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    source: Literal["operator"] = "operator"
    observed_at: datetime | None = None

    @field_validator("observed_at")
    @classmethod
    def observation_is_not_future(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)
        if normalized > datetime.now(timezone.utc) + timedelta(minutes=5):
            raise ValueError("Observation time cannot be in the future.")
        return normalized


class RegistryConnectionData(BaseModel):
    registry_connection_id: str
    tenant_id: str
    org_id: str
    name: str
    provider: str
    registry_url: str
    namespace: str
    credential_secret_ref: str
    status: str
    config: dict[str, Any]
    created_by_user_id: str | None
    created_at: str
    updated_at: str


class EnvironmentData(BaseModel):
    environment_id: str
    tenant_id: str
    org_id: str
    name: str
    slug: str
    environment_type: str
    status: str
    config: dict[str, Any]
    created_by_user_id: str | None
    created_at: str
    updated_at: str


class ReleaseData(BaseModel):
    release_id: str
    tenant_id: str
    org_id: str
    registry_connection_id: str | None
    component: str
    version: str
    artifact_type: str
    artifact_ref: str
    artifact_digest: str
    channel: str
    contract_version: str
    migration_plan: dict[str, Any]
    rollback_instructions: str
    status: str
    metadata: dict[str, Any]
    created_by_user_id: str | None
    created_at: str


class DeploymentData(BaseModel):
    deployment_id: str
    tenant_id: str
    org_id: str
    environment_id: str
    release_id: str
    component: str
    status: str
    is_current: bool
    supersedes_deployment_id: str | None
    desired_state: dict[str, Any]
    notes: str
    created_by_user_id: str | None
    created_at: str
    superseded_at: str | None


class RuntimeCheckData(BaseModel):
    check_run_id: str
    tenant_id: str
    org_id: str
    deployment_id: str
    status: str
    checks: list[Any]
    summary: dict[str, Any]
    source: str
    observed_at: str
    recorded_by_user_id: str | None
    created_at: str


class RegistryConnectionListData(BaseModel):
    items: list[RegistryConnectionData]


class EnvironmentListData(BaseModel):
    items: list[EnvironmentData]


class ReleaseListData(BaseModel):
    items: list[ReleaseData]


class DeploymentListData(BaseModel):
    items: list[DeploymentData]


class RuntimeCheckListData(BaseModel):
    items: list[RuntimeCheckData]


COMMON_RESPONSES = {
    401: {"model": Envelope[dict[str, Any]], "description": "Authentication required."},
    403: {"model": Envelope[dict[str, Any]], "description": "Organization access denied."},
    404: {"model": Envelope[dict[str, Any]], "description": "Resource not found."},
    409: {"model": Envelope[dict[str, Any]], "description": "Control-plane state conflict."},
}


@router.post("/registry-connections", response_model=Envelope[RegistryConnectionData], responses=COMMON_RESPONSES)
def create_registry_connection(request: Request, payload: RegistryConnectionCreatePayload) -> dict[str, object]:
    auth = require_authentication(request)
    org_id = _resolve_org(auth, payload.org_id, write=True)
    try:
        item = deployment_store.create_registry_connection(
            tenant_id=auth.tenant_id,
            org_id=org_id,
            payload=payload.model_dump(exclude={"org_id"}),
            user_id=auth.user_id,
        )
    except DeploymentStoreConflictError as error:
        raise _conflict(error) from error
    return ok_response(request, data=item)


@router.get("/registry-connections", response_model=Envelope[RegistryConnectionListData], responses=COMMON_RESPONSES)
def list_registry_connections(request: Request, org_id: str | None = None) -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    return ok_response(request, data={"items": deployment_store.list_registry_connections(tenant_id=auth.tenant_id, org_id=resolved_org_id)})


@router.get("/registry-connections/{registry_connection_id}", response_model=Envelope[RegistryConnectionData], responses=COMMON_RESPONSES)
def get_registry_connection(request: Request, registry_connection_id: str, org_id: str | None = None) -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    item = deployment_store.get_registry_connection(tenant_id=auth.tenant_id, org_id=resolved_org_id, registry_connection_id=registry_connection_id)
    if item is None:
        raise _not_found("Registry connection")
    return ok_response(request, data=item)


@router.patch("/registry-connections/{registry_connection_id}", response_model=Envelope[RegistryConnectionData], responses=COMMON_RESPONSES)
def update_registry_connection(request: Request, registry_connection_id: str, payload: RegistryConnectionUpdatePayload) -> dict[str, object]:
    auth = require_authentication(request)
    org_id = _resolve_org(auth, payload.org_id, write=True)
    try:
        item = deployment_store.update_registry_connection(
            tenant_id=auth.tenant_id,
            org_id=org_id,
            registry_connection_id=registry_connection_id,
            changes=payload.model_dump(exclude={"org_id"}, exclude_none=True),
            user_id=auth.user_id,
        )
    except DeploymentStoreConflictError as error:
        raise _conflict(error) from error
    if item is None:
        raise _not_found("Registry connection")
    return ok_response(request, data=item)


@router.post("/environments", response_model=Envelope[EnvironmentData], responses=COMMON_RESPONSES)
def create_environment(request: Request, payload: EnvironmentCreatePayload) -> dict[str, object]:
    auth = require_authentication(request)
    org_id = _resolve_org(auth, payload.org_id, write=True)
    try:
        item = deployment_store.create_environment(tenant_id=auth.tenant_id, org_id=org_id, payload=payload.model_dump(exclude={"org_id"}), user_id=auth.user_id)
    except DeploymentStoreConflictError as error:
        raise _conflict(error) from error
    return ok_response(request, data=item)


@router.get("/environments", response_model=Envelope[EnvironmentListData], responses=COMMON_RESPONSES)
def list_environments(request: Request, org_id: str | None = None) -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    return ok_response(request, data={"items": deployment_store.list_environments(tenant_id=auth.tenant_id, org_id=resolved_org_id)})


@router.get("/environments/{environment_id}", response_model=Envelope[EnvironmentData], responses=COMMON_RESPONSES)
def get_environment(request: Request, environment_id: str, org_id: str | None = None) -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    item = deployment_store.get_environment(tenant_id=auth.tenant_id, org_id=resolved_org_id, environment_id=environment_id)
    if item is None:
        raise _not_found("Environment")
    return ok_response(request, data=item)


@router.patch("/environments/{environment_id}", response_model=Envelope[EnvironmentData], responses=COMMON_RESPONSES)
def update_environment(request: Request, environment_id: str, payload: EnvironmentUpdatePayload) -> dict[str, object]:
    auth = require_authentication(request)
    org_id = _resolve_org(auth, payload.org_id, write=True)
    try:
        item = deployment_store.update_environment(
            tenant_id=auth.tenant_id,
            org_id=org_id,
            environment_id=environment_id,
            changes=payload.model_dump(exclude={"org_id"}, exclude_none=True),
            user_id=auth.user_id,
        )
    except DeploymentStoreConflictError as error:
        raise _conflict(error) from error
    if item is None:
        raise _not_found("Environment")
    return ok_response(request, data=item)


@router.post("/releases", response_model=Envelope[ReleaseData], responses=COMMON_RESPONSES)
def create_release(request: Request, payload: ReleaseCreatePayload) -> dict[str, object]:
    auth = require_authentication(request)
    org_id = _resolve_org(auth, payload.org_id, write=True)
    try:
        item = deployment_store.create_release(
            tenant_id=auth.tenant_id,
            org_id=org_id,
            payload=payload.model_dump(exclude={"org_id"}),
            user_id=auth.user_id,
        )
    except DeploymentStoreConflictError as error:
        raise _conflict(error) from error
    except DeploymentStoreReferenceError as error:
        raise _reference_error(error) from error
    return ok_response(request, data=item)


@router.get("/releases", response_model=Envelope[ReleaseListData], responses=COMMON_RESPONSES)
def list_releases(request: Request, org_id: str | None = None, component: str = "", channel: str = "", status: str = "") -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    items = deployment_store.list_releases(tenant_id=auth.tenant_id, org_id=resolved_org_id, component=component, channel=channel, status=status)
    return ok_response(request, data={"items": items})


@router.get("/releases/{release_id}", response_model=Envelope[ReleaseData], responses=COMMON_RESPONSES)
def get_release(request: Request, release_id: str, org_id: str | None = None) -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    item = deployment_store.get_release(tenant_id=auth.tenant_id, org_id=resolved_org_id, release_id=release_id)
    if item is None:
        raise _not_found("Release")
    return ok_response(request, data=item)


@router.post("/deployments", response_model=Envelope[DeploymentData], responses=COMMON_RESPONSES)
def create_deployment(request: Request, payload: DeploymentCreatePayload) -> dict[str, object]:
    auth = require_authentication(request)
    org_id = _resolve_org(auth, payload.org_id, write=True)
    try:
        item = deployment_store.create_deployment(
            tenant_id=auth.tenant_id,
            org_id=org_id,
            payload=payload.model_dump(exclude={"org_id"}),
            user_id=auth.user_id,
        )
    except DeploymentStoreConflictError as error:
        raise _conflict(error) from error
    except DeploymentStoreReferenceError as error:
        raise _reference_error(error) from error
    return ok_response(request, data=item)


@router.get("/deployments", response_model=Envelope[DeploymentListData], responses=COMMON_RESPONSES)
def list_deployments(request: Request, org_id: str | None = None, environment_id: str = "", current_only: bool = False) -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    items = deployment_store.list_deployments(tenant_id=auth.tenant_id, org_id=resolved_org_id, environment_id=environment_id, current_only=current_only)
    return ok_response(request, data={"items": items})


@router.get("/deployments/{deployment_id}", response_model=Envelope[DeploymentData], responses=COMMON_RESPONSES)
def get_deployment(request: Request, deployment_id: str, org_id: str | None = None) -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    item = deployment_store.get_deployment(tenant_id=auth.tenant_id, org_id=resolved_org_id, deployment_id=deployment_id)
    if item is None:
        raise _not_found("Deployment")
    return ok_response(request, data=item)


@router.post("/deployments/{deployment_id}/runtime-check-runs", response_model=Envelope[RuntimeCheckData], responses=COMMON_RESPONSES)
def record_runtime_check(request: Request, deployment_id: str, payload: RuntimeCheckCreatePayload) -> dict[str, object]:
    auth = require_authentication(request)
    org_id = _resolve_org(auth, payload.org_id, write=True)
    try:
        item = deployment_store.record_runtime_check(
            tenant_id=auth.tenant_id,
            org_id=org_id,
            deployment_id=deployment_id,
            payload=payload.model_dump(exclude={"org_id"}),
            user_id=auth.user_id,
        )
    except DeploymentStoreReferenceError as error:
        raise _reference_error(error) from error
    return ok_response(request, data=item)


@router.get("/deployments/{deployment_id}/runtime-check-runs", response_model=Envelope[RuntimeCheckListData], responses=COMMON_RESPONSES)
def list_runtime_checks(
    request: Request,
    deployment_id: str,
    org_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, object]:
    auth = require_authentication(request)
    resolved_org_id = _resolve_org(auth, org_id)
    items = deployment_store.list_runtime_checks(
        tenant_id=auth.tenant_id,
        org_id=resolved_org_id,
        deployment_id=deployment_id,
        limit=limit,
    )
    if items is None:
        raise _not_found("Deployment")
    return ok_response(request, data={"items": items})
