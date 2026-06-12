# Core Interop Spec v0.1

## Purpose

Define minimum interoperable contracts so external repos can integrate with the core engine.

This spec is designed for multiple interaction modes:

- full MyAI reference UI
- external wrappers/frontends
- direct API consumption without chat-room UX

## Required contract domains

1. Profile Contract
   - user/workstyle/domain goals
   - constraints, preferred methodologies (for example, TDD, DDD)
2. Context Contract
   - RAG sources + session context docs
   - scope and access restrictions
3. Capability Contract
   - what the assistant is optimized to do and avoid
4. Evaluation Contract
   - metric declarations (F1, ROUGE, BLEU, perplexity where relevant)
   - overfitting and balance checks
5. Audit Contract
   - correlation and causation linkage
   - event identity and tenant traceability
6. Artifact Contract
   - model/tokenizer/version lineage metadata
   - export/publish compatibility metadata
7. Task and Artifact Contracts
   - task typing across modalities (`text`, `translation`, `audio`, `video`)
   - artifact handoff metadata for downstream modules
8. Quality Gate Contract
   - quality/safety checks and release gating status
   - automated vs human review metadata

## Model strategy interoperability

Interop clients should declare model strategy in their runtime configuration:

- `bring_your_own_model`
- `api_provider`
- `local_training` (future capability)

This keeps downstream integrations stable even when training capabilities evolve.

## Governance interoperability requirements

Any client integrating with core contracts must preserve:

- tenant and org boundary metadata
- correlation IDs for request tracing
- machine-readable error codes
- policy decision records for denied or escalated actions

## Multimodal workflow interoperability

Interop clients should be able to execute or consume pipelines where outputs from one task become inputs to another.

Example sequence:

1. script generation
2. translation
3. proofreading/QA
4. audio generation
5. video generation
6. publish gate approval

The core contracts should support this sequence even when execution engines differ.

## Compatibility model

- `spec_version` required on all interop payloads
- clients should declare supported versions
- incompatible versions must return machine-readable errors
