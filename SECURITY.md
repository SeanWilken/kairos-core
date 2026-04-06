# Security Policy

## Reporting a vulnerability

Please do not open a public issue for security vulnerabilities.

Instead, report privately by email to: `sean.d.wilken@gmail.com`

When reporting, include:

- affected component(s)
- reproduction steps or proof of concept
- impact and severity estimate
- any suggested remediation

## Response targets

- Initial acknowledgement: within 3 business days
- Triage/update: within 7 business days
- Remediation timeline: depends on severity and scope

## Disclosure process

We follow coordinated disclosure.
Once a fix is available, we will publish a security note and changelog entry.

## Scope notes

For this project, security-sensitive areas include:

- tenant/org boundary enforcement
- access control and delegation policy logic
- event and audit integrity
- secrets/config handling

## AI-specific security concerns

Please include whether your report involves any of the following:

- prompt injection or jailbreak behavior
- unauthorized data exposure through retrieval/routing
- unsafe tool invocation from untrusted prompts
- policy bypass in user-facing chatbot flows
- hallucination risks that could cause material harm in regulated contexts

## Compliance and governance posture

This project follows a best-practice governance approach and uses major frameworks as guidance (for example, NIST AI RMF and OWASP LLM Top 10). We do not claim certification by default.

If your report has legal/compliance impact, call that out explicitly so it can be triaged with higher urgency.
