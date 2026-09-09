# Workspace Prototype Studio

Workspace Prototype Studio is the fast product and prototype incubation lane for
internal tools, future client apps, UI prototypes, and UI-plus-backend
experiments.

It is not a replacement for Workspace Delivery ART, platform release authority,
security architecture, or governed product delivery. Its job is to let operators
explore and prove product shape quickly while preserving enough lifecycle,
visibility, data-mode, and graduation control to avoid unmanaged throwaway work.

Authoritative references for this repo are `workspace-governance`,
`platform-engineering`, `security-architecture`, and
`operator-orchestration-service`.

## What Lives Here

- prototype briefs, backlog notes, change logs, and decision logs
- prototype design profiles and pattern inventories
- design baseline records before a UI is treated as approved
- backend stubs and local prototype services when needed
- mock and synthetic data fixtures
- reusable prototype validation and portfolio templates
- source-authoritative Prototype Landing records and review-branch receipts
- versioned Prototype Delivery packets that preserve source truth for later
  governed admission
- graduation records when a prototype moves into governed delivery, an existing
  product repo, or a new dedicated repo

## What Does Not Live Here

- production releases
- governed stage or prod deployment authority, which belongs to
  `platform-engineering`
- real client data by default
- security acceptance decisions, which belong to `security-architecture`
- Workspace Delivery ART work-state truth, which is mediated through
  `operator-orchestration-service`
- long-lived product source after graduation

## Quick Start

```bash
make validate
```

New Prototype records use the deterministic Landing owner command rather than
manual template and registry copying. See
[docs/prototype-landing.md](docs/prototype-landing.md).

Candidate and Baseline Promotion use the separate deterministic maturity owner
command. See [docs/prototype-maturity.md](docs/prototype-maturity.md).

## Security Baseline

The security review baseline for this lane is maintained in
`security-architecture/docs/reviews/components/2026-05-06-workspace-prototype-studio-product-incubation-baseline.md`.

Prototype work must also follow the security view in
`security-architecture/docs/architecture/components/workspace-prototype-studio/README.md`.
Real data, client-visible exposure, mutable external systems, identity,
secrets, AI-assisted action paths, or external hosting trigger security review
and usually graduation.

## Lifecycle

- `exploring`: rough idea, no approved direction yet
- `candidate`: accepted as worth shaping, still not design-approved
- `baseline-approved`: design baseline accepted for implementation
- `graduating`: being moved into governed delivery, a product repo, or a client
  project lane
- `graduated`: source of truth has moved elsewhere
- `retired`: no longer active; keep the decision record

See [docs/operating-model.md](docs/operating-model.md) for the full operator
workflow and [docs/interface-design-discipline.md](docs/interface-design-discipline.md)
for UI design discipline. Source structure and coding rules live in
[docs/source-structure-discipline.md](docs/source-structure-discipline.md).
The owner-local source path for Candidate and Baseline Promotion is in
[docs/prototype-maturity.md](docs/prototype-maturity.md).
The operator path for a baseline-approved Prototype entering Delivery is in
[docs/prototype-delivery-packets.md](docs/prototype-delivery-packets.md).
The separate source-only Workspace Intake path is in
[docs/prototype-intake-candidates.md](docs/prototype-intake-candidates.md).
