# Knowledge Code Ingest API

Core exposes a code-ingest helper for MyAIDE and related development-plane clients.

## Endpoint

- `POST /v1/knowledge/code-ingest`

## Purpose

This endpoint promotes code scan results into canonical knowledge entities and relationships so agents can reference existing files, symbols, and reuse signals instead of re-deriving them from prompts.

It is designed to align with MyAIDE development-plane needs by carrying optional:

- `workspace_id`
- `runner_id`
- project/repo metadata

## Created knowledge objects

- `project` entities
- `file` entities
- `symbol` entities
- containment relationships such as `contains` and `belongs_to`
- reuse relationships such as:
  - `similar_to`
  - `duplicate_of`
  - `extracted_from`
  - `should_be_shared`

## Notes

- `file` and `symbol` entities follow the canonical knowledge conventions contract.
- Reuse links are resolved deterministically from entity ids, file paths, titles, or `path::symbol_name` references included in the ingest payload.
- This is intended to be the practical ingest path for repo indexing, workspace scans, language tooling summaries, and future MyAIDE code-memory sync flows.
