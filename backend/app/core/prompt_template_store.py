from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, func, select, update

from app.core.db import SessionLocal
from app.core.db_models import PromptTemplateActivationModel, PromptTemplateVersionModel


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


SCOPE_PRIORITY = ["team", "division", "org", "tenant"]


class PromptTemplateStore:
    def _version_dict(self, row: PromptTemplateVersionModel) -> dict[str, Any]:
        return {
            "template_version_id": row.template_version_id,
            "tenant_id": row.tenant_id,
            "provider_id": row.provider_id,
            "template_kind": row.template_kind,
            "name": row.name,
            "version": row.version,
            "content": row.content,
            "created_by_user_id": row.created_by_user_id,
            "created_at": _dt_iso(row.created_at),
        }

    def _activation_dict(self, row: PromptTemplateActivationModel) -> dict[str, Any]:
        return {
            "activation_id": row.activation_id,
            "tenant_id": row.tenant_id,
            "scope_level": row.scope_level,
            "scope_id": row.scope_id,
            "provider_id": row.provider_id,
            "template_kind": row.template_kind,
            "template_version_id": row.template_version_id,
            "is_active": row.is_active,
            "reason": row.reason,
            "rolled_back_from_activation_id": row.rolled_back_from_activation_id,
            "created_by_user_id": row.created_by_user_id,
            "created_at": _dt_iso(row.created_at),
        }

    def create_version(
        self,
        *,
        tenant_id: str,
        provider_id: str,
        template_kind: str,
        name: str,
        content: str,
        created_by_user_id: str,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            max_version = db.scalar(
                select(func.max(PromptTemplateVersionModel.version))
                .where(PromptTemplateVersionModel.tenant_id == tenant_id)
                .where(PromptTemplateVersionModel.provider_id == provider_id)
                .where(PromptTemplateVersionModel.template_kind == template_kind)
                .where(PromptTemplateVersionModel.name == name)
            )
            row = PromptTemplateVersionModel(
                template_version_id=str(uuid4()),
                tenant_id=tenant_id,
                provider_id=provider_id,
                template_kind=template_kind,
                name=name,
                version=int(max_version or 0) + 1,
                content=content,
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._version_dict(row)

    def activate(
        self,
        *,
        tenant_id: str,
        scope_level: str,
        scope_id: str,
        provider_id: str,
        template_kind: str,
        template_version_id: str,
        reason: str,
        created_by_user_id: str,
        rolled_back_from_activation_id: str = "",
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            db.execute(
                update(PromptTemplateActivationModel)
                .where(PromptTemplateActivationModel.tenant_id == tenant_id)
                .where(PromptTemplateActivationModel.scope_level == scope_level)
                .where(PromptTemplateActivationModel.scope_id == scope_id)
                .where(PromptTemplateActivationModel.provider_id == provider_id)
                .where(PromptTemplateActivationModel.template_kind == template_kind)
                .values(is_active=False)
            )
            row = PromptTemplateActivationModel(
                activation_id=str(uuid4()),
                tenant_id=tenant_id,
                scope_level=scope_level,
                scope_id=scope_id,
                provider_id=provider_id,
                template_kind=template_kind,
                template_version_id=template_version_id,
                is_active=True,
                reason=reason,
                rolled_back_from_activation_id=rolled_back_from_activation_id,
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._activation_dict(row)

    def rollback(
        self,
        *,
        tenant_id: str,
        activation_id: str,
        created_by_user_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            source = db.scalar(
                select(PromptTemplateActivationModel)
                .where(PromptTemplateActivationModel.tenant_id == tenant_id)
                .where(PromptTemplateActivationModel.activation_id == activation_id)
            )
            if source is None:
                return None
            db.execute(
                update(PromptTemplateActivationModel)
                .where(PromptTemplateActivationModel.tenant_id == tenant_id)
                .where(PromptTemplateActivationModel.scope_level == source.scope_level)
                .where(PromptTemplateActivationModel.scope_id == source.scope_id)
                .where(PromptTemplateActivationModel.provider_id == source.provider_id)
                .where(PromptTemplateActivationModel.template_kind == source.template_kind)
                .values(is_active=False)
            )
            row = PromptTemplateActivationModel(
                activation_id=str(uuid4()),
                tenant_id=tenant_id,
                scope_level=source.scope_level,
                scope_id=source.scope_id,
                provider_id=source.provider_id,
                template_kind=source.template_kind,
                template_version_id=source.template_version_id,
                is_active=True,
                reason="rollback",
                rolled_back_from_activation_id=source.activation_id,
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._activation_dict(row)

    def list_versions(self, *, tenant_id: str, provider_id: str | None = None, template_kind: str | None = None) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(PromptTemplateVersionModel).where(PromptTemplateVersionModel.tenant_id == tenant_id)
            if provider_id:
                stmt = stmt.where(PromptTemplateVersionModel.provider_id == provider_id)
            if template_kind:
                stmt = stmt.where(PromptTemplateVersionModel.template_kind == template_kind)
            rows = db.scalars(stmt.order_by(desc(PromptTemplateVersionModel.created_at))).all()
            return [self._version_dict(item) for item in rows]

    def resolve_template(
        self,
        *,
        tenant_id: str,
        provider_id: str,
        template_kind: str,
        scopes: dict[str, str],
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            for level in SCOPE_PRIORITY:
                scope_id = str(scopes.get(level, "")).strip()
                if not scope_id:
                    continue
                activation = db.scalar(
                    select(PromptTemplateActivationModel)
                    .where(PromptTemplateActivationModel.tenant_id == tenant_id)
                    .where(PromptTemplateActivationModel.scope_level == level)
                    .where(PromptTemplateActivationModel.scope_id == scope_id)
                    .where(PromptTemplateActivationModel.provider_id == provider_id)
                    .where(PromptTemplateActivationModel.template_kind == template_kind)
                    .where(PromptTemplateActivationModel.is_active.is_(True))
                    .order_by(desc(PromptTemplateActivationModel.created_at))
                )
                if activation is None:
                    continue
                version = db.scalar(
                    select(PromptTemplateVersionModel).where(
                        PromptTemplateVersionModel.template_version_id == activation.template_version_id
                    )
                )
                if version is None:
                    continue
                return {
                    "scope_level": level,
                    "scope_id": scope_id,
                    "activation": self._activation_dict(activation),
                    "version": self._version_dict(version),
                }
            return None


prompt_template_store = PromptTemplateStore()
