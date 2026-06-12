# Chat Block Rendering Contract

This document defines how frontends should render assistant and user chat content when `structured_content.blocks` is present.

## Goal

Support mixed responses such as:

1. explanatory text
2. markdown section
3. follow-up text

while preserving one canonical persisted parent message.

## Persistence model

- one persisted parent assistant message
- ordered typed blocks in `message.metadata.structured_content.blocks`
- block-level actions later reference `message_id + block_id`

Do not treat each block as its own persisted chat message.

## Structured content shape

```json
{
  "version": "v1",
  "primary_type": "mixed",
  "response_type": "markdown",
  "render_hint": "structured_blocks",
  "blocks": [
    {
      "block_id": "block:0",
      "type": "text",
      "text": "Intro paragraph.",
      "capabilities": {
        "replyable": true,
        "editable": false,
        "saveable": true,
        "copyable": true
      }
    },
    {
      "block_id": "block:1",
      "type": "markdown",
      "markdown": "## Section\n- item",
      "capabilities": {
        "replyable": true,
        "editable": true,
        "saveable": true,
        "copyable": true
      }
    }
  ]
}
```

## Render rules

### Preferred decision order

1. `structured_content.render_hint`
2. block-level `type`
3. fallback to plain message `content`

### Render hints

- `plain_text`
  - render message as text-first
- `markdown`
  - render message as markdown-first
- `structured_blocks`
  - render individual blocks in order

## Block types

### `text`

- render with normal text bubble styling
- source field: `text`

### `markdown`

- render with markdown renderer in view mode
- source field: `markdown`
- preserve raw markdown for copy/save/edit actions

### `image`

- render image/media block
- use attachment metadata as provided

## UI / UX recommendation

For mixed content:

- render each block as a distinct segment or bubble inside one assistant response group
- keep visual grouping tied to the parent message
- maintain block ordering via array position

This creates a messaging feel without fragmenting persistence.

## Reply targeting

Future reply payloads should be able to reference:

- `message_id`
- `block_id`

Suggested shape:

```json
{
  "reply_target": {
    "message_id": "msg_123",
    "block_id": "block:1"
  }
}
```

## Edit targeting

Only blocks with:

- `capabilities.editable = true`

should be exposed to block-level edit UI.

Current expectation:

- markdown blocks are editable
- text blocks are not yet editable as block content

## Save / export targeting

Blocks with:

- `capabilities.saveable = true`

can be saved into notes, docs, snippets, or knowledge nodes later.

## WebSocket streaming model

For realtime clients the server may emit:

1. `chat.response.started`
2. one or more `chat.response.block`
3. final event (`chat.response.completed`, `chat.response.persona`, `council.response`)

The final event contains the persisted parent message. Frontends should reconcile streamed blocks with the final canonical message using `message_id`.

## Important compatibility note

Older clients may ignore block streaming and continue using the final event payload only.

Newer clients should prefer the block stream for incremental rendering and then reconcile against the final persisted parent message.
