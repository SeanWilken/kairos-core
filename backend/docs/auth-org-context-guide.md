# Auth and Organization Context Guide

This guide explains how clients should authenticate, discover org scope, and switch org context safely.

## Recommended Client Flow

1. Login with email/password.
2. Call `GET /v1/auth/me` using the access token.
3. Read `data.org_options` and show org switcher if more than one option exists.
4. Use `POST /v1/auth/context/switch` when user selects a different org.
5. Replace in-memory access token/refresh token with returned values.

## Why This Matters

- Most Studio endpoints are org-scoped.
- If a request sends an org the user does not belong to, access should be denied.
- If an org identifier is invalid, API returns `404 STUDIO_ORG_NOT_FOUND`.

## Endpoints

### Login

`POST /v1/auth/login`

```json
{
  "email": "owner@example.com",
  "password": "Password123!"
}
```

In single-tenant mode, tenant can be inferred automatically.

### Current Context

`GET /v1/auth/me`

Returns:

- `data.auth.org_id` current token org scope
- `data.memberships` raw memberships
- `data.org_options` normalized org options for selectors

Global admin behavior:

- If the authenticated user is a global admin, `org_options` includes all tenant organizations (even without explicit org memberships), so clients can render org selector directly from `/v1/auth/me`.

`org_options` shape:

```json
[
  {
    "org_id": "<uuid>",
    "name": "My Org",
    "slug": "my-org",
    "role": "owner"
  }
]
```

### Switch Org Context

`POST /v1/auth/context/switch`

```json
{
  "org_id": "<org_id-or-slug-or-name>"
}
```

Response includes a new token pair with updated org context.

## Client Token Handling Best Practices

- Keep only one active access token per browser/app session.
- On context switch:
  - overwrite token pair atomically,
  - clear org-scoped caches,
  - refetch `/v1/auth/me` and key org-scoped resources.
- Include `Authorization: Bearer <access_token>` on every request.

## Handling Users/Personas Queries

`/v1/studio/users` and `/v1/studio/personas` support org-aware behavior:

- Prefer passing current `org_id` explicitly.
- If omitted, server defaults to JWT org context.
- Unknown org identifiers now return `404` instead of internal server errors.

## Invite Emails and Provider Configuration

Invite creation now triggers email send through tool runtime using configured provider.

`POST /v1/studio/invites` -> sends email transport + stores email/tool execution record.

Tool/email provider readiness:

- `GET /v1/tools/providers/status`

Configure provider in env:

- `TOOL_PROVIDER_EMAIL_SEND=smtp|sendgrid|email`
- SMTP: `EMAIL_SMTP_HOST`, `EMAIL_SMTP_PORT`, `EMAIL_SMTP_USERNAME`, `EMAIL_SMTP_PASSWORD`, `EMAIL_SMTP_USE_TLS`
- SendGrid: `SENDGRID_API_KEY`

## Starter Persona Payloads (OpenAI, Google, Anthropic)

Create with `POST /v1/studio/personas`.

### OpenAI Planner

```json
{
  "org_id": "<org_id>",
  "name": "OpenAI Planner",
  "slug": "openai-planner",
  "role": "planner",
  "scope": "organization",
  "enabled": true,
  "runtime_provider_id": "openai",
  "runtime_model_id": "gpt-4o-mini",
  "data": {
    "prompt_blocks": {
      "mission": "Turn requests into practical implementation plans.",
      "instructions": "Be concise and actionable."
    }
  }
}
```

### Gemini Visual Architect

```json
{
  "org_id": "<org_id>",
  "name": "Gemini Visual Architect",
  "slug": "gemini-visual-architect",
  "role": "design-architect",
  "scope": "organization",
  "enabled": true,
  "runtime_provider_id": "google",
  "runtime_model_id": "gemini-2.5-flash",
  "data": {
    "prompt_blocks": {
      "mission": "Design clear UI component structures and interaction patterns.",
      "instructions": "Prioritize readability and implementation clarity."
    }
  }
}
```

### Claude Frontend Reviewer

```json
{
  "org_id": "<org_id>",
  "name": "Claude Frontend Reviewer",
  "slug": "claude-frontend-reviewer",
  "role": "frontend-reviewer",
  "scope": "organization",
  "enabled": true,
  "runtime_provider_id": "anthropic",
  "runtime_model_id": "claude-sonnet-4-20250514",
  "data": {
    "prompt_blocks": {
      "mission": "Review frontend architecture and suggest maintainable component improvements.",
      "instructions": "Surface risks and pragmatic remediations."
    }
  }
}
```
