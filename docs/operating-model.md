# Prototype Studio Operating Model

Workspace Prototype Studio is the fast lane for shaping products before they
are mature enough for governed delivery.

## Intake Flow

1. Capture the idea in Workspace Proposals when the work is more than a local
   sketch.
2. If the idea needs prototype exploration, add or update a record in
   `prototypes.yaml`.
3. Create the prototype files under `docs/prototypes/<prototype-id>/`.
4. Use mock or synthetic data by default.
5. Create a design baseline record only when the operator accepts the design
   direction.
6. Graduate the prototype when it needs durable delivery, real runtime,
   client-facing review, or long-lived source ownership.

## Lifecycle Transitions

`exploring` means the idea is being sketched and can be deleted without formal
retirement.

`candidate` means the operator wants it shaped, but the design is not approved.

`baseline-approved` means the design direction is accepted and implementation
can proceed against the baseline.

`graduating` means the work is moving to Workspace Delivery ART, an existing
repo, a new repo, or a client portfolio.

`graduated` means this repo is no longer the source of truth.

`retired` means the work is intentionally stopped.

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

## Portfolio Routing

Internal tools use the internal product portfolio until they graduate into the
workspace system or a dedicated product repo.

Client apps use the client app delivery portfolio. A separate client-visible
project is created only when confidentiality and access controls are ready.

Workspace system tools, such as the Governance Operations Console, may start
here but graduate to Workspace Delivery ART when they become part of the
governed system.

