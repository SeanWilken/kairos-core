# Contract Domains v0.1

This document defines the core contract objects expected across MyAI integrations.

## 1) ModelProfile

Represents how inference is provided.

Suggested fields:

- `profile_id`
- `strategy` (`bring_your_own_model` | `api_provider` | `local_training`)
- `provider` (optional for BYO)
- `model_ref`
- `tokenizer_ref` (when applicable)
- `runtime_constraints` (latency/cost/privacy)

## 2) OnboardingProfile

Represents user/team alignment input.

Suggested fields:

- `profile_id`
- `persona_name`
- `personality_tags`
- `focus_areas`
- `strengths`
- `weaknesses`
- `objectives`
- `milestones`
- `nice_to_have`

## 3) KnowledgeBundle

Represents prepared knowledge assets.

Suggested fields:

- `bundle_id`
- `source_documents`
- `cleanliness_status`
- `sanitization_report`
- `vector_index_ref`
- `tags`
- `provenance`

## 4) CapabilityContract

Represents expected behavior and limitations.

Suggested fields:

- `capability_id`
- `intended_tasks`
- `disallowed_tasks`
- `risk_tier`
- `output_style_constraints`
- `evaluation_targets`

## 5) RuntimeBundle

Represents deployable output consumed by other modules.

Suggested fields:

- `runtime_id`
- `model_profile_ref`
- `knowledge_bundle_ref`
- `policy_profile_ref`
- `api_endpoints`
- `integration_hints`

## 6) GovernanceRecord

Represents auditable control metadata.

Suggested fields:

- `record_id`
- `tenant_id`
- `org_id`
- `correlation_id`
- `decision_type`
- `decision_outcome`
- `reason_code`
- `timestamp`

## 7) TaskContract

Represents an executable unit of work across text, translation, audio, or video flows.

Suggested fields:

- `task_id`
- `task_type` (`text_generation` | `translation` | `proofread` | `audio_generation` | `video_generation`)
- `input_refs` (documents, context docs, or upstream artifacts)
- `output_requirements` (language, style, format)
- `risk_tier`
- `assignee_mode` (`single_agent` | `multi_agent`)

## 8) ArtifactOutput

Represents outputs produced by tasks and handed to downstream tools.

Suggested fields:

- `artifact_id`
- `artifact_type` (`script` | `subtitle` | `voice_track` | `video_cut` | `qa_report`)
- `source_task_id`
- `language`
- `storage_ref`
- `checksum`
- `license_or_rights`

## 9) QualityGate

Represents quality and safety checks required before downstream use.

Suggested fields:

- `gate_id`
- `target_task_id`
- `checks` (for example: translation fluency, policy safety, grounding, brand tone)
- `status` (`passed` | `failed` | `needs_review`)
- `reviewer_type` (`auto` | `human`)
- `notes`

## Versioning notes

- all domain payloads should include `spec_version`
- additive fields are preferred for minor evolution
- incompatible changes require new versioned contracts
