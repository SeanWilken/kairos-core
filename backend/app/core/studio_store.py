from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.db_models import (
    StudioOrgInviteModel,
    StudioOrgOnboardingModel,
    StudioOrgSettingModel,
    StudioOrganizationMembershipModel,
    StudioOrganizationModel,
    StudioUserModel,
)


def _dt_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat()


class StudioStore:
    def _to_membership_dict(self, model: StudioOrganizationMembershipModel) -> dict[str, Any]:
        return {
            "membership_id": model.membership_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "user_id": model.user_id,
            "role": model.role,
            "status": model.status,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_user_dict(self, model: StudioUserModel) -> dict[str, Any]:
        return {
            "spec_version": "v0.2",
            "user_id": model.user_id,
            "tenant_id": model.tenant_id,
            "email": model.email,
            "phone": model.phone,
            "first_name": model.first_name,
            "last_name": model.last_name,
            "status": model.status,
            "is_global_admin": model.is_global_admin,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_org_dict(self, model: StudioOrganizationModel) -> dict[str, Any]:
        return {
            "spec_version": "v0.2",
            "org_id": model.org_id,
            "tenant_id": model.tenant_id,
            "name": model.name,
            "slug": model.slug,
            "mode": model.mode,
            "owner_user_id": model.owner_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_invite_dict(self, model: StudioOrgInviteModel) -> dict[str, Any]:
        return {
            "invite_id": model.invite_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "email": model.email,
            "role": model.role,
            "status": model.status,
            "invited_by_user_id": model.invited_by_user_id,
            "accepted_by_user_id": model.accepted_by_user_id,
            "expires_at": _dt_iso(model.expires_at) if model.expires_at else None,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_org_settings_dict(self, model: StudioOrgSettingModel) -> dict[str, Any]:
        return {
            "setting_id": model.setting_id,
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "settings": json.loads(model.settings_json or "{}"),
            "updated_by_user_id": model.updated_by_user_id,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def _to_onboarding_dict(self, model: StudioOrgOnboardingModel) -> dict[str, Any]:
        return {
            "tenant_id": model.tenant_id,
            "org_id": model.org_id,
            "status": model.status,
            "checklist": json.loads(model.checklist_json or "{}"),
            "completed_by_user_id": model.completed_by_user_id,
            "completed_at": _dt_iso(model.completed_at) if model.completed_at else None,
            "created_at": _dt_iso(model.created_at),
            "updated_at": _dt_iso(model.updated_at),
        }

    def get_user_by_email(self, *, tenant_id: str, email: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioUserModel).where(
                    StudioUserModel.tenant_id == tenant_id,
                    StudioUserModel.email == email,
                )
            )
            if model is None:
                return None
            return self._to_user_dict(model)

    def create_user(
        self,
        *,
        tenant_id: str,
        org_id: str | None,
        email: str,
        first_name: str,
        last_name: str,
        phone: str = "",
        status: str = "active",
        is_global_admin: bool = False,
        role: str = "member",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        user_id = str(uuid4())

        with SessionLocal() as db:
            user = StudioUserModel(
                user_id=user_id,
                tenant_id=tenant_id,
                email=email,
                phone=phone,
                first_name=first_name,
                last_name=last_name,
                status=status,
                is_global_admin=is_global_admin,
                created_at=now,
                updated_at=now,
            )
            db.add(user)

            membership: StudioOrganizationMembershipModel | None = None
            if org_id:
                membership = StudioOrganizationMembershipModel(
                    membership_id=str(uuid4()),
                    tenant_id=tenant_id,
                    org_id=org_id,
                    user_id=user_id,
                    role=role,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
                db.add(membership)

            db.commit()
            db.refresh(user)
            out = self._to_user_dict(user)
            out["membership"] = (
                self._to_membership_dict(membership) if membership is not None else None
            )
            return out

    def create_membership(
        self,
        *,
        tenant_id: str,
        org_id: str,
        user_id: str,
        role: str = "member",
        status: str = "active",
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        membership_id = str(uuid4())

        with SessionLocal() as db:
            membership = StudioOrganizationMembershipModel(
                membership_id=membership_id,
                tenant_id=tenant_id,
                org_id=org_id,
                user_id=user_id,
                role=role,
                status=status,
                created_at=now,
                updated_at=now,
            )
            db.add(membership)
            db.commit()
            db.refresh(membership)
            return self._to_membership_dict(membership)

    def get_membership(self, *, tenant_id: str, membership_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            membership = db.scalar(
                select(StudioOrganizationMembershipModel).where(
                    StudioOrganizationMembershipModel.tenant_id == tenant_id,
                    StudioOrganizationMembershipModel.membership_id == membership_id,
                )
            )
            if membership is None:
                return None
            return self._to_membership_dict(membership)

    def get_membership_by_org_user(
        self, *, tenant_id: str, org_id: str, user_id: str
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            membership = db.scalar(
                select(StudioOrganizationMembershipModel).where(
                    StudioOrganizationMembershipModel.tenant_id == tenant_id,
                    StudioOrganizationMembershipModel.org_id == org_id,
                    StudioOrganizationMembershipModel.user_id == user_id,
                )
            )
            if membership is None:
                return None
            return self._to_membership_dict(membership)

    def list_user_memberships(self, *, tenant_id: str, user_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(StudioOrganizationMembershipModel)
                .where(
                    StudioOrganizationMembershipModel.tenant_id == tenant_id,
                    StudioOrganizationMembershipModel.user_id == user_id,
                )
                .order_by(StudioOrganizationMembershipModel.created_at.desc())
            ).all()
            return [self._to_membership_dict(row) for row in rows]

    def update_membership(
        self,
        *,
        tenant_id: str,
        membership_id: str,
        role: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any] | None:
        with SessionLocal() as db:
            membership = db.scalar(
                select(StudioOrganizationMembershipModel).where(
                    StudioOrganizationMembershipModel.tenant_id == tenant_id,
                    StudioOrganizationMembershipModel.membership_id == membership_id,
                )
            )
            if membership is None:
                return None

            if role is not None:
                membership.role = role
            if status is not None:
                membership.status = status
            membership.updated_at = datetime.now(timezone.utc)

            db.add(membership)
            db.commit()
            db.refresh(membership)
            return self._to_membership_dict(membership)

    def list_users(self, *, tenant_id: str, org_id: str | None = None) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            if org_id:
                rows = db.scalars(
                    select(StudioUserModel)
                    .join(
                        StudioOrganizationMembershipModel,
                        StudioOrganizationMembershipModel.user_id == StudioUserModel.user_id,
                    )
                    .where(
                        StudioUserModel.tenant_id == tenant_id,
                        StudioOrganizationMembershipModel.org_id == org_id,
                    )
                    .order_by(StudioUserModel.created_at.desc())
                ).all()
            else:
                rows = db.scalars(
                    select(StudioUserModel)
                    .where(StudioUserModel.tenant_id == tenant_id)
                    .order_by(StudioUserModel.created_at.desc())
                ).all()

            return [self._to_user_dict(row) for row in rows]

    def get_user(self, *, tenant_id: str, user_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioUserModel).where(
                    StudioUserModel.tenant_id == tenant_id,
                    StudioUserModel.user_id == user_id,
                )
            )
            if model is None:
                return None
            return self._to_user_dict(model)

    def create_organization(
        self,
        *,
        tenant_id: str,
        name: str,
        slug: str,
        mode: str,
        owner_user_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        org_id = str(uuid4())

        with SessionLocal() as db:
            model = StudioOrganizationModel(
                org_id=org_id,
                tenant_id=tenant_id,
                name=name,
                slug=slug,
                mode=mode,
                owner_user_id=owner_user_id,
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_org_dict(model)

    def list_organizations(self, *, tenant_id: str) -> list[dict[str, Any]]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(StudioOrganizationModel)
                .where(StudioOrganizationModel.tenant_id == tenant_id)
                .order_by(StudioOrganizationModel.created_at.desc())
            ).all()
            return [self._to_org_dict(row) for row in rows]

    def get_organization(self, *, tenant_id: str, org_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioOrganizationModel).where(
                    StudioOrganizationModel.tenant_id == tenant_id,
                    StudioOrganizationModel.org_id == org_id,
                )
            )
            if model is None:
                return None
            return self._to_org_dict(model)

    def create_org_invite(
        self,
        *,
        tenant_id: str,
        org_id: str,
        email: str,
        role: str,
        invited_by_user_id: str,
        expires_at: datetime | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        invite_id = str(uuid4())

        with SessionLocal() as db:
            model = StudioOrgInviteModel(
                invite_id=invite_id,
                tenant_id=tenant_id,
                org_id=org_id,
                email=email,
                role=role,
                status="pending",
                invited_by_user_id=invited_by_user_id,
                accepted_by_user_id=None,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_invite_dict(model)

    def get_org_invite(self, *, tenant_id: str, invite_id: str) -> dict[str, Any] | None:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioOrgInviteModel).where(
                    StudioOrgInviteModel.tenant_id == tenant_id,
                    StudioOrgInviteModel.invite_id == invite_id,
                )
            )
            if model is None:
                return None
            return self._to_invite_dict(model)

    def accept_org_invite(
        self,
        *,
        tenant_id: str,
        invite_id: str,
        accepted_by_user_id: str,
    ) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)

        with SessionLocal() as db:
            invite = db.scalar(
                select(StudioOrgInviteModel).where(
                    StudioOrgInviteModel.tenant_id == tenant_id,
                    StudioOrgInviteModel.invite_id == invite_id,
                )
            )
            if invite is None:
                return None

            invite.status = "accepted"
            invite.accepted_by_user_id = accepted_by_user_id
            invite.updated_at = now
            db.add(invite)
            db.commit()
            db.refresh(invite)
            return self._to_invite_dict(invite)

    def get_org_settings(self, *, tenant_id: str, org_id: str) -> dict[str, Any]:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioOrgSettingModel).where(
                    StudioOrgSettingModel.tenant_id == tenant_id,
                    StudioOrgSettingModel.org_id == org_id,
                )
            )
            if model is None:
                now = datetime.now(timezone.utc)
                model = StudioOrgSettingModel(
                    setting_id=str(uuid4()),
                    tenant_id=tenant_id,
                    org_id=org_id,
                    settings_json="{}",
                    updated_by_user_id=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(model)
                db.commit()
                db.refresh(model)
            return self._to_org_settings_dict(model)

    def update_org_settings(
        self,
        *,
        tenant_id: str,
        org_id: str,
        patch: dict[str, Any],
        updated_by_user_id: str,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioOrgSettingModel).where(
                    StudioOrgSettingModel.tenant_id == tenant_id,
                    StudioOrgSettingModel.org_id == org_id,
                )
            )
            now = datetime.now(timezone.utc)
            if model is None:
                model = StudioOrgSettingModel(
                    setting_id=str(uuid4()),
                    tenant_id=tenant_id,
                    org_id=org_id,
                    settings_json="{}",
                    updated_by_user_id=updated_by_user_id,
                    created_at=now,
                    updated_at=now,
                )

            current = json.loads(model.settings_json or "{}")
            current.update(patch)
            model.settings_json = json.dumps(current)
            model.updated_by_user_id = updated_by_user_id
            model.updated_at = now
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_org_settings_dict(model)

    def get_org_onboarding(self, *, tenant_id: str, org_id: str) -> dict[str, Any]:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioOrgOnboardingModel).where(
                    StudioOrgOnboardingModel.tenant_id == tenant_id,
                    StudioOrgOnboardingModel.org_id == org_id,
                )
            )
            if model is None:
                now = datetime.now(timezone.utc)
                model = StudioOrgOnboardingModel(
                    tenant_id=tenant_id,
                    org_id=org_id,
                    status="pending",
                    checklist_json=json.dumps(
                        {
                            "organization_created": True,
                            "members_invited": False,
                            "settings_reviewed": False,
                            "persona_configured": False,
                        }
                    ),
                    completed_by_user_id=None,
                    completed_at=None,
                    created_at=now,
                    updated_at=now,
                )
                db.add(model)
                db.commit()
                db.refresh(model)
            return self._to_onboarding_dict(model)

    def complete_org_onboarding(
        self,
        *,
        tenant_id: str,
        org_id: str,
        completed_by_user_id: str,
        checklist_patch: dict[str, bool] | None = None,
    ) -> dict[str, Any]:
        with SessionLocal() as db:
            model = db.scalar(
                select(StudioOrgOnboardingModel).where(
                    StudioOrgOnboardingModel.tenant_id == tenant_id,
                    StudioOrgOnboardingModel.org_id == org_id,
                )
            )
            now = datetime.now(timezone.utc)
            if model is None:
                model = StudioOrgOnboardingModel(
                    tenant_id=tenant_id,
                    org_id=org_id,
                    status="pending",
                    checklist_json="{}",
                    completed_by_user_id=None,
                    completed_at=None,
                    created_at=now,
                    updated_at=now,
                )

            checklist = json.loads(model.checklist_json or "{}")
            if checklist_patch:
                checklist.update(checklist_patch)
            model.checklist_json = json.dumps(checklist)
            model.status = "completed"
            model.completed_by_user_id = completed_by_user_id
            model.completed_at = now
            model.updated_at = now
            db.add(model)
            db.commit()
            db.refresh(model)
            return self._to_onboarding_dict(model)


studio_store = StudioStore()
