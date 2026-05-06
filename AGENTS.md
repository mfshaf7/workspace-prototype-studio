# Workspace Prototype Studio AGENTS

This repo owns fast prototype and product-incubation source for internal tools
and future client apps.

Authoritative references for this repo are `workspace-governance`,
`platform-engineering`, `security-architecture`, and
`operator-orchestration-service`.

## Start Here

1. Read `README.md`.
2. Read `docs/operating-model.md`.
3. Inspect `prototypes.yaml` before editing any prototype.
4. Run `make validate` before treating changes as complete.

## Operating Rules

- Keep prototype work fast, but keep lifecycle and boundaries explicit.
- Do not put real client data, secrets, tokens, credentials, production exports,
  or private operational logs in this repo.
- Treat
  `security-architecture/docs/architecture/components/workspace-prototype-studio/README.md`
  and
  `security-architecture/docs/reviews/components/2026-05-06-workspace-prototype-studio-product-incubation-baseline.md`
  as the concrete security artifacts for this repo.
- Default to `mock` or `synthetic` data unless a prototype record explicitly
  allows `real-readonly` and carries security-review evidence.
- `real-mutable` requires a security trigger review and a graduation or governed
  delivery plan before implementation.
- Client-visible work must use `client-review` or `public-demo` visibility only
  after a client-safe evidence path exists.
- UI prototypes should prioritize deliberate design direction over generic
  scaffolding.
- Backend stubs are allowed here only while the prototype is still incubating.
  Durable backend services must graduate to the owning product repo or a new
  repo.

## Review Guidelines

- Verify lifecycle state, visibility tier, data mode, mutation boundary, and
  graduation posture.
- Check that each prototype has a brief, backlog, change log, and decision log.
- Check that security triggers are present for identity, secrets, real data,
  mutable workflows, client exposure, AI assistance, or external hosting.
- Treat design baseline approval as a record, not a chat memory.
