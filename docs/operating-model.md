# Prototype Studio Operating Model

Workspace Prototype Studio is the fast lane for shaping products before they
are mature enough for governed delivery.

## Intake Flow

1. Capture the idea in Workspace Proposals when the work is more than a local
   sketch.
2. If the idea needs prototype exploration, capture a Prototype Entry Packet
   and accepted Landing request.
3. Apply a ready Landing through the owner command on a non-default review
   branch. The command creates the registry record and prototype files
   together.
4. Create or update the prototype design profile before UI work is treated as
   baseline-ready.
5. Use mock or synthetic data by default.
6. Create a design baseline record only when the operator accepts the design
   direction.
7. Graduate the prototype when it needs durable delivery, real runtime,
   client-facing review, or long-lived source ownership.

The command and its source/readiness/workflow boundaries are documented in
[Prototype Landing](prototype-landing.md). Direct edits to create a new
Prototype are a recovery path, not the normal operator workflow.

## Lifecycle Transitions

`exploring` means the idea is being sketched and can be deleted without formal
retirement.

`candidate` means the operator wants it shaped, but the design is not approved.

Candidate state is entered only through the source-authoritative promotion
path in [Prototype Maturity](prototype-maturity.md). An interview, checklist,
or readiness result alone does not change the registry.

`baseline-approved` means the design direction is accepted and implementation
can proceed against the baseline.

Baseline state is entered only when an approved maturity decision prepares the
exact registry and design-baseline change on a review branch and merged-source
readback later confirms it.

Baseline approval does not mean the prototype has live backend authority. It
means the operator shape, visual language, workflow states, and local proof are
accepted enough for implementation or graduation work to proceed deliberately.

`graduating` means a route-specific lifecycle transition is moving the work to
Workspace Delivery ART, an existing repo, a new repo, or an admitted platform
path. The source domain, validator, target domain, named decision authority,
orchestration, and target adapter retain their distinct authorities.

`graduated` means this repo is no longer the source of truth.

`retired` means the work is intentionally stopped.

## Linked Records

`prototypes.yaml` uses typed `linked_records` for traceability to proposal,
delivery, baseline, graduation, and retirement records. These links do not
drive prototype lifecycle state by themselves.

Lifecycle state comes from the prototype registry fields and required records:

- `lifecycle`
- `design_baseline_ref`
- `delivery_packet_ref`
- `graduation_ref`
- `retirement_ref`

`delivery_packet_ref` is required while `graduating` and resolves to a
versioned Prototype-owned packet under `records/delivery-packets/`.
`graduation_ref` is required only after a target application receipt proves the
final transition and the lifecycle becomes `graduated`.

Linked OpenProject records may be at different ART levels, such as an Epic
anchor, a Feature parent, or a User story evidence record. The operator surface
must display each link by role instead of treating every linked work package as
the same kind of delivery state. The retired untyped `delivery_refs` field must
not be used for new prototype records.

## Baseline Boundary

Prototype Studio separates baseline shaping from live implementation.

Before baseline approval, a prototype may own mock, synthetic, approved
read-only, or prototype-local behavior that proves the product and operator
workflow. It may also define component rules, local persistence, focused smoke
checks, visual evidence, and records that explain what the baseline includes.

After baseline approval, or during graduation, the work may move into durable
backend wiring, real-system mutation, durable receipt ledgers, live
persistence, complete live-contract regression, governed runtime activation,
or owner-repo promotion. Those responsibilities must not be hidden inside a
pre-baseline prototype unless the prototype record explicitly admits the data
mode and the required security/governance evidence exists.

When a prototype discovers backend/live work before baseline approval, record
it as post-baseline or graduation work instead of presenting local mock
behavior as a finished system.

## Visibility Tiers

- `private-internal`: workspace-only, not client-visible
- `operator-review`: safe for internal operator review
- `client-review`: safe for a named client review surface
- `public-demo`: safe for public demonstration

## Data Modes

- `mock`: invented data only
- `synthetic`: generated data that resembles reality but carries no real
  secrets, client data, or operational exports
- `real-readonly`: real read-only data with security review evidence
- `real-mutable`: real mutable workflow, requiring security review and a
  governed delivery or graduation plan

## Mutation Boundaries

- `none`: no backend mutation path
- `read-only`: reads from a mock, synthetic, or approved read-only source
- `prototype-local`: writes only to local disposable prototype state
- `external-sandbox`: writes to an isolated external sandbox
- `real-system`: writes to a real system and must graduate before normal use

## Graduation Triggers

Graduate when any of these become true:

- real client data is needed
- client-facing review needs controlled access
- identity, secrets, or payments enter the design
- mutable backend workflow reaches beyond prototype-local state
- the backend becomes durable product source
- the prototype needs governed stage or prod
- multiple operators or clients depend on it

## Product Portfolio Publication

Workspace Intake entrant candidates are a separate source projection. They
preserve the approved baseline and stable prototype identity without changing
lifecycle, classifying the entrant, or assigning its durable owner. Use
[Prototype Intake Candidates](prototype-intake-candidates.md) for that path.

Portfolio is the managed-product catalog and operator showcase for graduated,
durable products. It is not a build lane, a generic posture register, or a
Prototype visibility mechanism.

Most new work flows from Workspace Proposals into Prototype Studio or Workspace
Delivery ART. A Prototype may use its own Preview Runtime for early visibility,
but it cannot publish directly into Portfolio. It must first graduate to a
durable product owner and managed runtime or distribution path.

A Delivery closeout may produce a product-publication candidate when the
outcome creates a new product, release, or material product update. Non-product
Delivery outcomes remain Delivery history. Product identity and maturity come
from the workspace product registry; product description comes from a
product-owned manifest; Platform and Security retain runtime, exposure, and
acceptance authority.

Portfolio admission validates those source-backed facts and creates or updates
one product entry. Portfolio controls listing and curation only. It does not
grant runtime access, widen exposure, approve security posture, or take source
custody from Proposal, Prototype, Delivery, or an owner repository.

Workspace system tools, such as the Governance Operations Console, may start
here but graduate to Workspace Delivery ART when they become part of the
governed system.

## Interface Design Discipline

UI work in this repo uses the workspace `interface-design-discipline` skill.
Each active UI prototype must keep a design profile in its prototype record.

The design profile is the project-local contract for visual direction,
typography, status semantics, responsive policy, source-of-truth assumptions,
and reusable patterns. It lets prototype work move quickly without forcing every
future UI to inherit the same look.

See [interface-design-discipline.md](interface-design-discipline.md).

## Source Structure Discipline

Prototype source must keep ownership boundaries visible while moving quickly.
Use [source-structure-discipline.md](source-structure-discipline.md) before
changing component structure, workflow session architecture, shared primitives,
read models, selectors, CSS ownership, or validation guards.

The goal is resumable work: each substantial surface should be coherent enough
to pause, switch away, and resume later through records, predictable modules,
and focused guards rather than chat memory.
