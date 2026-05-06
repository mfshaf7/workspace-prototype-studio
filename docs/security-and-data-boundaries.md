# Security And Data Boundaries

Prototype speed is allowed only while boundaries stay explicit.

Primary security artifacts:

- `security-architecture/docs/architecture/components/workspace-prototype-studio/README.md`
- `security-architecture/docs/reviews/components/2026-05-06-workspace-prototype-studio-product-incubation-baseline.md`

## Security Trigger Matrix

Open a security review or link an existing one when a prototype introduces:

- identity, authentication, authorization, or session behavior
- secrets, tokens, credentials, webhooks, or third-party API keys
- real client data or operational exports
- mutable writes outside local prototype state
- client-visible or public-demo exposure
- AI-assisted decision or action paths
- external hosting or inbound network exposure
- payment, billing, healthcare, legal, finance, or regulated data

## Default Deny Rules

- No real client data by default.
- No secrets in repository files.
- No `real-mutable` prototype without security evidence and graduation plan.
- No client review without a client-safe evidence path.
- No production deployment from this repo.
