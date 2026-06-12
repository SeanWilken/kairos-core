# Policy Override Governance v0.1

This document defines governance for policy overrides in MyAI Core and suite applications.

## Baseline Rule

Policy constraints are first-class and enforced by default on every request.

Overrides are exceptional and require explicit user intervention, approval, and audit logging.

## Constraint Classes

## Non-overridable

These constraints cannot be bypassed by runtime override:

- tenant isolation and auth validity
- mandatory safety and legal constraints marked hard
- explicit deny decisions with non-overridable reason class

## Conditionally overridable

These may be overridden only through approved workflow:

- selected tool usage guidance
- scoped execution behavior constraints
- optional quality or preference constraints

Each overridable class must be tagged in policy metadata.

## Override Lifecycle

1. request submitted (`override.requested`)
2. human approval interaction (`override.approved` or `override.rejected`)
3. active window (time-bounded)
4. expiry or revocation (`override.expired` or `override.revoked`)

## Mandatory Approval Record Fields

- approval id
- request id
- tenant id and org id
- requested by (actor)
- approved by (actor)
- reason and optional ticket reference
- scope (`single_request|session|timeboxed`)
- expiry timestamp
- created timestamp

## Enforcement Rules

- No override is applied without active approval record.
- Expired overrides are ignored automatically.
- Overrides never supersede non-overridable constraints.
- Every applied override must be surfaced in runtime trace output.

## Audit and Trace Requirements

For any override path, system must emit:

- policy decision event
- override decision event
- execution event with applied override references

Trace payload should include:

- selected constraints
- overridden constraints
- skipped override reasons
- final effective instruction/order summary

## Operator UX Requirements (Studio and CLI)

- clear approval prompts with scope and expiry selection
- visible reason-code and impact summary
- approval queue and history view
- revoke action for active overrides

## Initial Scope

Single approval is supported in v0.1. Dual-approval can be introduced later for high-risk classes.
