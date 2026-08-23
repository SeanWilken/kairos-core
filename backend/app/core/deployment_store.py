from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError

from app.core.db import SessionLocal
from app.core.db_models import (
    AuditEventModel,
    DeploymentDeclarationModel,
    DeploymentEnvironmentModel,
    DeploymentRegistryConnectionModel,
    DeploymentReleaseModel,
    DeploymentRuntimeCheckRunModel,
)


class DeploymentStoreConflictError(ValueError):
    pass


class DeploymentStoreReferenceError(ValueError):
    pass


def _dt_iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat() if value is not None else None


def _load_json(value: str, fallback: dict[str, Any] | list[Any]) -> dict[str, Any] | list[Any]:
    try:
        loaded = json.loads(value)
    except Exception:
        return fallback
    if isinstance(fallback, dict) and isinstance(loaded, dict):
        return loaded
    if isinstance(fallback, list) and isinstance(loaded, list):
        return loaded
    return fallback


def _add_audit_event(
    db: Any,
    *,
    tenant_id: str,
    org_id: str,
    user_id: str,
    action: str,
    resource_type: str,
    resource_id: str,
) -> None:
    db.add(
        AuditEventModel(
            audit_event_id=str(uuid4()),
            tenant_id=tenant_id,
            org_id=org_id,
            actor_type="user",
            actor_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            room_id="",
            orchestration_run_id="",
            decision="allowed",
            reason_code="DEPLOYMENT_CONTROL_DECLARATIVE_CHANGE",
            policy_version="v1",
            metadata_json=json.dumps({"org_id": org_id, "execution_performed": False}),
            created_at=datetime.now(timezone.utc),
        )
    )


