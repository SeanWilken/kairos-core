from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request

from app.core.security import decode_jwt


@dataclass
class AuthContext:
    user_id: str
    tenant_id: str
    org_id: str | None
    token_type: str
    token_id: str
    is_global_admin: bool
    roles: list[str]


def _extract_bearer_token(request: Request) -> str:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Authorization bearer token is required.",
                "details": {"reason_code": "AUTH_TOKEN_MISSING"},
            },
        )
    return header.split(" ", 1)[1].strip()


def _context_from_claims(claims: dict) -> AuthContext:
    user_id = claims.get("sub")
    tenant_id = claims.get("tenant_id")
    token_type = claims.get("token_type")
    token_id = claims.get("jti")
    org_id = claims.get("org_id")
    is_global_admin = bool(claims.get("is_global_admin", False))
    roles_raw = claims.get("roles", [])
    roles = [str(role) for role in roles_raw] if isinstance(roles_raw, list) else []

    if not isinstance(user_id, str) or not isinstance(tenant_id, str):
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Token payload is invalid.",
                "details": {"reason_code": "AUTH_TOKEN_INVALID"},
            },
        )
    if not isinstance(token_type, str) or not isinstance(token_id, str):
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Token payload is invalid.",
                "details": {"reason_code": "AUTH_TOKEN_INVALID"},
            },
        )

    org_value = org_id if isinstance(org_id, str) and org_id else None
    return AuthContext(
        user_id=user_id,
        tenant_id=tenant_id,
        org_id=org_value,
        token_type=token_type,
        token_id=token_id,
        is_global_admin=is_global_admin,
        roles=roles,
    )


def require_authentication(request: Request, *, require_org: bool = False) -> AuthContext:
    token = _extract_bearer_token(request)
    try:
        claims = decode_jwt(token)
    except ValueError as error:
        raise HTTPException(
            status_code=401,
            detail={
                "message": str(error),
                "details": {"reason_code": "AUTH_TOKEN_INVALID"},
            },
        ) from error

    context = _context_from_claims(claims)
    if context.token_type != "access":
        raise HTTPException(
            status_code=401,
            detail={
                "message": "Access token is required.",
                "details": {"reason_code": "AUTH_TOKEN_TYPE_INVALID"},
            },
        )

    if context.is_global_admin and not context.org_id:
        org_header = request.headers.get("X-Org-ID")
        if org_header:
            context.org_id = org_header

    if require_org and not context.org_id and not context.is_global_admin:
        raise HTTPException(
            status_code=403,
            detail={
                "message": "Organization scope is required.",
                "details": {"reason_code": "ORG_SCOPE_REQUIRED"},
            },
        )

    request.state.user_id = context.user_id
    request.state.tenant_id = context.tenant_id
    request.state.org_id = context.org_id
    request.state.auth = context
    return context


def require_roles(context: AuthContext, allowed: set[str]) -> None:
    if context.is_global_admin:
        return
    if any(role in allowed for role in context.roles):
        return
    raise HTTPException(
        status_code=403,
        detail={
            "message": "Insufficient role for this action.",
            "details": {"reason_code": "ROLE_FORBIDDEN", "required": sorted(allowed)},
        },
    )
