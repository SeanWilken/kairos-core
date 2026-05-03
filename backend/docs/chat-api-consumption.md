# Chat API Consumption Guide

This guide covers the current APIs required to wire a dedicated chat application to Kairos Studio chat and realtime orchestration.

## Base URL and Auth

- Base URL: `http://<host>:<port>/v1`
- Auth type: Bearer JWT access token
- Tenant context header is required for auth endpoints and should be consistently sent:
  - `X-Tenant-ID: <tenant_id>`

## 1) Register or Login

### Register

`POST /v1/auth/register`

```json
{
  "email": "you@example.com",
  "password": "strong-password",
  "first_name": "First",
  "last_name": "Last",
  "tenant_id": "tenant0"
}
```

### Login

`POST /v1/auth/login`

```json
{
  "email": "you@example.com",
  "password": "strong-password",
  "tenant_id": "tenant0"
}
```

Use `data.access_token` from the response as `Authorization: Bearer <token>`.

## 2) Create Organization (if needed)

`POST /v1/studio/organizations`

```json
{
  "name": "My Org",
  "slug": "my-org",
  "mode": "team"
}
```

## 3) Create Personas (OpenAI + Google example)

`POST /v1/studio/personas`

OpenAI persona:

```json
{
  "org_id": "<org_id>",
  "name": "OpenAI Agent",
  "slug": "openai-agent",
  "role": "assistant",
  "scope": "organization",
  "enabled": true,
  "runtime_provider_id": "openai",
  "runtime_model_id": "gpt-4o-mini",
  "data": {
    "prompt_blocks": {
      "mission": "Provide clear implementation guidance."
    }
  }
}
```

Google persona:

```json
{
  "org_id": "<org_id>",
  "name": "Gemini Agent",
  "slug": "gemini-agent",
  "role": "assistant",
  "scope": "organization",
  "enabled": true,
  "runtime_provider_id": "google",
  "runtime_model_id": "gemini-2.5-flash",
  "data": {
    "prompt_blocks": {
      "mission": "Focus on concise practical next steps."
    }
  }
}
```

## 4) Create Channel

`POST /v1/studio/channels`

```json
{
  "org_id": "<org_id>",
  "channel_type": "org",
  "name": "chat-room",
  "retention_days": 30,
  "response_policy": "single_best",
  "auto_respond": true,
  "responder_delay_seconds": 1
}
```

## 5) Configure Council Room (optional multi-agent)

### Attach personas to room

`PUT /v1/studio/channels/{channel_id}/personas`

```json
{
  "personas": [
    { "persona_id": "<openai_persona_id>", "role_in_room": "head", "sort_order": 1 },
    { "persona_id": "<google_persona_id>", "role_in_room": "member", "sort_order": 2 }
  ]
}
```

### Council config

`PATCH /v1/studio/channels/{channel_id}/council-config`

```json
{
  "council_mode": "summarized",
  "delay_before_orchestration_ms": 0,
  "allow_parallel_responses": true
}
```

Note: parallel execution is additionally controlled by org setting `orchestration_parallel_enabled`.

Additional orchestration tuning org settings:

- `orchestration_auto_escalation_enabled` (default `true`)
  - when `false`, server will not auto-upgrade `single_best` requests to council summary mode.
- `orchestration_max_personas` (default `4`, capped `1..8`)
  - limits active personas participating in a council turn.

## 6) Send Chat (HTTP)

`POST /v1/studio/channels/{channel_id}/chat`

```json
{
  "content": "Compare implementation tradeoffs for this feature.",
  "mode": "single_best"
}
```

For explicit persona:

```json
{
  "content": "Review this as the OpenAI agent.",
  "persona_id": "<openai_persona_id>",
  "mode": "single_best"
}
```

## 7) Realtime WebSocket

Connect:

- `/v1/realtime/ws?token=<access_token>`

Send message:

```json
{
  "action": "chat.send",
  "channel_id": "<channel_id>",
  "content": "Please synthesize next steps.",
  "mode": "council"
}
```

Common incoming events:

- `system.connected`
- `chat.message.user.created`
- `orchestration.policy.resolved`
- `orchestration.run.created`
- `council.delayed_start`
- `chat.response.completed` (single best)
- `council.response` (summarized council)
- `chat.response.awaiting_approval` (fallback approval required)

Action-aware routing behaviors:

- `@personaHandle` mention
  - server can auto-route to mentioned persona (`single_best`) when no explicit `persona_id` is supplied.
- `/focus` or `/flow`
  - server treats as workflow actions and may route to `summarized` council mode when multiple active personas exist.
- `orchestration.policy.resolved`
  - includes action classification metadata:
    - `action_type`
    - `action_reason`
    - `resolved_persona_id`

## 8) Helpful Read APIs

- `GET /v1/studio/channels?org_id=<org_id>`
- `GET /v1/studio/channels/{channel_id}/messages`
- `GET /v1/system/audit/events?room_id=<channel_id>`
- `GET /v1/system/fallback-approvals?status=pending`
- `GET /v1/tools/providers/status` (tool provider readiness for image/email)

## 9) Prompt Template Overrides (Provider/Scope)

You can override persona system prompts by provider and hierarchy.

- Create version: `POST /v1/system/prompt-templates/versions`
- Activate at scope: `POST /v1/system/prompt-templates/activations`
- Resolve: `GET /v1/system/prompt-templates/resolve`
- Rollback: `POST /v1/system/prompt-templates/activations/{activation_id}/rollback`

Template variables supported currently include:

- `{{persona.name}}`
- `{{persona.role}}`
- `{{persona.scope}}`
- `{{persona.base_prompt}}`

## 10) Provider Configuration Checklist

For two-provider testing (OpenAI + Google):

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `LLM_LIVE_MODE=true` (if you want live provider calls; otherwise simulation paths are used)
