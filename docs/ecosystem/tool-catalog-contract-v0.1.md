# Tool Catalog Contract v0.1

This document defines the canonical machine-readable catalog shape for tools and wrapper-capable host features in the MyAI ecosystem.

## Purpose

The tool catalog should answer:

- what tools exist
- what class/category they belong to
- how risky they are
- what wrapper command should invoke them
- what capabilities they expose
- what hosts or installers are required
- what docs bundles describe them

## Core object

```json
{
  "tool_id": "image_resize",
  "label": "Image Resize",
  "category": "image_processing",
  "description": "Resize and reformat images for common output targets.",
  "risk_level": "low",
  "approval_mode": "none",
  "side_effect_level": "write",
  "wrapper_command": "myai image resize",
  "capabilities": ["image_read", "image_write", "resize", "reformat"],
  "implementations": [
    {
      "implementation_id": "imagemagick",
      "kind": "host_cli",
      "binary_name": "magick",
      "provider_id": null,
      "default": true
    }
  ],
  "host_requirements": {
    "os": ["windows", "linux", "macos"],
    "architectures": ["amd64", "arm64"],
    "install_modes": ["installer", "manual", "container"]
  },
  "input_schema_ref": "schemas/tools/image_resize.input.json",
  "output_schema_ref": "schemas/tools/image_resize.output.json",
  "docs_bundle_ref": "docs/tools/image_resize/",
  "profile_affinity": ["document-drafter", "generalist"],
  "provider_preferences": {},
  "status": "supported"
}
```

## Required fields

- `tool_id`
- `label`
- `category`
- `risk_level`
- `approval_mode`
- `side_effect_level`
- `wrapper_command`
- `capabilities`
- `implementations`
- `host_requirements`
- `status`

## Enumerations

### `risk_level`

- `low`
- `medium`
- `high`
- `critical`

### `approval_mode`

- `none`
- `single`
- `multi_stage`

### `side_effect_level`

- `read`
- `write`
- `execute`
- `destructive`

### `status`

- `supported`
- `experimental`
- `disabled`
- `deprecated`

### `implementation.kind`

- `host_cli`
- `embedded_runtime`
- `api_provider`
- `containerized`
- `wrapper_only`

## Recommended categories

- `speech_audio`
- `image_processing`
- `image_generation`
- `document_processing`
- `filesystem_data`
- `developer_build`
- `web_search`
- `shopping_commerce`
- `email_calendar`
- `deployment_container`
- `creative_content`
- `workflow_support`

## Capability examples

- `speech_to_text`
- `text_to_speech`
- `image_resize`
- `image_reformat`
- `pdf_extract_text`
- `document_convert`
- `file_read`
- `file_write`
- `build_run`
- `test_run`
- `git_commit`
- `web_search`
- `email_send`
- `calendar_query`
- `container_status`

## Provider preferences

For provider-backed tools, the catalog can optionally express defaults like:

```json
{
  "provider_preferences": {
    "provider_id": "google",
    "model_id": "imagen-3.0-generate-002"
  }
}
```

This is intended for deterministic execution and should not require repeated LLM reasoning to select providers.

## Relation to profiles

The catalog does not decide the active tool. It only describes what is available.

Profiles may reference tool IDs in:

- `preferred_tools`
- `preferred_tool_policies`
- provider/output preferences

## Relation to runtime registry

The catalog is canonical and static-ish.

The runtime registry answers:

- is it installed?
- where is it?
- is it validated?
- which implementation is active on this host?

## Initial contract deliverables

Near-term deliverables based on this contract:

1. a seed catalog for built-in tools
2. a runtime registry endpoint
3. a docs bundle contract
4. wrapper invocation contracts

Current backend-facing surfaces now include:

- `GET /v1/tools/catalog`
- `GET /v1/tools/runtime-registry`

Initial seed coverage includes tools such as:

- `speech_to_text`
- `text_to_speech`
- `image_generate`
- `email_send`
- `document_create_markdown` (planned)
- `task_create` (planned)
- `relationship_create` (planned)

## Notes

- This contract is intentionally vendor-neutral where possible.
- Wrapper commands should remain stable even if the underlying implementation changes.
