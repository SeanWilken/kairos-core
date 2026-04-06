# Model Artifact Spec v0.1

## Goal

Standardize model artifacts so they can be consumed locally, by OpenCode-like frontends, or published to Hugging Face.

## Required metadata

- artifact id and version
- base model reference
- tokenizer reference/version
- lineage (parent artifact/version)
- dataset/profile/context provenance summary
- evaluation metrics summary
- intended use and limitations
- license and distribution metadata
- safety policy profile reference
- governance metadata (risk tier, evaluation gate state)

## Export targets

- local bundle format
- Hugging Face-compatible publishing package
- OpenCode-compatible runtime mapping metadata

## Safety and reproducibility

- immutable artifact identifiers
- checksums for package integrity
- reproducibility fields (config fingerprints, versions)
- documented evaluation outcomes for intended use cases
- policy-alignment notes for user-facing deployment contexts
