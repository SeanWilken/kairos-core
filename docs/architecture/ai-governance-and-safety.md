# AI Governance and Safety Baseline

This document defines the baseline governance and safety posture for Kairos Core.

## Goals

- reduce harmful or policy-violating output in user-facing use cases
- reduce hallucination and unsupported claims
- ensure traceability for high-impact decisions
- keep governance compatible with modular integrations

## Baseline control areas

1. Input safety
   - prompt injection detection patterns
   - context boundary enforcement (system/instruction separation)
   - tenant/org scope checks before retrieval and tool use

2. Retrieval safety
   - source scoping and authorization filters before retrieval
   - citation-ready retrieval output
   - stale/low-confidence source handling

3. Output safety
   - policy checks on generated output
   - refusal/escalation behavior for disallowed requests
   - role-bound response shaping for delegated agents

4. Runtime governance
   - audit events for sensitive actions and approvals
   - risk-tiered behavior (low/medium/high impact)
   - reproducible request metadata (correlation ID, version, environment)

5. Monitoring and response
   - latency/quality/usage telemetry
   - policy violation and drift signals
   - incident workflow through `SECURITY.md`

## Prompt injection and jailbreak posture

Kairos Core assumes prompt injection will happen in user-facing systems.
Core integrations should follow these rules:

- never treat user text as trusted system instructions
- keep policy-critical instructions outside user-controlled context
- sanitize and partition retrieved content by trust/source class
- gate tool invocation and data access through policy checks
- keep denial reasons machine-readable and auditable

## Compliance alignment targets

This project references widely used frameworks as implementation guidance:

- NIST AI RMF (risk management)
- OWASP LLM Top 10 (LLM-specific threats)
- SOC 2 style controls (operational security practices)
- GDPR/CCPA principles where personal data handling applies

These are guidance targets, not a legal certification claim.

## User-facing chatbot note

For chatbot or FAQ integrations, implementers should require:

- grounding/citation mode where possible
- output policy filtering
- human escalation paths for high-risk topics
- clear disclosure that AI output may be imperfect
