# Knowledge Entity And Reuse Conventions v0.1

This document defines the first canonical conventions for structured knowledge objects that help agents reduce drift across projects and reuse existing work instead of rewriting it.

## Entity Conventions

- `file`
  - Required facet: `path` or `file_path`
  - Represents a concrete source file or artifact path.
- `symbol`
  - Required facet: one of `symbol_name`, `class_name`, `function_name`, `component_name`
  - Recommended facets: `symbol_kind`, `path`
  - Represents a code-level unit such as a function, class, component, or block.
- `project`
  - Required facet: one of `project_key`, `slug`, `repo_name`
  - Represents a project, repo, or bounded implementation space.
- `glossary_term`
  - Convention id comes from `subtype=glossary_term`
  - Required kind payload field: `definition` or `meaning`
  - Represents a stable shared term or definition for humans and agents.

## Reuse Relationships

- `similar_to`
  - Two entities implement closely related logic or structure.
- `duplicate_of`
  - One entity is effectively a duplicate of another.
- `extracted_from`
  - A shared helper, abstraction, or artifact was extracted from another entity.
- `should_be_shared`
  - A governance or review signal that similar code should be consolidated into a common reusable unit.

## Intended Use

- Help agents identify reusable code and prior work across projects.
- Improve deterministic context bundle construction.
- Provide stable references for files, symbols, projects, tasks, and glossary terms.
- Support future compaction, dedupe, and relationship health logic.
