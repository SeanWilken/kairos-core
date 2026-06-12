# myAI POC Roadmap (Public-Facing Draft)

This roadmap is intended for early adopters running MyAI Core with sibling suite repos (including `../myAI`).

It focuses on practical readiness, known shortcomings, and what is expected next.

## Current Focus (Now)

### Studio

- Governance and configuration workflows for suite entities
- Users, orgs, personas, room-level persona assignments
- Policy and document setup needed by other surfaces

### Council

- Realtime WebSocket stability and reconnection behavior
- Multi-persona orchestration behavior by mode
- Better clarity for requested mode vs effective mode in outcomes

### AIDE / myAI Integration

- Local-first workspace and repo graph usage
- Core-backed policy/context orchestration for agent tasks
- Traceability of coding actions against shared contracts

## Known Shortcomings

- Not all client surfaces currently implement automatic access-token refresh/retry.
- Some environment setups vary significantly (Docker vs Podman, local dependency drift).
- Realtime behavior can appear inconsistent when proxy/rewrite config differs by app.
- Cross-app UX consistency is still converging while contracts stabilize.

## Next 30-60 Days (Target)

1. Stabilize Studio/Council/AIDE critical workflows and acceptance checks.
2. Finalize shared contract set used by these workflows.
3. Improve auth/session reliability with standard refresh-and-retry behavior.
4. Expand observability for orchestration, context usage, and policy outcomes.
5. Introduce CLI wrapper and indexed instruction resolution for tool and agent capability control.

## New Architecture Track (In Progress)

- CLI wrapper model for operator and developer workflows
- Knowledge-indexed tool instructions instead of monolithic skill files
- Policy-first override governance with required user approval and audit trace

See:

- `docs/ecosystem/cli-wrapper-and-tool-index-v0.1.md`
- `docs/architecture/policy-override-governance-v0.1.md`
- `shared-contracts/schemas/interop/instruction-resolution-v0.1.md`

## After Core Path Is Operational

Selection criteria for the next experience:

- dependency readiness on shared contracts,
- implementation effort,
- ecosystem leverage.

Likely next candidates:

- KnowLedger improvements (knowledge graph explainability)
- Journeyl or Illuminate (memory/learning surfaces)

## Conjure Feasibility Note

Conjure should be relatively low effort after shared capability plumbing for image generation is production-stable across chat/request pathways. Video can then be added as an extension rather than a new stack.

## POC-to-Production Boundary

Treat current release posture as POC until the following are consistently true:

- contract compatibility checks pass across priority apps,
- auth/session flows recover gracefully from token expiry,
- realtime and orchestration diagnostics are transparent enough for operators,
- installation docs are reproducible by external users without internal intervention.
