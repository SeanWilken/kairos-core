from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.db_models import AuthRefreshTokenModel, StudioUserCredentialModel


class AuthStore:
    def get_password_hash(self, *, user_id: str) -> str | None:
        with SessionLocal() as db:
            credential = db.scalar(
                select(StudioUserCredentialModel).where(
                    StudioUserCredentialModel.user_id == user_id
                )
            )
            return credential.password_hash if credential is not None else None

    def upsert_password_hash(self, *, user_id: str, password_hash: str) -> None:
        now = datetime.now(timezone.utc)
        with SessionLocal() as db:
            credential = db.scalar(
                select(StudioUserCredentialModel).where(
                    StudioUserCredentialModel.user_id == user_id
                )
            )
            if credential is None:
                credential = StudioUserCredentialModel(
                    user_id=user_id,
                    password_hash=password_hash,
                    created_at=now,
                    updated_at=now,
                )
            else:
                credential.password_hash = password_hash
                credential.updated_at = now
            db.add(credential)
            db.commit()

    def create_refresh_token(
        self,
        *,
        token_id: str,
        user_id: str,
        tenant_id: str,
        org_id: str | None,
        token_hash: str,
        expires_at: datetime,
    ) -> None:
        with SessionLocal() as db:
            row = AuthRefreshTokenModel(
                token_id=token_id,
                user_id=user_id,
                tenant_id=tenant_id,
                org_id=org_id or "",
                token_hash=token_hash,
                expires_at=expires_at,
                revoked_at=None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(row)
            db.commit()

    def get_refresh_token(self, *, token_id: str) -> AuthRefreshTokenModel | None:
        with SessionLocal() as db:
            return db.scalar(
                select(AuthRefreshTokenModel).where(AuthRefreshTokenModel.token_id == token_id)
            )

    def revoke_refresh_token(self, *, token_id: str) -> None:
        with SessionLocal() as db:
            row = db.scalar(
                select(AuthRefreshTokenModel).where(AuthRefreshTokenModel.token_id == token_id)
            )
            if row is None:
                return
            row.revoked_at = datetime.now(timezone.utc)
            db.add(row)
            db.commit()


auth_store = AuthStore()
