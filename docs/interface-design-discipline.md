# Interface Design Discipline

Workspace Prototype Studio uses fast visual iteration, but UI work is still
controlled. The goal is to move quickly without creating inconsistent panels,
tables, modals, buttons, or workflow surfaces that later need to be rebuilt.

Use the workspace `interface-design-discipline` skill before changing any UI or
visual workflow in this repo.

## Design Modes

`exploration` is for fast local shaping. Visual experiments can move quickly,
but the active design profile must stay honest about what is still undecided.

`baseline hardening` starts when the operator likes the direction and wants it
made consistent. One-off styling should be consolidated into named patterns.

`post-baseline maintenance` starts only after a design baseline record is
accepted. Changes after that point must preserve the approved visual language
or explicitly update the baseline.

## Prototype Baseline Boundary

Every prototype must keep a clear boundary between baseline-shaping work and
post-baseline implementation work.

Before baseline approval, work may shape and validate:

- product and operator workflow structure
- visual design, component rules, and interaction states
- mock, synthetic, approved read-only, or prototype-local data behavior
- local-only session persistence when it proves the operator workflow
- named reusable patterns and focused smoke or visual checks
- baseline records, change logs, decision logs, and hardening backlog

Before baseline approval, work must not be treated as complete live system
implementation when it needs:

- real-system mutation
- durable backend persistence
- durable receipt or ledger authority
- governed stage or prod runtime
- live model invocation or governed AI action paths
- complete end-to-end regression against live contracts
- promotion out of Prototype Studio into a durable owner repo

Those items belong after baseline approval, during graduation, or in the
durable owner repo unless the prototype record explicitly admits a stronger
data mode and security/governance evidence. `real-readonly` may be used only
when the prototype record and security evidence allow it. `real-mutable`
requires a security trigger review and a governed delivery or graduation plan.

If a design task discovers post-baseline work, record it as a boundary item
instead of half-wiring it into the prototype. The baseline should prove the
operator shape; it should not disguise unfinished backend authority as a
finished workflow.

## Required Project Design Profile

Every active UI prototype needs a design profile under its prototype record.
The profile defines:

- audience and operating context
- visual direction
- typography direction
- color and status semantics
- component and pattern inventory
- responsive policy
- data and source-of-truth assumptions
- interaction and guard behavior
- baseline review states

The profile is not a generic style guide. It is the local design contract for
one prototype or product surface.

## Fast Iteration Rules

- Keep pre-baseline UI iteration local unless remote backup is needed.
- Do not open a PR for every visual tweak.
- Reuse existing patterns before creating a new visual variant.
- Change one coherent surface at a time unless the operator asks for a broader
  redesign.
- Record settled design direction in the design profile instead of relying on
  chat memory.
- Use mock or synthetic data unless the prototype registry explicitly allows a
  stronger data mode.
- Keep the running preview server alive during visual exploration. Restart it
  only when the process is unhealthy or dependencies, config, or startup shape
  changed.

## Exploration Correction Boundary

During pre-baseline exploration, operator-found visual or workflow-shape drift
is part of the local design loop. Correct it in the prototype, update the local
design or workbench contract when the rule is now settled, and continue the
iteration.

Do not route ordinary exploration corrections into workspace-governance
self-improvement records. Create a durable improvement candidate only when the
operator explicitly asks for one, when the issue crosses into baseline-approved
behavior, governed delivery, live/backend authority, security posture,
workspace governance, or when the prototype record itself is being promoted as
a durable baseline.

## Exploration Interaction Gate

Exploration does not require full automated visual testing, but changed
operator controls must be manually exercised before they are called done:

- Identify the changed pattern and compare it to the closest existing good
  pattern.
- Click every new or changed control once in the running preview.
- Confirm each click produces visible operator feedback: state change, route,
  receipt, guard, disabled reason, or an explicit not-wired state.
- Confirm modals are centered, readable, bounded to the viewport, and not
  visually broken by animation or overflow.
- Use focused typecheck only for React, state, data-shape, or TypeScript
  changes.
- Do not run commands that perform a full Next build or rewrite `.next` during
  exploration, including `npm run build`, `npm run check`, or `make validate`,
  unless the operator is preparing a baseline, dependency change, deployment
  readiness check, or explicit completion checkpoint. Use focused typecheck and
  the smallest relevant Playwright verifier for UI iteration.

## Baseline Review Gate

A UI prototype is not baseline-ready until:

- the design profile is current
- repeated elements use named patterns
- filler content has been removed or marked as mock
- key states have been reviewed
- the target viewport policy has been checked
- the focused project validation command passes
- the operator explicitly accepts the baseline

For high-risk visual surfaces, add screenshot or component-state regression
checks after baseline approval.
