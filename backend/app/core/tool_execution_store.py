from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import EmailMessageModel, ToolExecutionModel


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class ToolExecutionStore:
    def create_execution(
        self,
        *,
        tenant_id: str,
        org_id: str,
        tool_id: str,
        provider_id: str,
        model_id: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any],
        created_by_user_id: str,
        status: str = "completed",
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            row = ToolExecutionModel(
                execution_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                tool_id=tool_id,
                provider_id=provider_id,
                model_id=model_id,
                status=status,
                input_json=json.dumps(input_payload or {}),
                output_json=json.dumps(output_payload or {}),
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.commit()
            return {
                "execution_id": row.execution_id,
                "tool_id": row.tool_id,
                "provider_id": row.provider_id,
                "model_id": row.model_id,
                "status": row.status,
                "input": input_payload,
                "output": output_payload,
                "created_at": _dt_iso(row.created_at),
            }

    def list_executions(self, *, tenant_id: str, org_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(ToolExecutionModel)
                .where(ToolExecutionModel.tenant_id == tenant_id)
                .where(ToolExecutionModel.org_id == org_id)
                .order_by(desc(ToolExecutionModel.created_at))
                .limit(limit)
            ).all()
            items: list[dict[str, Any]] = []
            for row in rows:
                items.append(
                    {
                        "execution_id": row.execution_id,
                        "tool_id": row.tool_id,
                        "provider_id": row.provider_id,
                        "model_id": row.model_id,
                        "status": row.status,
                        "created_at": _dt_iso(row.created_at),
                    }
                )
            return items

    def create_email(
        self,
        *,
        tenant_id: str,
        org_id: str,
        sender: str,
        recipients: list[str],
        subject: str,
        body: str,
        created_by_user_id: str,
        status: str = "sent",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            row = EmailMessageModel(
                email_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                direction="outbound",
                sender=sender,
                recipients_json=json.dumps(recipients),
                subject=subject,
                body=body,
                status=status,
                metadata_json=json.dumps(metadata or {"provider": "email-simulated"}),
                created_by_user_id=created_by_user_id,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.commit()
            return {
                "email_id": row.email_id,
                "direction": row.direction,
                "sender": row.sender,
                "recipients": recipients,
                "subject": row.subject,
                "body": row.body,
                "status": row.status,
                "created_at": _dt_iso(row.created_at),
            }

    def list_emails(self, *, tenant_id: str, org_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(EmailMessageModel)
                .where(EmailMessageModel.tenant_id == tenant_id)
                .where(EmailMessageModel.org_id == org_id)
                .order_by(desc(EmailMessageModel.created_at))
                .limit(limit)
            ).all()
            items: list[dict[str, Any]] = []
            for row in rows:
                recipients = json.loads(row.recipients_json or "[]")
                items.append(
                    {
                        "email_id": row.email_id,
                        "direction": row.direction,
                        "sender": row.sender,
                        "recipients": recipients if isinstance(recipients, list) else [],
                        "subject": row.subject,
                        "body": row.body,
                        "status": row.status,
                        "created_at": _dt_iso(row.created_at),
                    }
                )
            return items


tool_execution_store = ToolExecutionStore()