class DeploymentStore:
    def _registry_to_dict(self, row: DeploymentRegistryConnectionModel) -> dict[str, Any]:
        return {
            "registry_connection_id": row.registry_connection_id,
            "tenant_id": row.tenant_id,
            "org_id": row.org_id,
            "name": row.name,
            "provider": row.provider,
            "registry_url": row.registry_url,
            "namespace": row.namespace,
            "credential_secret_ref": row.credential_secret_ref,
            "status": row.status,
            "config": _load_json(row.config_json, {}),
            "created_by_user_id": row.created_by_user_id,
            "created_at": _dt_iso(row.created_at),
            "updated_at": _dt_iso(row.updated_at),
        }

    def _environment_to_dict(self, row: DeploymentEnvironmentModel) -> dict[str, Any]:
        return {
            "environment_id": row.environment_id,
            "tenant_id": row.tenant_id,
            "org_id": row.org_id,
            "name": row.name,
            "slug": row.slug,
            "environment_type": row.environment_type,
            "status": row.status,
            "config": _load_json(row.config_json, {}),
            "created_by_user_id": row.created_by_user_id,
            "created_at": _dt_iso(row.created_at),
            "updated_at": _dt_iso(row.updated_at),
        }

    def _release_to_dict(self, row: DeploymentReleaseModel) -> dict[str, Any]:
        return {
            "release_id": row.release_id,
            "tenant_id": row.tenant_id,
            "org_id": row.org_id,
            "registry_connection_id": row.registry_connection_id,
            "component": row.component,
            "version": row.version,
            "artifact_type": row.artifact_type,
            "artifact_ref": row.artifact_ref,
            "artifact_digest": row.artifact_digest,
            "channel": row.channel,
            "contract_version": row.contract_version,
            "migration_plan": _load_json(row.migration_plan_json, {}),
            "rollback_instructions": row.rollback_instructions,
            "status": row.status,
            "metadata": _load_json(row.metadata_json, {}),
            "created_by_user_id": row.created_by_user_id,
            "created_at": _dt_iso(row.created_at),
        }

    def _deployment_to_dict(self, row: DeploymentDeclarationModel) -> dict[str, Any]:
        return {
            "deployment_id": row.deployment_id,
            "tenant_id": row.tenant_id,
            "org_id": row.org_id,
            "environment_id": row.environment_id,
            "release_id": row.release_id,
            "component": row.component,
            "status": row.status,
            "is_current": row.is_current,
            "supersedes_deployment_id": row.supersedes_deployment_id,
            "desired_state": _load_json(row.desired_state_json, {}),
            "notes": row.notes,
            "created_by_user_id": row.created_by_user_id,
            "created_at": _dt_iso(row.created_at),
            "superseded_at": _dt_iso(row.superseded_at),
        }

    def _check_to_dict(self, row: DeploymentRuntimeCheckRunModel) -> dict[str, Any]:
        return {
            "check_run_id": row.check_run_id,
            "tenant_id": row.tenant_id,
            "org_id": row.org_id,
            "deployment_id": row.deployment_id,
            "status": row.status,
            "checks": _load_json(row.checks_json, []),
            "summary": _load_json(row.summary_json, {}),
            "source": row.source,
            "observed_at": _dt_iso(row.observed_at),
            "recorded_by_user_id": row.recorded_by_user_id,
            "created_at": _dt_iso(row.created_at),
        }

    def create_registry_connection(self, *, tenant_id: str, org_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        row = DeploymentRegistryConnectionModel(
            registry_connection_id=str(uuid4()),
            tenant_id=tenant_id,
            org_id=org_id,
            name=str(payload["name"]),
            provider=str(payload["provider"]),
            registry_url=str(payload["registry_url"]),
            namespace=str(payload.get("namespace", "")),
            credential_secret_ref=str(payload.get("credential_secret_ref", "")),
            status=str(payload.get("status", "active")),
            config_json=json.dumps(payload.get("config", {})),
            created_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        with SessionLocal() as db:
            db.add(row)
            _add_audit_event(
                db,
                tenant_id=tenant_id,
                org_id=org_id,
                user_id=user_id,
                action="deployment.registry_connection.created",
                resource_type="deployment_registry_connection",
                resource_id=row.registry_connection_id,
            )
            try:
                db.commit()
            except IntegrityError as error:
                db.rollback()
                raise DeploymentStoreConflictError("Registry connection name already exists.") from error
            db.refresh(row)
            return self._registry_to_dict(row)

    def list_registry_connections(self, *, tenant_id: str, org_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(DeploymentRegistryConnectionModel)
                .where(DeploymentRegistryConnectionModel.tenant_id == tenant_id)
                .where(DeploymentRegistryConnectionModel.org_id == org_id)
                .order_by(desc(DeploymentRegistryConnectionModel.created_at))
            ).all()
            return [self._registry_to_dict(row) for row in rows]

    def get_registry_connection(self, *, tenant_id: str, org_id: str, registry_connection_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(DeploymentRegistryConnectionModel)
                .where(DeploymentRegistryConnectionModel.tenant_id == tenant_id)
                .where(DeploymentRegistryConnectionModel.org_id == org_id)
                .where(DeploymentRegistryConnectionModel.registry_connection_id == registry_connection_id)
            )
            return self._registry_to_dict(row) if row is not None else None

    def update_registry_connection(self, *, tenant_id: str, org_id: str, registry_connection_id: str, changes: dict[str, Any], user_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(DeploymentRegistryConnectionModel)
                .where(DeploymentRegistryConnectionModel.tenant_id == tenant_id)
                .where(DeploymentRegistryConnectionModel.org_id == org_id)
                .where(DeploymentRegistryConnectionModel.registry_connection_id == registry_connection_id)
            )
            if row is None:
                return None
            for key in ("name", "provider", "registry_url", "namespace", "credential_secret_ref", "status"):
                if key in changes:
                    setattr(row, key, str(changes[key]))
            if "config" in changes:
                row.config_json = json.dumps(changes["config"])
            row.updated_at = datetime.now(timezone.utc)
            _add_audit_event(
                db,
                tenant_id=tenant_id,
                org_id=org_id,
                user_id=user_id,
                action="deployment.registry_connection.updated",
                resource_type="deployment_registry_connection",
                resource_id=row.registry_connection_id,
            )
            try:
                db.commit()
            except IntegrityError as error:
                db.rollback()
                raise DeploymentStoreConflictError("Registry connection name already exists.") from error
            db.refresh(row)
            return self._registry_to_dict(row)

    def create_environment(self, *, tenant_id: str, org_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        row = DeploymentEnvironmentModel(
            environment_id=str(uuid4()),
            tenant_id=tenant_id,
            org_id=org_id,
            name=str(payload["name"]),
            slug=str(payload["slug"]),
            environment_type=str(payload.get("environment_type", "development")),
            status=str(payload.get("status", "active")),
            config_json=json.dumps(payload.get("config", {})),
            created_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )
        with SessionLocal() as db:
            db.add(row)
            _add_audit_event(
                db,
                tenant_id=tenant_id,
                org_id=org_id,
                user_id=user_id,
                action="deployment.environment.created",
                resource_type="deployment_environment",
                resource_id=row.environment_id,
            )
            try:
                db.commit()
            except IntegrityError as error:
                db.rollback()
                raise DeploymentStoreConflictError("Environment slug already exists.") from error
            db.refresh(row)
            return self._environment_to_dict(row)

    def list_environments(self, *, tenant_id: str, org_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(DeploymentEnvironmentModel)
                .where(DeploymentEnvironmentModel.tenant_id == tenant_id)
                .where(DeploymentEnvironmentModel.org_id == org_id)
                .order_by(desc(DeploymentEnvironmentModel.created_at))
            ).all()
            return [self._environment_to_dict(row) for row in rows]

    def get_environment(self, *, tenant_id: str, org_id: str, environment_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(DeploymentEnvironmentModel)
                .where(DeploymentEnvironmentModel.tenant_id == tenant_id)
                .where(DeploymentEnvironmentModel.org_id == org_id)
                .where(DeploymentEnvironmentModel.environment_id == environment_id)
            )
            return self._environment_to_dict(row) if row is not None else None

    def update_environment(self, *, tenant_id: str, org_id: str, environment_id: str, changes: dict[str, Any], user_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(DeploymentEnvironmentModel)
                .where(DeploymentEnvironmentModel.tenant_id == tenant_id)
                .where(DeploymentEnvironmentModel.org_id == org_id)
                .where(DeploymentEnvironmentModel.environment_id == environment_id)
            )
            if row is None:
                return None
            for key in ("name", "slug", "environment_type", "status"):
                if key in changes:
                    setattr(row, key, str(changes[key]))
            if "config" in changes:
                row.config_json = json.dumps(changes["config"])
            row.updated_at = datetime.now(timezone.utc)
            _add_audit_event(
                db,
                tenant_id=tenant_id,
                org_id=org_id,
                user_id=user_id,
                action="deployment.environment.updated",
                resource_type="deployment_environment",
                resource_id=row.environment_id,
            )
            try:
                db.commit()
            except IntegrityError as error:
                db.rollback()
                raise DeploymentStoreConflictError("Environment slug already exists.") from error
            db.refresh(row)
            return self._environment_to_dict(row)

    def create_release(self, *, tenant_id: str, org_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        with SessionLocal() as db:
            registry_connection_id = payload.get("registry_connection_id")
            if registry_connection_id:
                registry = db.scalar(
                    select(DeploymentRegistryConnectionModel)
                    .where(DeploymentRegistryConnectionModel.tenant_id == tenant_id)
                    .where(DeploymentRegistryConnectionModel.org_id == org_id)
                    .where(DeploymentRegistryConnectionModel.registry_connection_id == registry_connection_id)
                )
                if registry is None:
                    raise DeploymentStoreReferenceError("Registry connection not found in this organization.")
            row = DeploymentReleaseModel(
                release_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                registry_connection_id=str(registry_connection_id) if registry_connection_id else None,
                component=str(payload["component"]),
                version=str(payload["version"]),
                artifact_type=str(payload.get("artifact_type", "container")),
                artifact_ref=str(payload["artifact_ref"]),
                artifact_digest=str(payload["artifact_digest"]),
                channel=str(payload.get("channel", "candidate")),
                contract_version=str(payload.get("contract_version", "v1")),
                migration_plan_json=json.dumps(payload.get("migration_plan", {})),
                rollback_instructions=str(payload.get("rollback_instructions", "")),
                status=str(payload.get("status", "candidate")),
                metadata_json=json.dumps(payload.get("metadata", {})),
                created_by_user_id=user_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            _add_audit_event(
                db,
                tenant_id=tenant_id,
                org_id=org_id,
                user_id=user_id,
                action="deployment.release.created",
                resource_type="deployment_release",
                resource_id=row.release_id,
            )
            try:
                db.commit()
            except IntegrityError as error:
                db.rollback()
                raise DeploymentStoreConflictError("Component version already exists.") from error
            db.refresh(row)
            return self._release_to_dict(row)

    def list_releases(self, *, tenant_id: str, org_id: str, component: str = "", channel: str = "", status: str = "") -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = (
                select(DeploymentReleaseModel)
                .where(DeploymentReleaseModel.tenant_id == tenant_id)
                .where(DeploymentReleaseModel.org_id == org_id)
            )
            if component:
                stmt = stmt.where(DeploymentReleaseModel.component == component)
            if channel:
                stmt = stmt.where(DeploymentReleaseModel.channel == channel)
            if status:
                stmt = stmt.where(DeploymentReleaseModel.status == status)
            rows = db.scalars(stmt.order_by(desc(DeploymentReleaseModel.created_at))).all()
            return [self._release_to_dict(row) for row in rows]

    def get_release(self, *, tenant_id: str, org_id: str, release_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(DeploymentReleaseModel)
                .where(DeploymentReleaseModel.tenant_id == tenant_id)
                .where(DeploymentReleaseModel.org_id == org_id)
                .where(DeploymentReleaseModel.release_id == release_id)
            )
            return self._release_to_dict(row) if row is not None else None

    def create_deployment(self, *, tenant_id: str, org_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            environment = db.scalar(
                select(DeploymentEnvironmentModel)
                .where(DeploymentEnvironmentModel.tenant_id == tenant_id)
                .where(DeploymentEnvironmentModel.org_id == org_id)
                .where(DeploymentEnvironmentModel.environment_id == payload["environment_id"])
            )
            release = db.scalar(
                select(DeploymentReleaseModel)
                .where(DeploymentReleaseModel.tenant_id == tenant_id)
                .where(DeploymentReleaseModel.org_id == org_id)
                .where(DeploymentReleaseModel.release_id == payload["release_id"])
            )
            if environment is None or release is None:
                raise DeploymentStoreReferenceError("Environment or release not found in this organization.")
            if release.status == "withdrawn":
                raise DeploymentStoreReferenceError("Withdrawn releases cannot be declared for deployment.")
            previous = db.scalar(
                select(DeploymentDeclarationModel)
                .where(DeploymentDeclarationModel.tenant_id == tenant_id)
                .where(DeploymentDeclarationModel.org_id == org_id)
                .where(DeploymentDeclarationModel.environment_id == environment.environment_id)
                .where(DeploymentDeclarationModel.component == release.component)
                .where(DeploymentDeclarationModel.is_current.is_(True))
            )
            if previous is not None:
                previous.is_current = False
                previous.status = "superseded"
                previous.superseded_at = now
            row = DeploymentDeclarationModel(
                deployment_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                environment_id=environment.environment_id,
                release_id=release.release_id,
                component=release.component,
                status="declared",
                is_current=True,
                supersedes_deployment_id=previous.deployment_id if previous is not None else None,
                desired_state_json=json.dumps(payload.get("desired_state", {})),
                notes=str(payload.get("notes", "")),
                created_by_user_id=user_id,
                created_at=now,
            )
            db.add(row)
            _add_audit_event(
                db,
                tenant_id=tenant_id,
                org_id=org_id,
                user_id=user_id,
                action="deployment.declaration.created",
                resource_type="deployment_declaration",
                resource_id=row.deployment_id,
            )
            try:
                db.commit()
            except IntegrityError as error:
                db.rollback()
                raise DeploymentStoreConflictError("Current deployment changed concurrently.") from error
            db.refresh(row)
            return self._deployment_to_dict(row)

    def list_deployments(self, *, tenant_id: str, org_id: str, environment_id: str = "", current_only: bool = False) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = (
                select(DeploymentDeclarationModel)
                .where(DeploymentDeclarationModel.tenant_id == tenant_id)
                .where(DeploymentDeclarationModel.org_id == org_id)
            )
            if environment_id:
                stmt = stmt.where(DeploymentDeclarationModel.environment_id == environment_id)
            if current_only:
                stmt = stmt.where(DeploymentDeclarationModel.is_current.is_(True))
            rows = db.scalars(stmt.order_by(desc(DeploymentDeclarationModel.created_at))).all()
            return [self._deployment_to_dict(row) for row in rows]

    def get_deployment(self, *, tenant_id: str, org_id: str, deployment_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(DeploymentDeclarationModel)
                .where(DeploymentDeclarationModel.tenant_id == tenant_id)
                .where(DeploymentDeclarationModel.org_id == org_id)
                .where(DeploymentDeclarationModel.deployment_id == deployment_id)
            )
            return self._deployment_to_dict(row) if row is not None else None

    def record_runtime_check(self, *, tenant_id: str, org_id: str, deployment_id: str, payload: dict[str, Any], user_id: str) -> dict[str, Any]:
        with SessionLocal() as db:
            deployment = db.scalar(
                select(DeploymentDeclarationModel)
                .where(DeploymentDeclarationModel.tenant_id == tenant_id)
                .where(DeploymentDeclarationModel.org_id == org_id)
                .where(DeploymentDeclarationModel.deployment_id == deployment_id)
            )
            if deployment is None:
                raise DeploymentStoreReferenceError("Deployment not found in this organization.")
            row = DeploymentRuntimeCheckRunModel(
                check_run_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                deployment_id=deployment_id,
                status=str(payload.get("status", "unknown")),
                checks_json=json.dumps(payload.get("checks", [])),
                summary_json=json.dumps(payload.get("summary", {})),
                source=str(payload.get("source", "external")),
                observed_at=payload.get("observed_at") or datetime.now(timezone.utc),
                recorded_by_user_id=user_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            _add_audit_event(
                db,
                tenant_id=tenant_id,
                org_id=org_id,
                user_id=user_id,
                action="deployment.runtime_check.recorded",
                resource_type="deployment_runtime_check",
                resource_id=row.check_run_id,
            )
            db.commit()
            db.refresh(row)
            return self._check_to_dict(row)

    def list_runtime_checks(self, *, tenant_id: str, org_id: str, deployment_id: str, limit: int) -> list[dict[str, Any]] | None:
        with SessionLocal() as db:
            deployment = db.scalar(
                select(DeploymentDeclarationModel.deployment_id)
                .where(DeploymentDeclarationModel.tenant_id == tenant_id)
                .where(DeploymentDeclarationModel.org_id == org_id)
                .where(DeploymentDeclarationModel.deployment_id == deployment_id)
            )
            if deployment is None:
                return None
            rows = db.scalars(
                select(DeploymentRuntimeCheckRunModel)
                .where(DeploymentRuntimeCheckRunModel.tenant_id == tenant_id)
                .where(DeploymentRuntimeCheckRunModel.org_id == org_id)
                .where(DeploymentRuntimeCheckRunModel.deployment_id == deployment_id)
                .order_by(desc(DeploymentRuntimeCheckRunModel.observed_at))
                .limit(limit)
            ).all()
            return [self._check_to_dict(row) for row in rows]


deployment_store = DeploymentStore()
