from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import desc, select

from app.core.db import SessionLocal
from app.core.db_models import (
    PersonaVersionHistoryModel,
    PersonaVersionModel,
    RoomCouncilConfigModel,
    RoomPersonaModel,
    StudioChannelMessageModel,
    StudioChannelModel,
    StudioChannelParticipantModel,
    StudioDivisionModel,
    StudioMeetingModel,
    StudioMeetingParticipantModel,
    StudioPersonaModel,
    StudioTaskAssignmentModel,
    StudioTaskModel,
    StudioTeamMembershipModel,
    StudioTeamModel,
    UserPersonaContextModel,
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
            "approval_status": model.approval_status,
            "approved_by_user_id": model.approved_by_user_id,
            "approved_at": _dt_iso(model.approved_at) if model.approved_at else None,
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

    def _to_persona_version_dict(self, model: PersonaVersionModel) -> dict[str, Any]:
        config: dict[str, Any] = {}
        try:
            loaded = json.loads(model.config_json)
            if isinstance(loaded, dict):
                config = loaded
        except Exception:
            config = {}

        return {
            "version_id": model.version_id,
            "tenant_id": model.tenant_id,
            "persona_id": model.persona_id,
            "version_major": model.version_major,
            "version_minor": model.version_minor,
            "version_patch": model.version_patch,
            "version_string": model.version_string,
            "config": config,
            "generated_prompt": model.generated_prompt,
            "token_count": model.token_count,
            "change_summary": model.change_summary,
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
        }

    def _to_user_persona_context_dict(self, model: UserPersonaContextModel) -> dict[str, Any]:
        strengths: list[str] = []
        weaknesses: list[str] = []
        context: dict[str, Any] = {}
        try:
            loaded_strengths = json.loads(model.user_strengths_json)
            if isinstance(loaded_strengths, list):
                strengths = [str(item) for item in loaded_strengths]
        except Exception:
            strengths = []
        try:
            loaded_weaknesses = json.loads(model.user_weaknesses_json)
            if isinstance(loaded_weaknesses, list):
                weaknesses = [str(item) for item in loaded_weaknesses]
        except Exception:
            weaknesses = []
        try:
            loaded_context = json.loads(model.context_json)
            if isinstance(loaded_context, dict):
                context = loaded_context
        except Exception:
            context = {}

        return {
            "context_id": model.context_id,
            "tenant_id": model.tenant_id,
            "user_id": model.user_id,
            "persona_id": model.persona_id,
            "user_strengths": strengths,
            "user_weaknesses": weaknesses,
            "autonomy_level": model.autonomy_level,
            "communication_preference": model.communication_preference,
            "detail_level": model.detail_level,
            "check_in_frequency": model.check_in_frequency,
            "context": context,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_council_config_dict(self, model: RoomCouncilConfigModel) -> dict[str, Any]:
        return {
            "config_id": model.config_id,
            "tenant_id": model.tenant_id,
            "room_id": model.room_id,
            "council_head_persona_id": model.council_head_persona_id,
            "council_mode": model.council_mode,
            "delay_before_orchestration_ms": model.delay_before_orchestration_ms,
            "show_reasoning_metadata": model.show_reasoning_metadata,
            "allow_parallel_responses": model.allow_parallel_responses,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_room_persona_dict(self, model: RoomPersonaModel) -> dict[str, Any]:
        return {
            "room_persona_id": model.room_persona_id,
            "tenant_id": model.tenant_id,
            "room_id": model.room_id,
            "persona_id": model.persona_id,
            "role_in_room": model.role_in_room,
            "sort_order": model.sort_order,
            "is_active": model.is_active,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
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
                approval_status="draft",
                approved_by_user_id=None,
                approved_at=None,
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

    def list_personas_any_org(self, *, tenant_id: str, enabled_only: bool = False) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(StudioPersonaModel).where(StudioPersonaModel.tenant_id == tenant_id)
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
            model.approval_status = "draft"
            model.approved_by_user_id = None
            model.approved_at = None
            model.updated_at = datetime.now(timezone.utc)

            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_persona_dict(model)

    def set_persona_approval(
        self,
        *,
        tenant_id: str,
        persona_id: str,
        approval_status: str,
        approved_by_user_id: str | None,
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

            model.approval_status = approval_status
            if approval_status == "approved":
                model.approved_by_user_id = approved_by_user_id
                model.approved_at = datetime.now(timezone.utc)
            else:
                model.approved_by_user_id = None
                model.approved_at = None
            model.updated_at = datetime.now(timezone.utc)
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_persona_dict(model)

    def _build_persona_generated_prompt(self, persona: dict[str, Any]) -> str:
        lines = [
            f"Name: {persona.get('name', '')}",
            f"Role: {persona.get('role', '')}",
            f"Scope: {persona.get('scope', '')}",
            f"Model Profile: {persona.get('model_profile', '')}",
        ]
        system_prompt = str(persona.get("system_prompt", "")).strip()
        if system_prompt:
            lines.append(system_prompt)
        data = persona.get("data", {})
        if isinstance(data, dict) and data:
            lines.append(json.dumps(data, ensure_ascii=True, sort_keys=True))
        return "\n\n".join(lines)

    def _compute_next_persona_version(
        self,
        *,
        db,
        tenant_id: str,
        persona_id: str,
        bump: str,
    ) -> tuple[int, int, int]:
        latest = db.scalar(
            select(PersonaVersionModel)
            .where(
                PersonaVersionModel.tenant_id == tenant_id,
                PersonaVersionModel.persona_id == persona_id,
            )
            .order_by(
                desc(PersonaVersionModel.version_major),
                desc(PersonaVersionModel.version_minor),
                desc(PersonaVersionModel.version_patch),
            )
        )
        if latest is None:
            return (1, 0, 0)

        major = latest.version_major
        minor = latest.version_minor
        patch = latest.version_patch
        if bump == "major":
            return (major + 1, 0, 0)
        if bump == "minor":
            return (major, minor + 1, 0)
        return (major, minor, patch + 1)

    def create_persona_version(
        self,
        *,
        tenant_id: str,
        persona_id: str,
        created_by_user_id: str | None,
        bump: str = "patch",
        change_summary: str = "",
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            persona_model = db.scalar(
                select(StudioPersonaModel).where(
                    StudioPersonaModel.tenant_id == tenant_id,
                    StudioPersonaModel.persona_id == persona_id,
                )
            )
            if persona_model is None:
                return None

            persona = self._to_persona_dict(persona_model)
            generated_prompt = self._build_persona_generated_prompt(persona)
            token_count = max(len(generated_prompt.split()), 0)
            major, minor, patch = self._compute_next_persona_version(
                db=db,
                tenant_id=tenant_id,
                persona_id=persona_id,
                bump=bump,
            )
            now = datetime.now(timezone.utc)
            version_model = PersonaVersionModel(
                version_id=str(uuid4()),
                tenant_id=tenant_id,
                persona_id=persona_id,
                version_major=major,
                version_minor=minor,
                version_patch=patch,
                version_string=f"{major}.{minor}.{patch}",
                config_json=json.dumps(persona),
                generated_prompt=generated_prompt,
                token_count=token_count,
                change_summary=change_summary,
                created_by_user_id=created_by_user_id,
                created_at=now,
            )
            db.add(version_model)
            db.commit()
            db.refresh(version_model)
            return self._to_persona_version_dict(version_model)

    def list_persona_versions(self, *, tenant_id: str, persona_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(PersonaVersionModel)
                .where(
                    PersonaVersionModel.tenant_id == tenant_id,
                    PersonaVersionModel.persona_id == persona_id,
                )
                .order_by(
                    desc(PersonaVersionModel.version_major),
                    desc(PersonaVersionModel.version_minor),
                    desc(PersonaVersionModel.version_patch),
                )
            ).all()
            return [self._to_persona_version_dict(row) for row in rows]

    def get_persona_version(
        self,
        *,
        tenant_id: str,
        persona_id: str,
        version_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(PersonaVersionModel).where(
                    PersonaVersionModel.tenant_id == tenant_id,
                    PersonaVersionModel.persona_id == persona_id,
                    PersonaVersionModel.version_id == version_id,
                )
            )
            return self._to_persona_version_dict(model) if model else None

    def get_latest_persona_version(self, *, tenant_id: str, persona_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(PersonaVersionModel)
                .where(
                    PersonaVersionModel.tenant_id == tenant_id,
                    PersonaVersionModel.persona_id == persona_id,
                )
                .order_by(
                    desc(PersonaVersionModel.version_major),
                    desc(PersonaVersionModel.version_minor),
                    desc(PersonaVersionModel.version_patch),
                )
            )
            return self._to_persona_version_dict(model) if model else None

    def rollback_persona_to_version(
        self,
        *,
        tenant_id: str,
        persona_id: str,
        version_id: str,
        changed_by_user_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            persona_model = db.scalar(
                select(StudioPersonaModel).where(
                    StudioPersonaModel.tenant_id == tenant_id,
                    StudioPersonaModel.persona_id == persona_id,
                )
            )
            version_model = db.scalar(
                select(PersonaVersionModel).where(
                    PersonaVersionModel.tenant_id == tenant_id,
                    PersonaVersionModel.persona_id == persona_id,
                    PersonaVersionModel.version_id == version_id,
                )
            )
            if persona_model is None or version_model is None:
                return None

            try:
                snapshot = json.loads(version_model.config_json)
            except Exception:
                return None
            if not isinstance(snapshot, dict):
                return None

            fields = {
                "name": "name",
                "slug": "slug",
                "role": "role",
                "scope": "scope",
                "enabled": "enabled",
                "model_profile": "model_profile",
                "system_prompt": "system_prompt",
            }
            now = datetime.now(timezone.utc)
            for key, attr_name in fields.items():
                if key in snapshot:
                    old = getattr(persona_model, attr_name)
                    new = snapshot[key]
                    if old != new:
                        db.add(
                            PersonaVersionHistoryModel(
                                history_id=str(uuid4()),
                                tenant_id=tenant_id,
                                version_id=version_id,
                                field_name=key,
                                old_value=str(old) if old is not None else None,
                                new_value=str(new) if new is not None else None,
                                changed_by_user_id=changed_by_user_id,
                                changed_at=now,
                            )
                        )
                    setattr(persona_model, attr_name, new)

            data = snapshot.get("data")
            if isinstance(data, dict):
                persona_model.persona_json = json.dumps(data)

            persona_model.approval_status = "draft"
            persona_model.approved_by_user_id = None
            persona_model.approved_at = None
            persona_model.updated_at = now
            db.add(persona_model)
            db.commit()
            db.refresh(persona_model)
            return self._to_persona_dict(persona_model)

    def upsert_user_persona_context(
        self,
        *,
        tenant_id: str,
        user_id: str,
        persona_id: str,
        user_strengths: list[str],
        user_weaknesses: list[str],
        autonomy_level: str,
        communication_preference: str,
        detail_level: str,
        check_in_frequency: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            model = db.scalar(
                select(UserPersonaContextModel).where(
                    UserPersonaContextModel.tenant_id == tenant_id,
                    UserPersonaContextModel.user_id == user_id,
                    UserPersonaContextModel.persona_id == persona_id,
                )
            )
            now = datetime.now(timezone.utc)
            if model is None:
                model = UserPersonaContextModel(
                    context_id=str(uuid4()),
                    tenant_id=tenant_id,
                    user_id=user_id,
                    persona_id=persona_id,
                    user_strengths_json=json.dumps(user_strengths),
                    user_weaknesses_json=json.dumps(user_weaknesses),
                    autonomy_level=autonomy_level,
                    communication_preference=communication_preference,
                    detail_level=detail_level,
                    check_in_frequency=check_in_frequency,
                    context_json=json.dumps(context),
                    created_at=now,
                    updated_at=now,
                )
            else:
                model.user_strengths_json = json.dumps(user_strengths)
                model.user_weaknesses_json = json.dumps(user_weaknesses)
                model.autonomy_level = autonomy_level
                model.communication_preference = communication_preference
                model.detail_level = detail_level
                model.check_in_frequency = check_in_frequency
                model.context_json = json.dumps(context)
                model.updated_at = now
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_user_persona_context_dict(model)

    def get_user_persona_context(
        self,
        *,
        tenant_id: str,
        user_id: str,
        persona_id: str,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(UserPersonaContextModel).where(
                    UserPersonaContextModel.tenant_id == tenant_id,
                    UserPersonaContextModel.user_id == user_id,
                    UserPersonaContextModel.persona_id == persona_id,
                )
            )
            return self._to_user_persona_context_dict(model) if model else None

    def list_user_persona_contexts(self, *, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(UserPersonaContextModel)
                .where(
                    UserPersonaContextModel.tenant_id == tenant_id,
                    UserPersonaContextModel.user_id == user_id,
                )
                .order_by(UserPersonaContextModel.updated_at.desc())
            ).all()
            return [self._to_user_persona_context_dict(row) for row in rows]

    def upsert_room_council_config(
        self,
        *,
        tenant_id: str,
        room_id: str,
        council_head_persona_id: str | None,
        council_mode: str,
        delay_before_orchestration_ms: int,
        show_reasoning_metadata: bool,
        allow_parallel_responses: bool,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            model = db.scalar(
                select(RoomCouncilConfigModel).where(
                    RoomCouncilConfigModel.tenant_id == tenant_id,
                    RoomCouncilConfigModel.room_id == room_id,
                )
            )
            now = datetime.now(timezone.utc)
            if model is None:
                model = RoomCouncilConfigModel(
                    config_id=str(uuid4()),
                    tenant_id=tenant_id,
                    room_id=room_id,
                    council_head_persona_id=council_head_persona_id,
                    council_mode=council_mode,
                    delay_before_orchestration_ms=delay_before_orchestration_ms,
                    show_reasoning_metadata=show_reasoning_metadata,
                    allow_parallel_responses=allow_parallel_responses,
                    created_at=now,
                    updated_at=now,
                )
            else:
                model.council_head_persona_id = council_head_persona_id
                model.council_mode = council_mode
                model.delay_before_orchestration_ms = delay_before_orchestration_ms
                model.show_reasoning_metadata = show_reasoning_metadata
                model.allow_parallel_responses = allow_parallel_responses
                model.updated_at = now
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_council_config_dict(model)

    def get_room_council_config(self, *, tenant_id: str, room_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(RoomCouncilConfigModel).where(
                    RoomCouncilConfigModel.tenant_id == tenant_id,
                    RoomCouncilConfigModel.room_id == room_id,
                )
            )
            return self._to_council_config_dict(model) if model else None

    def set_room_personas(
        self,
        *,
        tenant_id: str,
        room_id: str,
        persona_items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            existing_rows = db.scalars(
                select(RoomPersonaModel).where(
                    RoomPersonaModel.tenant_id == tenant_id,
                    RoomPersonaModel.room_id == room_id,
                )
            ).all()
            for row in existing_rows:
                db.delete(row)

            now = datetime.now(timezone.utc)
            created: list[RoomPersonaModel] = []
            for item in persona_items:
                persona_id = str(item.get("persona_id", "")).strip()
                if not persona_id:
                    continue
                row = RoomPersonaModel(
                    room_persona_id=str(uuid4()),
                    tenant_id=tenant_id,
                    room_id=room_id,
                    persona_id=persona_id,
                    role_in_room=str(item.get("role_in_room", "member")),
                    sort_order=int(item.get("sort_order", 0)),
                    is_active=bool(item.get("is_active", True)),
                    created_at=now,
                    updated_at=now,
                )
                db.add(row)
                created.append(row)

            db.commit()
            for row in created:
                db.refresh(row)
            return [self._to_room_persona_dict(row) for row in created]

    def list_room_personas(self, *, tenant_id: str, room_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(RoomPersonaModel)
                .where(
                    RoomPersonaModel.tenant_id == tenant_id,
                    RoomPersonaModel.room_id == room_id,
                )
                .order_by(RoomPersonaModel.sort_order.asc(), RoomPersonaModel.created_at.asc())
            ).all()
            return [self._to_room_persona_dict(row) for row in rows]

    def _to_task_dict(self, model: StudioTaskModel) -> dict[str, Any]:
        tags = []
        metadata = {}
        related_node_ids = []
        try:
            loaded = json.loads(model.tags_json or "[]")
            if isinstance(loaded, list):
                tags = [str(item) for item in loaded]
        except Exception:
            tags = []
        try:
            loaded = json.loads(model.metadata_json or "{}")
            if isinstance(loaded, dict):
                metadata = loaded
        except Exception:
            metadata = {}
        try:
            loaded = json.loads(model.related_node_ids_json or "[]")
            if isinstance(loaded, list):
                related_node_ids = [str(item) for item in loaded]
        except Exception:
            related_node_ids = []
        return {
            "task_id": model.task_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "team_id": model.team_id,
            "title": model.title,
            "description": model.description,
            "status": model.status,
            "visibility": model.visibility,
            "tags": tags,
            "metadata": metadata,
            "related_node_ids": related_node_ids,
            "channel_id": model.channel_id,
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

    def _to_meeting_dict(self, model: StudioMeetingModel) -> dict[str, Any]:
        tags = []
        metadata = {}
        agenda = []
        try:
            loaded = json.loads(model.tags_json or "[]")
            if isinstance(loaded, list):
                tags = [str(item) for item in loaded]
        except Exception:
            tags = []
        try:
            loaded = json.loads(model.metadata_json or "{}")
            if isinstance(loaded, dict):
                metadata = loaded
        except Exception:
            metadata = {}
        try:
            loaded = json.loads(model.agenda_json or "[]")
            if isinstance(loaded, list):
                agenda = [str(item) for item in loaded]
        except Exception:
            agenda = []
        return {
            "meeting_id": model.meeting_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "team_id": model.team_id,
            "channel_id": model.channel_id,
            "title": model.title,
            "description": model.description,
            "status": model.status,
            "scheduled_start_at": _dt_iso(model.scheduled_start_at),
            "scheduled_end_at": _dt_iso(model.scheduled_end_at),
            "timezone": model.timezone,
            "tags": tags,
            "metadata": metadata,
            "agenda": agenda,
            "created_by_user_id": model.created_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_meeting_participant_dict(self, model: StudioMeetingParticipantModel) -> dict[str, Any]:
        return {
            "participant_id": model.participant_id,
            "tenant_id": model.tenant_id,
            "meeting_id": model.meeting_id,
            "user_id": model.user_id,
            "role": model.role,
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
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        related_node_ids: list[str] | None = None,
        channel_id: str | None = None,
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
                tags_json=json.dumps(tags or []),
                metadata_json=json.dumps(metadata or {}),
                related_node_ids_json=json.dumps(related_node_ids or []),
                channel_id=channel_id,
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
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        related_node_ids: list[str] | None = None,
        channel_id: str | None = None,
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
            if tags is not None:
                row.tags_json = json.dumps(tags)
            if metadata is not None:
                row.metadata_json = json.dumps(metadata)
            if related_node_ids is not None:
                row.related_node_ids_json = json.dumps(related_node_ids)
            if channel_id is not None:
                row.channel_id = channel_id
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

    def create_meeting(
        self,
        *,
        tenant_id: str,
        org_id: str,
        team_id: str | None,
        channel_id: str | None,
        title: str,
        description: str,
        status: str,
        scheduled_start_at: datetime,
        scheduled_end_at: datetime,
        timezone_name: str,
        tags: list[str],
        metadata: dict[str, Any],
        agenda: list[str],
        created_by_user_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = StudioMeetingModel(
                meeting_id=str(uuid4()),
                tenant_id=tenant_id,
                org_id=org_id,
                team_id=team_id,
                channel_id=channel_id,
                title=title,
                description=description,
                status=status,
                scheduled_start_at=scheduled_start_at,
                scheduled_end_at=scheduled_end_at,
                timezone=timezone_name,
                tags_json=json.dumps(tags),
                metadata_json=json.dumps(metadata),
                agenda_json=json.dumps(agenda),
                created_by_user_id=created_by_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_meeting_dict(row)

    def list_meetings(
        self,
        *,
        tenant_id: str,
        org_id: str,
        team_id: str | None = None,
        channel_id: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            stmt = select(StudioMeetingModel).where(
                StudioMeetingModel.tenant_id == tenant_id,
                StudioMeetingModel.org_id == org_id,
            )
            if team_id is not None:
                stmt = stmt.where(StudioMeetingModel.team_id == team_id)
            if channel_id is not None:
                stmt = stmt.where(StudioMeetingModel.channel_id == channel_id)
            if status is not None:
                stmt = stmt.where(StudioMeetingModel.status == status)
            rows = db.scalars(stmt.order_by(desc(StudioMeetingModel.scheduled_start_at))).all()
            return [self._to_meeting_dict(row) for row in rows]

    def get_meeting(self, *, tenant_id: str, meeting_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioMeetingModel).where(
                    StudioMeetingModel.tenant_id == tenant_id,
                    StudioMeetingModel.meeting_id == meeting_id,
                )
            )
            return self._to_meeting_dict(row) if row else None

    def update_meeting(
        self,
        *,
        tenant_id: str,
        meeting_id: str,
        patch: dict[str, Any],
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            row = db.scalar(
                select(StudioMeetingModel).where(
                    StudioMeetingModel.tenant_id == tenant_id,
                    StudioMeetingModel.meeting_id == meeting_id,
                )
            )
            if row is None:
                return None
            if "title" in patch:
                row.title = str(patch.get("title") or row.title)
            if "description" in patch:
                row.description = str(patch.get("description") or "")
            if "status" in patch:
                row.status = str(patch.get("status") or row.status)
            if "team_id" in patch:
                row.team_id = patch.get("team_id")
            if "channel_id" in patch:
                row.channel_id = patch.get("channel_id")
            if "scheduled_start_at" in patch and isinstance(patch.get("scheduled_start_at"), datetime):
                row.scheduled_start_at = patch["scheduled_start_at"]
            if "scheduled_end_at" in patch and isinstance(patch.get("scheduled_end_at"), datetime):
                row.scheduled_end_at = patch["scheduled_end_at"]
            if "timezone" in patch:
                row.timezone = str(patch.get("timezone") or row.timezone)
            if "tags" in patch and isinstance(patch.get("tags"), list):
                row.tags_json = json.dumps([str(item) for item in patch["tags"]])
            if "metadata" in patch and isinstance(patch.get("metadata"), dict):
                row.metadata_json = json.dumps(patch["metadata"])
            if "agenda" in patch and isinstance(patch.get("agenda"), list):
                row.agenda_json = json.dumps([str(item) for item in patch["agenda"]])
            row.updated_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_meeting_dict(row)

    def create_meeting_participant(
        self,
        *,
        tenant_id: str,
        meeting_id: str,
        user_id: str,
        role: str,
        status: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            row = StudioMeetingParticipantModel(
                participant_id=str(uuid4()),
                tenant_id=tenant_id,
                meeting_id=meeting_id,
                user_id=user_id,
                role=role,
                status=status,
                created_at=now,
                updated_at=now,
            )
            db.add(row)
            db.commit()
            db.refresh(row)
            return self._to_meeting_participant_dict(row)

    def list_meeting_participants(self, *, tenant_id: str, meeting_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(StudioMeetingParticipantModel)
                .where(
                    StudioMeetingParticipantModel.tenant_id == tenant_id,
                    StudioMeetingParticipantModel.meeting_id == meeting_id,
                )
                .order_by(StudioMeetingParticipantModel.created_at.asc())
            ).all()
            return [self._to_meeting_participant_dict(row) for row in rows]


collaboration_store = CollaborationStore()
