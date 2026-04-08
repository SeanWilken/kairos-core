# Architecture Notes

This directory contains architecture docs and system diagrams for the core training stack.

## Current Architecture Direction

- Core-first modular monolith for early velocity
- clear extraction boundaries for future external services/repos
- standards-driven interoperability
- governance and safety controls as default runtime behavior

## Primary architecture threads

1. Core Engine
   - tenancy, policies, event sourcing, audit, orchestration primitives
2. Training/Alignment Orchestrator
   - onboarding profile synthesis
   - RAG/context document behavior shaping
   - exercise/coaching pathways (coding-first domain initially)
3. Model Artifact Manager
   - lineage metadata, packaging, export/publish flows
4. Reference UI
   - baseline UX similar to OpenCode style workflows
   - not required for ecosystem interoperability

## Planned diagrams

- Context diagram
- Container diagram
- Event flow sequence (event-sourcing + projections)
- LangGraph orchestration state flow
- Inter-repo topology and contract boundaries

## Supporting docs

- `docs/architecture/repo-charter.md`
- `docs/architecture/ai-governance-and-safety.md`
- `docs/architecture/core-bootstrap-roadmap.md`
