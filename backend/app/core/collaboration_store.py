from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import (
    StudioChannelMessageModel,
    StudioChannelModel,
    StudioChannelParticipantModel,
    StudioDivisionModel,
    StudioPersonaModel,
    StudioTaskAssignmentModel,
    StudioTaskModel,
    StudioTeamMembershipModel,
    StudioTeamModel,
)


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class CollaborationStore:
    def _to_persona_dict(self, model: StudioPersonaModel) -> dict[str, Any]:
        data: dict[str, Any] = {}
        try:
            loaded = json.loads(model.persona_json)
            if isinstance(loaded, dict):
                data = loaded
        except Exception:
            data = {}

        return {
            "persona_id": model.persona_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "name": model.name,
            "slug": model.slug,
            "role": model.role,
            "scope": model.scope,
            "enabled": model.enabled,
            "model_profile": model.model_profile,
            "system_prompt": model.system_prompt,
            "data": data,
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_division_dict(self, model: StudioDivisionModel) -> dict[str, Any]:
        return {
            "division_id": model.division_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "name": model.name,
            "slug": model.slug,
            "description": model.description,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_team_dict(self, model: StudioTeamModel) -> dict[str, Any]:
        return {
            "team_id": model.team_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "division_id": model.division_id,
            "parent_team_id": model.parent_team_id,
            "name": model.name,
            "slug": model.slug,
            "description": model.description,
            "access_mode": model.access_mode,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_team_membership_dict(self, model: StudioTeamMembershipModel) -> dict[str, Any]:
        return {
            "team_membership_id": model.team_membership_id,
            "tenant_id": model.tenant_id,
            "team_id": model.team_id,
            "user_id": model.user_id,
            "role": model.role,
            "status": model.status,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_channel_dict(self, model: StudioChannelModel) -> dict[str, Any]:
        return {
            "channel_id": model.channel_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "team_id": model.team_id,
            "channel_type": model.channel_type,
            "name": model.name,
            "retention_days": model.retention_days,
            "response_policy": model.response_policy,
            "auto_respond": model.auto_respond,
            "responder_delay_seconds": model.responder_delay_seconds,
            "default_persona_id": model.default_persona_id,
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_message_dict(self, model: StudioChannelMessageModel) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        try:
            loaded = json.loads(model.metadata_json)
            if isinstance(loaded, dict):
                metadata = loaded
        except Exception:
            metadata = {}

        return {
            "message_id": model.message_id,
            "tenant_id": model.tenant_id,
            "channel_id": model.channel_id,
            "sender_user_id": model.sender_user_id,
            "content": model.content,
            "metadata": metadata,
            "created_at": _dt_iso(model.created_at),
        }

    def create_persona(
        self,
        *,
        tenant_id: str,
        org_id: str,
        name: str,
        slug: str,
        role: str,
        scope: str,
        enabled: bool,
        model_profile: str,
        system_prompt: str,
        data: dict[str, Any],
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            model = StudioPersonaModel(
                persona_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                name=name,
                slug=slug,
                role=role,
                scope=scope,
                enabled=enabled,
                model_profile=model_profile,
                system_prompt=system_prompt,
                persona_json=json.dumps(data),
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_persona_dict(model)

    def get_persona(self, *, tenant_id: str, persona_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioPersonaModel).where(
                    StudioPersonaModel.tenant_id == tenant_id,
                    StudioPersonaModel.persona_id == persona_id,
                )
            )
            return self._to_persona_dict(model) if model else None

    def list_personas(
        self, *, tenant_id: str, org_id: str, enabled_only: bool = False
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(StudioPersonaModel).where(
                StudioPersonaModel.tenant_id == tenant_id,
                StudioPersonaModel.org_id == org_id,
            )
            if enabled_only:
                stmt = stmt.where(StudioPersonaModel.enabled.is_(True))
            rows = db.scalars(stmt.order_by(StudioPersonaModel.created_at.asc())).all()
            return [self._to_persona_dict(row) for row in rows]

    def update_persona(
        self,
        *,
        tenant_id: str,
        persona_id: str,
        name: str | None = None,
        slug: str | None = None,
        role: str | None = None,
        scope: str | None = None,
        enabled: bool | None = None,
        model_profile: str | None = None,
        system_prompt: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioPersonaModel).where(
                    StudioPersonaModel.tenant_id == tenant_id,
                    StudioPersonaModel.persona_id == persona_id,
                )
            )
            if model is None:
                return None

            if name is not None:
                model.name = name
            if slug is not None:
                model.slug = slug
            if role is not None:
                model.role = role
            if scope is not None:
                model.scope = scope
            if enabled is not None:
                model.enabled = enabled
            if model_profile is not None:
                model.model_profile = model_profile
            if system_prompt is not None:
                model.system_prompt = system_prompt
            if data is not None:
                model.persona_json = json.dumps(data)
            model.updated_at = datetime.now(timezone.utc)

            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_persona_dict(model)

    def _to_task_dict(self, model: StudioTaskModel) -> dict[str, Any]:
        return {
            "task_id": model.task_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "team_id": model.team_id,
            "title": model.title,
            "description": model.description,
            "status": model.status,
            "visibility": model.visibility,
            "owner_user_id": model.owner_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_assignment_dict(self, model: StudioTaskAssignmentModel) -> dict[str, Any]:
        return {
            "assignment_id": model.assignment_id,
            "tenant_id": model.tenant_id,
            "task_id": model.task_id,
            "assignee_user_id": model.assignee_user_id,
            "status": model.status,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def create_division(
        self, *, tenant_id: str, org_id: str, name: str, slug: str, description: str = ""
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            model = StudioDivisionModel(
                division_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                name=name,
                slug=slug,
                description=description,
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_division_dict(model)

    def list_divisions(self, *, tenant_id: str, org_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(StudioDivisionModel)
                .where(
                    StudioDivisionModel.tenant_id == tenant_id,
                    StudioDivisionModel.org_id == org_id,
                )
                .order_by(StudioDivisionModel.created_at.asc())
            ).all()
            return [self._to_division_dict(row) for row in rows]

    def get_division(self, *, tenant_id: str, division_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioDivisionModel).where(
                    StudioDivisionModel.tenant_id == tenant_id,
                    StudioDivisionModel.division_id == division_id,
                )
            )
            return self._to_division_dict(model) if model else None

    def create_team(
        self,
        *,
        tenant_id: str,
        org_id: str,
        name: str,
        slug: str,
        description: str = "",
        access_mode: str = "internal",
        division_id: str | None = None,
        parent_team_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            model = StudioTeamModel(
                team_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                division_id=division_id,
                parent_team_id=parent_team_id,
                name=name,
                slug=slug,
                description=description,
                access_mode=access_mode,
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_team_dict(model)

    def list_teams(
        self,
        *,
        tenant_id: str,
        org_id: str,
        division_id: str | None = None,
        parent_team_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(StudioTeamModel).where(
                StudioTeamModel.tenant_id == tenant_id,
                StudioTeamModel.org_id == org_id,
            )
            if division_id is not None:
                stmt = stmt.where(StudioTeamModel.division_id == division_id)
            if parent_team_id is not None:
                stmt = stmt.where(StudioTeamModel.parent_team_id == parent_team_id)
            rows = db.scalars(stmt.order_by(StudioTeamModel.created_at.asc())).all()
            return [self._to_team_dict(row) for row in rows]

    def get_team(self, *, tenant_id: str, team_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioTeamModel).where(
                    StudioTeamModel.tenant_id == tenant_id,
                    StudioTeamModel.team_id == team_id,
                )
            )
            return self._to_team_dict(model) if model else None

    def create_team_membership(
        self, *, tenant_id: str, team_id: str, user_id: str, role: str, status: str = "active"
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            model = StudioTeamMembershipModel(
                team_membership_id=str(uuid4()),
                tenant_id=tenant_id,
                team_id=team_id,
                user_id=user_id,
                role=role,
                status=status,
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_team_membership_dict(model)

    def list_team_memberships(self, *, tenant_id: str, team_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(StudioTeamMembershipModel)
                .where(
                    StudioTeamMembershipModel.tenant_id == tenant_id,
                    StudioTeamMembershipModel.team_id == team_id,
                )
                .order_by(StudioTeamMembershipModel.created_at.asc())
            ).all()
            return [self._to_team_membership_dict(row) for row in rows]

    def get_team_membership_by_team_user(
        self, *, tenant_id: str, team_id: str, user_id: str
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioTeamMembershipModel).where(
                    StudioTeamMembershipModel.tenant_id == tenant_id,
                    StudioTeamMembershipModel.team_id == team_id,
                    StudioTeamMembershipModel.user_id == user_id,
                )
            )
            return self._to_team_membership_dict(row) if row else None

    def update_team_membership(
        self,
        *,
        tenant_id: str,
        team_membership_id: str,
        role: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioTeamMembershipModel).where(
                    StudioTeamMembershipModel.tenant_id == tenant_id,
                    StudioTeamMembershipModel.team_membership_id == team_membership_id,
                )
            )
            if row is None:
                return None
            if role is not None:
                row.role = role
            if status is not None:
                row.status = status
            row.updated_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_team_membership_dict(row)

    def is_user_in_team(self, *, tenant_id: str, team_id: str, user_id: str) -> bool:
        return (
            self.get_team_membership_by_team_user(
                tenant_id=tenant_id,
                team_id=team_id,
                user_id=user_id,
            )
            is not None
        )

    def create_channel(
        self,
        *,
        tenant_id: str,
        org_id: str,
        channel_type: str,
        name: str,
        created_by_user_id: str,
        retention_days: int,
        participant_user_ids: list[str],
        team_id: str | None = None,
        response_policy: str = "single_best",
        auto_respond: bool = True,
        responder_delay_seconds: int = 12,
        default_persona_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            channel = StudioChannelModel(
                channel_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                team_id=team_id,
                channel_type=channel_type,
                name=name,
                retention_days=retention_days,
                response_policy=response_policy,
                auto_respond=auto_respond,
                responder_delay_seconds=responder_delay_seconds,
                default_persona_id=default_persona_id,
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(channel)

            all_participants = sorted(set([created_by_user_id, *participant_user_ids]))
            for user_id in all_participants:
                db.add(
                    StudioChannelParticipantModel(
                        participant_id=str(uuid4()),
                        tenant_id=tenant_id,
                        channel_id=channel.channel_id,
                        user_id=user_id,
                        joined_at=now,
                    )
                )

            db.commit()
            db.refresh(channel)
            out = self._to_channel_dict(channel)
            out["participants"] = all_participants
            return out

    def list_channels(
        self,
        *,
        tenant_id: str,
        org_id: str,
        user_id: str,
        channel_type: str | None = None,
        team_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = (
                select(StudioChannelModel)
                .join(
                    StudioChannelParticipantModel,
                    StudioChannelParticipantModel.channel_id == StudioChannelModel.channel_id,
                )
                .where(
                    StudioChannelModel.tenant_id == tenant_id,
                    StudioChannelModel.org_id == org_id,
                    StudioChannelParticipantModel.user_id == user_id,
                )
            )
            if channel_type is not None:
                stmt = stmt.where(StudioChannelModel.channel_type == channel_type)
            if team_id is not None:
                stmt = stmt.where(StudioChannelModel.team_id == team_id)
            rows = db.scalars(stmt.order_by(desc(StudioChannelModel.updated_at))).all()
            return [self._to_channel_dict(row) for row in rows]

    def get_channel(self, *, tenant_id: str, channel_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioChannelModel).where(
                    StudioChannelModel.tenant_id == tenant_id,
                    StudioChannelModel.channel_id == channel_id,
                )
            )
            return self._to_channel_dict(row) if row else None

    def is_channel_participant(self, *, tenant_id: str, channel_id: str, user_id: str) -> bool:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioChannelParticipantModel.participant_id).where(
                    StudioChannelParticipantModel.tenant_id == tenant_id,
                    StudioChannelParticipantModel.channel_id == channel_id,
                    StudioChannelParticipantModel.user_id == user_id,
                )
            )
            return row is not None

    def create_channel_message(
        self,
        *,
        tenant_id: str,
        channel_id: str,
        sender_user_id: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = StudioChannelMessageModel(
                message_id=str(uuid4()),
                tenant_id=tenant_id,
                channel_id=channel_id,
                sender_user_id=sender_user_id,
                content=content,
                metadata_json=json.dumps(metadata or {}),
                created_at=now,
            )
            db.add(row)
            channel = db.scalar(
                select(StudioChannelModel).where(
                    StudioChannelModel.tenant_id == tenant_id,
                    StudioChannelModel.channel_id == channel_id,
                )
            )
            if channel is not None:
                channel.updated_at = now
                db.add(channel)
            db.commit()
            db.refresh(row)
            return self._to_message_dict(row)

    def update_channel_policy(
        self,
        *,
        tenant_id: str,
        channel_id: str,
        response_policy: str | None = None,
        auto_respond: bool | None = None,
        responder_delay_seconds: int | None = None,
        default_persona_id: str | None = None,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            channel = db.scalar(
                select(StudioChannelModel).where(
                    StudioChannelModel.tenant_id == tenant_id,
                    StudioChannelModel.channel_id == channel_id,
                )
            )
            if channel is None:
                return None

            if response_policy is not None:
                channel.response_policy = response_policy
            if auto_respond is not None:
                channel.auto_respond = auto_respond
            if responder_delay_seconds is not None:
                channel.responder_delay_seconds = responder_delay_seconds
            if default_persona_id is not None:
                channel.default_persona_id = default_persona_id
            channel.updated_at = datetime.now(timezone.utc)

            db.add(channel)
            db.commit()
            db.refresh(channel)
            return self._to_channel_dict(channel)

    def build_conversation_messages(
        self, *, tenant_id: str, channel_id: str, limit: int = 40
    ) -> list[dict[str, str]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(StudioChannelMessageModel)
                .where(
                    StudioChannelMessageModel.tenant_id == tenant_id,
                    StudioChannelMessageModel.channel_id == channel_id,
                )
                .order_by(desc(StudioChannelMessageModel.created_at))
                .limit(limit)
            ).all()

            ordered = list(reversed(rows))
            messages: list[dict[str, str]] = []
            for row in ordered:
                role = "assistant"
                if row.sender_user_id:
                    metadata = {}
                    try:
                        loaded = json.loads(row.metadata_json)
                        if isinstance(loaded, dict):
                            metadata = loaded
                    except Exception:
                        metadata = {}

                    sender_kind = metadata.get("sender_kind")
                    if sender_kind != "assistant":
                        role = "user"

                messages.append({"role": role, "content": row.content})
            return messages

    def list_channel_messages(
        self, *, tenant_id: str, channel_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(StudioChannelMessageModel)
                .where(
                    StudioChannelMessageModel.tenant_id == tenant_id,
                    StudioChannelMessageModel.channel_id == channel_id,
                )
                .order_by(desc(StudioChannelMessageModel.created_at))
                .limit(limit)
            ).all()
            ordered = list(reversed(rows))
            return [self._to_message_dict(row) for row in ordered]

    def create_task(
        self,
        *,
        tenant_id: str,
        org_id: str,
        owner_user_id: str,
        title: str,
        description: str,
        visibility: str,
        status: str = "todo",
        team_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = StudioTaskModel(
                task_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                team_id=team_id,
                title=title,
                description=description,
                status=status,
                visibility=visibility,
                owner_user_id=owner_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_task_dict(row)

    def get_task(self, *, tenant_id: str, task_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioTaskModel).where(
                    StudioTaskModel.tenant_id == tenant_id,
                    StudioTaskModel.task_id == task_id,
                )
            )
            return self._to_task_dict(row) if row else None

    def update_task(
        self,
        *,
        tenant_id: str,
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        status: str | None = None,
        visibility: str | None = None,
        team_id: str | None = None,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioTaskModel).where(
                    StudioTaskModel.tenant_id == tenant_id,
                    StudioTaskModel.task_id == task_id,
                )
            )
            if row is None:
                return None
            if title is not None:
                row.title = title
            if description is not None:
                row.description = description
            if status is not None:
                row.status = status
            if visibility is not None:
                row.visibility = visibility
            if team_id is not None:
                row.team_id = team_id
            row.updated_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_task_dict(row)

    def list_tasks(
        self,
        *,
        tenant_id: str,
        org_id: str,
        team_id: str | None = None,
        owner_user_id: str | None = None,
        visibility: str | None = None,
        assignee_user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(StudioTaskModel).where(
                StudioTaskModel.tenant_id == tenant_id,
                StudioTaskModel.org_id == org_id,
            )
            if team_id is not None:
                stmt = stmt.where(StudioTaskModel.team_id == team_id)
            if owner_user_id is not None:
                stmt = stmt.where(StudioTaskModel.owner_user_id == owner_user_id)
            if visibility is not None:
                stmt = stmt.where(StudioTaskModel.visibility == visibility)
            if assignee_user_id is not None:
                stmt = stmt.join(
                    StudioTaskAssignmentModel,
                    StudioTaskAssignmentModel.task_id == StudioTaskModel.task_id,
                ).where(StudioTaskAssignmentModel.assignee_user_id == assignee_user_id)
            rows = db.scalars(stmt.order_by(desc(StudioTaskModel.updated_at))).all()
            return [self._to_task_dict(row) for row in rows]

    def create_task_assignment(
        self,
        *,
        tenant_id: str,
        task_id: str,
        assignee_user_id: str,
        status: str = "active",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = StudioTaskAssignmentModel(
                assignment_id=str(uuid4()),
                tenant_id=tenant_id,
                task_id=task_id,
                assignee_user_id=assignee_user_id,
                status=status,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            task = db.scalar(
                select(StudioTaskModel).where(
                    StudioTaskModel.tenant_id == tenant_id,
                    StudioTaskModel.task_id == task_id,
                )
            )
            if task is not None:
                task.updated_at = now
                db.add(task)
            db.commit()
            db.refresh(row)
            return self._to_assignment_dict(row)

    def get_task_assignment_by_task_user(
        self, *, tenant_id: str, task_id: str, assignee_user_id: str
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioTaskAssignmentModel).where(
                    StudioTaskAssignmentModel.tenant_id == tenant_id,
                    StudioTaskAssignmentModel.task_id == task_id,
                    StudioTaskAssignmentModel.assignee_user_id == assignee_user_id,
                )
            )
            return self._to_assignment_dict(row) if row else None


collaboration_store = CollaborationStore()
