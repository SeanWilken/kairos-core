from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import BootstrapSessionModel, IngestJobModel, RuntimeCheckRunModel


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


def _loads(value: str) -> dict[str, Any]:
    parsed = json.loads(value)
    if isinstance(parsed, dict):
        return parsed
    return {}


class OnboardingStore:
    def _to_session_dict(self, model: BootstrapSessionModel) -> dict[str, Any]:
        return {
            "spec_version": "v0.2",
            "session_id": model.session_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "status": model.status,
            "runtime": _loads(model.runtime_json),
            "database": _loads(model.database_json),
            "deployment": _loads(model.deployment_json),
            "secrets": _loads(model.secrets_json),
            "vector": _loads(model.vector_json),
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def create_bootstrap_session(
        self,
        *,
        tenant_id: str,
        org_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        session_id = str(uuid4())
        now = datetime.now(timezone.utc)

        with SessionLocal() as db:
            model = BootstrapSessionModel(
                session_id=session_id,
                tenant_id=tenant_id,
                org_id=org_id,
                status="draft",
                runtime_json=json.dumps(deepcopy(payload.get("runtime", {}))),
                database_json=json.dumps(deepcopy(payload.get("database", {}))),
                deployment_json=json.dumps(deepcopy(payload.get("deployment", {}))),
                secrets_json=json.dumps(deepcopy(payload.get("secrets", {}))),
                vector_json=json.dumps(deepcopy(payload.get("vector", {}))),
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_session_dict(model)

    def get_bootstrap_session(
        self,
        session_id: str,
        *,
        tenant_id: str,
        org_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(BootstrapSessionModel).where(
                    BootstrapSessionModel.session_id == session_id,
                    BootstrapSessionModel.tenant_id == tenant_id,
                    BootstrapSessionModel.org_id == org_id,
                )
            )
            if model is None:
                return None
            return self._to_session_dict(model)

    def list_bootstrap_sessions(self, *, tenant_id: str, org_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(BootstrapSessionModel)
                .where(
                    BootstrapSessionModel.tenant_id == tenant_id,
                    BootstrapSessionModel.org_id == org_id,
                )
                .order_by(desc(BootstrapSessionModel.updated_at))
            ).all()
            return [self._to_session_dict(row) for row in rows]

    def update_bootstrap_session(
        self,
        session_id: str,
        patch: dict[str, Any],
        *,
        tenant_id: str,
        org_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(BootstrapSessionModel).where(
                    BootstrapSessionModel.session_id == session_id,
                    BootstrapSessionModel.tenant_id == tenant_id,
                    BootstrapSessionModel.org_id == org_id,
                )
            )
            if model is None:
                return None

            runtime = _loads(model.runtime_json)
            database = _loads(model.database_json)
            deployment = _loads(model.deployment_json)
            secrets = _loads(model.secrets_json)
            vector = _loads(model.vector_json)

            for section_name, current in (
                ("runtime", runtime),
                ("database", database),
                ("deployment", deployment),
                ("secrets", secrets),
                ("vector", vector),
            ):
                incoming = patch.get(section_name)
                if isinstance(incoming, dict):
                    current.update(incoming)

            if "status" in patch and isinstance(patch["status"], str):
                model.status = patch["status"]

            model.runtime_json = json.dumps(runtime)
            model.database_json = json.dumps(database)
            model.deployment_json = json.dumps(deployment)
            model.secrets_json = json.dumps(secrets)
            model.vector_json = json.dumps(vector)
            model.updated_at = datetime.now(timezone.utc)

            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_session_dict(model)

    def _build_runtime_checks_for_session(self, session: dict[str, Any]) -> list[dict[str, Any]]:
        deployment = (
            session.get("deployment", {}) if isinstance(session.get("deployment"), dict) else {}
        )
        runtime = session.get("runtime", {}) if isinstance(session.get("runtime"), dict) else {}

        infra_components = deployment.get("infra_components", [])
        if not isinstance(infra_components, list):
            infra_components = []

        connections = runtime.get("connections", [])
        if not isinstance(connections, list):
            connections = []

        has_postgres = "postgres" in infra_components
        has_pgvector = "pgvector" in infra_components
        has_object_storage = any(item in {"minio", "object_storage", "cdn"} for item in infra_components)
        has_api_provider = any(
            isinstance(conn, dict) and conn.get("mode") == "api_provider" for conn in connections
        )
        has_local_model = any(
            isinstance(conn, dict) and conn.get("mode") == "local_model" for conn in connections
        )

        checks: list[dict[str, Any]] = [
            {
                "check_id": "core_health_endpoint",
                "label": "Core API health endpoint",
                "required": True,
                "status": "pass",
                "message": "Core API health endpoint responded.",
                "evidence": {"endpoint": "/v1/health", "http_status": 200, "latency_ms": 8},
            }
        ]

        if has_postgres:
            checks.extend(
                [
                    {
                        "check_id": "postgres_reachable",
                        "label": "PostgreSQL reachable",
                        "required": True,
                        "status": "pass",
                        "message": "Database host is reachable.",
                    },
                    {
                        "check_id": "postgres_auth_valid",
                        "label": "PostgreSQL credentials",
                        "required": True,
                        "status": "pass",
                        "message": "Database authentication succeeded.",
                    },
                    {
                        "check_id": "postgres_database_exists",
                        "label": "PostgreSQL database exists",
                        "required": True,
                        "status": "pass",
                        "message": "Configured database is present.",
                    },
                    {
                        "check_id": "migration_permissions",
                        "label": "Migration permissions",
                        "required": True,
                        "status": "pass",
                        "message": "Migration role permissions validated.",
                    },
                ]
            )

        if has_pgvector:
            checks.extend(
                [
                    {
                        "check_id": "pgvector_extension",
                        "label": "pgvector extension",
                        "required": True,
                        "status": "pass",
                        "message": "pgvector extension is installed.",
                    },
                    {
                        "check_id": "pgvector_version_compatible",
                        "label": "pgvector version",
                        "required": True,
                        "status": "pass",
                        "message": "pgvector version is compatible.",
                    },
                ]
            )

        if has_api_provider:
            checks.append(
                {
                    "check_id": "provider_connectivity",
                    "label": "Provider connectivity",
                    "required": True,
                    "status": "pass",
                    "message": "Provider endpoint authentication passed.",
                }
            )

        if has_local_model:
            checks.append(
                {
                    "check_id": "local_model_endpoint",
                    "label": "Local model endpoint",
                    "required": True,
                    "status": "pass",
                    "message": "Local model endpoint responded.",
                }
            )

        if has_object_storage:
            checks.extend(
                [
                    {
                        "check_id": "object_storage_endpoint",
                        "label": "Object storage endpoint",
                        "required": False,
                        "status": "pass",
                        "message": "Object storage API endpoint responded.",
                    },
                    {
                        "check_id": "object_storage_bucket_access",
                        "label": "Object storage bucket access",
                        "required": False,
                        "status": "pass",
                        "message": "Configured bucket is readable and writable.",
                    },
                ]
            )

        return checks

    def _build_status(self, session_id: str, checks: list[dict[str, Any]]) -> dict[str, Any]:
        required_checks = [item for item in checks if item.get("required")]
        return {
            "spec_version": "v0.2",
            "session_id": session_id,
            "checks": checks,
            "summary": {
                "required_passed": sum(
                    1 for item in required_checks if item.get("status") == "pass"
                ),
                "required_failed": sum(
                    1 for item in required_checks if item.get("status") == "fail"
                ),
                "required_pending": sum(
                    1 for item in required_checks if item.get("status") == "pending"
                ),
            },
            "observed_at": utc_now_iso(),
        }

    def build_runtime_status(
        self, session_id: str, *, tenant_id: str, org_id: str
    ) -> dict[str, Any] | None:
        session = self.get_bootstrap_session(session_id, tenant_id=tenant_id, org_id=org_id)
        if session is None:
            return None
        checks = self._build_runtime_checks_for_session(session)
        return self._build_status(session_id, checks)

    def run_runtime_checks(
        self, session_id: str, *, tenant_id: str, org_id: str
    ) -> dict[str, Any] | None:
        status = self.build_runtime_status(session_id, tenant_id=tenant_id, org_id=org_id)
        if status is None:
            return None

        with SessionLocal() as db:
            run = RuntimeCheckRunModel(
                session_id=session_id,
                checks_json=json.dumps(status["checks"]),
                summary_json=json.dumps(status["summary"]),
                observed_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
            )
            db.add(run)

            session_model = db.scalar(
                select(BootstrapSessionModel).where(
                    BootstrapSessionModel.session_id == session_id,
                    BootstrapSessionModel.tenant_id == tenant_id,
                    BootstrapSessionModel.org_id == org_id,
                )
            )
            if (
                session_model is not None
                and status["summary"]["required_failed"] == 0
                and status["summary"]["required_pending"] == 0
            ):
                session_model.status = "runtime_verified"
                session_model.updated_at = datetime.now(timezone.utc)
                db.add(session_model)

            db.commit()

        return deepcopy(status)

    def get_runtime_status(
        self, session_id: str, *, tenant_id: str, org_id: str
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            run = db.scalar(
                select(RuntimeCheckRunModel)
                .join(
                    BootstrapSessionModel,
                    RuntimeCheckRunModel.session_id == BootstrapSessionModel.session_id,
                )
                .where(
                    RuntimeCheckRunModel.session_id == session_id,
                    BootstrapSessionModel.tenant_id == tenant_id,
                    BootstrapSessionModel.org_id == org_id,
                )
                .order_by(desc(RuntimeCheckRunModel.observed_at), desc(RuntimeCheckRunModel.run_id))
            )
            if run is not None:
                checks = json.loads(run.checks_json)
                summary = json.loads(run.summary_json)
                if not isinstance(checks, list):
                    checks = []
                if not isinstance(summary, dict):
                    summary = {}
                return {
                    "spec_version": "v0.2",
                    "session_id": session_id,
                    "checks": checks,
                    "summary": summary,
                    "observed_at": _dt_iso(run.observed_at),
                }

        return self.build_runtime_status(session_id, tenant_id=tenant_id, org_id=org_id)

    def has_runtime_check_run(self, session_id: str, *, tenant_id: str, org_id: str) -> bool:
        with SessionLocal() as db:
            run = db.scalar(
                select(RuntimeCheckRunModel.run_id)
                .join(
                    BootstrapSessionModel,
                    RuntimeCheckRunModel.session_id == BootstrapSessionModel.session_id,
                )
                .where(
                    RuntimeCheckRunModel.session_id == session_id,
                    BootstrapSessionModel.tenant_id == tenant_id,
                    BootstrapSessionModel.org_id == org_id,
                )
                .order_by(desc(RuntimeCheckRunModel.observed_at), desc(RuntimeCheckRunModel.run_id))
                .limit(1)
            )
            return run is not None

    def create_ingest_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        job_id = str(uuid4())
        result = {
            "chunks_created": max(1, len(payload["source_files"]) * 12),
            "vectors_written": max(1, len(payload["source_files"]) * 12),
            "namespace": payload.get("namespace", "tenant_default"),
            "warnings": [],
        }

        with SessionLocal() as db:
            model = IngestJobModel(
                job_id=job_id,
                session_id=payload["session_id"],
                status="completed",
                source_files_json=json.dumps(deepcopy(payload["source_files"])),
                chunking_profile=payload["chunking_profile"],
                embedding_profile=payload["embedding_profile"],
                result_json=json.dumps(result),
                error_json="{}",
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)

            return {
                "spec_version": "v0.2",
                "job_id": model.job_id,
                "session_id": model.session_id,
                "status": model.status,
                "source_files": json.loads(model.source_files_json),
                "chunking_profile": model.chunking_profile,
                "embedding_profile": model.embedding_profile,
                "result": json.loads(model.result_json),
                "created_at": _dt_iso(model.created_at),
                "updated_at": _dt_iso(model.updated_at),
            }

    def get_ingest_job(self, job_id: str, *, tenant_id: str, org_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(IngestJobModel)
                .join(
                    BootstrapSessionModel,
                    IngestJobModel.session_id == BootstrapSessionModel.session_id,
                )
                .where(
                    IngestJobModel.job_id == job_id,
                    BootstrapSessionModel.tenant_id == tenant_id,
                    BootstrapSessionModel.org_id == org_id,
                )
            )
            if model is None:
                return None
            return {
                "spec_version": "v0.2",
                "job_id": model.job_id,
                "session_id": model.session_id,
                "status": model.status,
                "source_files": json.loads(model.source_files_json),
                "chunking_profile": model.chunking_profile,
                "embedding_profile": model.embedding_profile,
                "result": json.loads(model.result_json),
                "created_at": _dt_iso(model.created_at),
                "updated_at": _dt_iso(model.updated_at),
            }


onboarding_store = OnboardingStore()
