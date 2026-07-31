# Governance Operations Console Record Index

Status: graduated historical record index.

This directory retains the approved Governance Operations Console prototype
history inside Workspace Prototype Studio. Durable product source and current
product-local records now live in the
[Governance Operations Console owner repository](https://github.com/mfshaf7/governance-operations-console).
Do not resume product implementation from this historical copy.

## Read Order

1. `system-design.md`
   - Full system purpose, work-type taxonomy, global boundaries, source of
     truth model, and prototype lifecycle expectations.
2. `architecture/README.md`
   - Canonical machine-readable system model plus synchronized views for system
     context, operator surfaces, authorities, lifecycle, handoffs, runtime and
     release, and capability maturity.
3. `operation-workbench-contract.md`
   - Shared Operation Workbench engineering, visual, workflow, panel, Teras,
     and drift-control rules.
4. `authority-decision-contract.md`
   - Cross-cutting request, authority, receipt, expiry, and originating-domain
     rules for waiver and accepted-risk decisions.
5. `product-app-boundaries.md`
   - Product-app extraction boundaries for reusable tools currently hosted by
     Operation Workbench domains, including Context Board and Build Tree.
6. `durable-orchestration-standard.md`
   - General qualification, definition, lifecycle, run, ownership, security,
     versioning, and operator-surface rules for durable orchestration.
7. `orchestration-use-case-matrix.md`
   - Locked classification of current Operation Workbench workflows as
     synchronous, conditional, or durable candidates.
8. `orchestration-definitions/`
   - Versioned concrete definition contracts derived from qualified durable
     candidates. The first definition is `delivery.refinement.apply` v1.
9. `orchestration-boundary-contract.md`
   - Cross-domain definition, OOS request, run projection, receipt,
     run-control, and Temporal-adapter boundary rules.
10. `domain-contracts/`
   - Domain-owned contracts for Proposal, Repository, Delivery, Prototype,
     Portfolio, Model Operations, and Orchestration.
   - For Delivery source architecture specifically,
     `domain-contracts/delivery.md` is source-derived from the current
     Delivery code and Delivery-hosted product-app code. If older broad records
     conflict with it on Delivery structure, product-app ownership, or
     no-behavior cleanup rules, use the Delivery contract.
11. `surface-contracts/`
   - Cross-surface contracts for Console navigation, Lifecycle Transition
     Control, Environment Lifecycle, Runtime Readiness, and Agent Console.
   - Read `surface-contracts/console-navigation.md` before changing top-level
     Console entries or moving capability surfaces in or out of Console home.
12. `teras-contract.md`
   - Product-neutral shared UI primitive contract.
13. `baseline-candidate-review.md`
   - Consolidated Baseline Foundation scope, evidence, deferred-owner ledger, validation,
     and the explicit operator approval gate.
14. `implementation-audit.md`
   - Current source alignment, operation ownership, integration boundaries,
     executable controls, and deliberate prototype limits.
15. Registry-required current records:
   - `brief.md`
   - `design-profile.md`
   - `backlog.md`
   - `decision-log.md`
   - `change-log.md`

The records below preserve the approved baseline and its design history. Their
source paths and implementation-maturity statements describe the prototype at
the time of approval; current product decisions belong in the owner repository.

## Resume Rule

After context compaction or restart, use this index only for prototype
provenance. Resume current Console work from the owner repository.

## Phase Discipline

The graduated product retains this historical phase discipline:

1. Normalize records and read order.
2. Confirm or update the relevant domain or surface contract.
3. Inspect current code against that contract.
4. Make the smallest implementation slice that follows the contract.
5. Validate the affected slice.
6. Report remaining percentage against the active full-plan phase and the next
   move.

Current changes must update the corresponding records and validation in the
owner repository, not this archived packet.
