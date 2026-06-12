# Chat API Consumption Guide

This guide covers the current APIs required to wire a dedicated chat application to MyAI Studio chat and realtime orchestration.

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

Role requirement note:

- `channel_type` values `org` and `team` are admin-managed and require `owner`/`admin` (or global admin) roles.
- Member-facing clients should gate room creation UX accordingly, or use member-allowed channel patterns where applicable.

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
  "mode": "single_best",
  "response_type": "conversation",
  "auto_execute_tools": true,
  "persona_overrides": {},
  "strict_validation": false
}
```

Optional user-inserted structured content blocks:

```json
{
  "content": "Draft launch assets",
  "content_blocks": [
    { "type": "markdown", "markdown": "## Launch brief" },
    { "type": "image", "url": "https://example.com/mock.png", "caption": "Reference" }
  ]
}
```

Supported `content_blocks[].type` values:

- `text`
- `markdown`
- `image`
- `code`
- `callout`
- `table`
- `report`

Available `response_type` values:

- `conversation` (default)
- `markdown`
- `summary`
- `reporting`

For explicit persona:

```json
{
  "content": "Review this as the OpenAI agent.",
  "persona_id": "<openai_persona_id>",
  "mode": "single_best",
  "response_type": "markdown"
}
```

Advanced participant overrides payload (for expanded toolbar UX):

```json
{
  "content": "Coordinate a focus group response.",
  "mode": "council",
  "response_type": "reporting",
  "persona_overrides": {
    "<persona_id_1>": { "response_type": "markdown", "mode": "threaded" },
    "<persona_id_2>": { "response_type": "summary", "mode": "summarized" }
  }
}
```

Preferred contract shape (chat-type aware):

```json
{
  "content": "Coordinate a launch plan.",
  "chat_type": "group",
  "mode": "council",
  "response_type": "reporting",
  "global_controls": {
    "effort": "deep"
  },
  "participant_controls": {
    "<persona_id_openai>": {
      "response_type": "markdown",
      "runtime_provider_id": "openai",
      "runtime_model_id": "gpt-4o-mini"
    },
    "<persona_id_google>": {
      "response_type": "summary",
      "runtime_provider_id": "google",
      "runtime_model_id": "gemini-2.5-flash"
    }
  },
  "explicit_persona_calls": ["<persona_id_openai>", "<persona_id_google>"],
  "auto_execute_tools": false,
  "strict_validation": false
}
```

Current behavior note:

- `persona_overrides` is accepted and returned for client orchestration state, while full per-participant execution overrides can be layered incrementally by client/runtime policy.
- `auto_execute_tools=false` allows tool recommendations to be returned without executing the tool call.

Chat response now includes `chat_options` to drive UI controls:

- `administrator_default_persona_id`
- `response_types`
- `modes`
- `workflow_actions`
- `prompt_template_kinds`
- `parallel_enabled`
- `max_personas`
- `participant_options[]` (per attached persona runtime/mode metadata)

Chat response also includes `requested_controls`:

- `response_type`
- `persona_overrides`
- `auto_execute_tools`

Chat response includes `validation` metadata:

- `warnings[]` non-fatal issues adjusted or ignored by server
- `rejections[]` fatal issues (when request is rejected)
- `summary` counts

Assistant and user messages include `metadata.structured_content` with block format:

```json
{
  "version": "v1",
  "primary_type": "markdown",
  "response_type": "markdown",
  "render_hint": "markdown",
  "blocks": [
    { "type": "markdown", "markdown": "..." }
  ]
}
```

For UI rendering, frontends should prefer:

- `assistant_message.metadata.response_type`
- `assistant_message.metadata.structured_content.render_hint`
- block-level `type` values such as `markdown` or `text`

This allows a message to be rendered in markdown view mode while preserving the raw markdown payload for copy, save, or edit actions.

Validation semantics:

- If malicious/forbidden/context-breaking input is detected, server rejects with `422 CHAT_PAYLOAD_VALIDATION_FAILED`.
- If input is non-fatal but imperfect, server applies best-valid controls and returns warnings.
- When `strict_validation=true`, warning-class issues (such as unknown fields) are escalated to rejection.

Server validation also enforces:

- size limits for `participant_controls` and `explicit_persona_calls`
- participant control field allowlist (`response_type`, `effort`, `runtime_provider_id`, `runtime_model_id`, `mode`)
- one-to-one context protections (for example, invalid group-only controls are ignored or rejected based on strict mode)

## 7) Realtime WebSocket

Connect:

- `/v1/realtime/ws?token=<access_token>`

Send message:

```json
{
  "action": "chat.send",
  "channel_id": "<channel_id>",
  "content": "Please synthesize next steps.",
  "mode": "council",
  "response_type": "summary"
}
```

Assistant websocket responses can now stream as additive block events while preserving one canonical persisted parent message:

1. `chat.response.started`
2. one or more `chat.response.block`
3. final legacy event such as `chat.response.completed`, `chat.response.persona`, or `council.response`

Example block event:

```json
{
  "event": "chat.response.block",
  "channel_id": "<channel_id>",
  "run_id": "<run_id>",
  "response_id": "<message_id>",
  "message_id": "<message_id>",
  "sequence": 1,
  "block_type": "markdown",
  "block": {
    "block_id": "<message_id>:block:1",
    "type": "markdown",
    "markdown": "## Section\n- item"
  }
}
```

This lets frontends render separate bubbles or segments for mixed `text` / `markdown` / `image` responses while keeping a single persisted assistant message with ordered blocks for replay, edit, or block-specific reply actions later.

See also: `backend/docs/chat-block-rendering-contract.md`

Common incoming events:

- `system.connected`
- `chat.message.user.created`
- `orchestration.policy.resolved`
- `orchestration.run.created`
- `council.delayed_start`
- `chat.response.completed` (single best)
- `council.response` (summarized council)
- `chat.response.awaiting_approval` (fallback approval required)

Image tool event behavior:

- If message content starts with `/image <prompt>`, server executes image generation via `nano_banana` tool routing.
- If message implies image intent (for example, "create an image" / "hero image" / "mockup"), server can recommend or execute image tool flow.
- Realtime emits `chat.response.completed` with assistant message metadata containing image attachment data.

Action-aware routing behaviors:

- `@personaHandle` mention
  - server can auto-route to mentioned persona (`single_best`) when no explicit `persona_id` is supplied.
- `/focus` or `/flow`
  - server treats as workflow actions and may route to `summarized` council mode when multiple active personas exist.
  - prompt-template kinds can be applied by workflow class:
    - `/focus` -> `focus_group_prompt`
    - `/flow` and `/agent` -> `tasking_prompt`
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
- `GET /v1/tools/executions?org_id=<org_id>` (tool execution audit trail)
- `GET /v1/tools/email/messages?org_id=<org_id>` (email send audit trail)

## 8.1) Tool Commands in Chat

HTTP and realtime chat both support image command syntax:

- `/image <prompt text>`

Example:

```json
{
  "content": "/image Create a product launch hero image with geometric accents.",
  "mode": "single_best"
}
```

Assistant message metadata for image tool responses includes:

- `tool_call.tool_id` (currently `nano_banana`)
- `tool_call.execution_id`
- `attachments[]` with:
  - `type` (`image`)
  - `mime_type`
  - `asset_url` (when available)
  - `image_base64` (when provider returns inline image bytes)
  - `status` (`completed` or `simulated`)

Client render hook recommendation:

- If `message.metadata.attachments` exists, iterate attachments and render image when `type === "image"`.
- Prefer `asset_url` when present; else render `data:${mime_type};base64,${image_base64}`.
- Keep a fallback label for `status === "simulated"` so users know image is non-live.
- Optionally deep-link tool logs via `tool_call.execution_id` to `/v1/tools/executions`.

## 8.2) Persona Visibility for Permission Testing

Personas can include access policy metadata in `data.access_policy`:

```json
{
  "access_policy": {
    "visibility": "admin_only"
  }
}
```

Supported visibility values currently:

- `organization` (default, visible to members)
- `admin_only` (owner/admin/global admin only)

When `admin_only` is set:

- persona is filtered from general member persona lists,
- direct persona fetch/use returns `403 STUDIO_PERSONA_ACCESS_FORBIDDEN`.

## 9) Prompt Template Overrides (Provider/Scope)

You can override persona system prompts by provider and hierarchy.

- Create version: `POST /v1/system/prompt-templates/versions`
- Activate at scope: `POST /v1/system/prompt-templates/activations`
- Resolve: `GET /v1/system/prompt-templates/resolve`
- Rollback: `POST /v1/system/prompt-templates/activations/{activation_id}/rollback`
- Capabilities: `GET /v1/system/prompt-templates/capabilities`
- Render preview: `POST /v1/system/prompt-templates/render-preview`

Template kinds currently supported for editing:

- `system_prompt`
- `planner_prompt`
- `tool_call_prompt`
- `focus_group_prompt`
- `tasking_prompt`
- `reflection_prompt`

Template variables supported currently include:

- `{{persona.name}}`
- `{{persona.role}}`
- `{{persona.scope}}`
- `{{persona.base_prompt}}`
- `{{request.message}}`
- `{{request.action_type}}`
- `{{council.response_count}}`

Persona APIs include chat configuration metadata:

- `GET /v1/studio/personas`
- `GET /v1/studio/personas/{persona_id}`

Each persona payload includes `chat_configuration` with available modes, response types, and template kinds so clients can build administrator default + per-participant controls from server-provided options.

## 10) Provider Configuration Checklist

Dynamic dropdown/source-of-truth endpoints for client controls:

- `GET /v1/system/ai/providers`
  - provider catalog, configured status, capabilities, and provider `response_controls` (including `effort_levels` and supported response types).
- `GET /v1/system/ai/providers/{provider_id}/models?capability=chat`
  - provider model options plus `response_controls` for that provider.

Recommended client behavior:

- Populate model dropdown from provider models endpoint.
- Populate effort/response controls from provider `response_controls`.
- Avoid hardcoding provider-specific controls in client where possible.

For two-provider testing (OpenAI + Google):

- `OPENAI_API_KEY`
- `GEMINI_API_KEY`
- `LLM_LIVE_MODE=true` (if you want live provider calls; otherwise simulation paths are used)

Email sending setup:

- Select provider: `TOOL_PROVIDER_EMAIL_SEND=smtp|sendgrid|email`
- SMTP:
  - `EMAIL_SMTP_HOST`
  - `EMAIL_SMTP_PORT`
  - `EMAIL_SMTP_USERNAME`
  - `EMAIL_SMTP_PASSWORD`
  - `EMAIL_SMTP_USE_TLS`
- SendGrid:
  - `SENDGRID_API_KEY`

Sender identity notes:

- Use a `sender` address your SMTP or SendGrid account is authorized to send from.
- For production deliverability, configure SPF/DKIM and verified sender/domain on your provider.

Image generation routing setup:

- `TOOL_PROVIDER_IMAGE_GENERATION=google|openai`
- Google default model env: `GEMINI_IMAGE_MODEL`
- OpenAI default model env: `OPENAI_IMAGE_MODEL`
