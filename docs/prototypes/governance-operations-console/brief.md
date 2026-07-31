# Workspace Governance Operations Console Brief

Status: graduated prototype history.

This file exists because `prototypes.yaml` requires a brief path. The detailed
system contract lives in [`system-design.md`](system-design.md). Use this file
only for quick orientation.

## Purpose

Create the central operator face for the governed workspace system.

The console is not only a Workspace Governance Control Fabric UI. It gives the
operator one coherent prototype surface across Workspace Proposals, Repository
admission, Workspace Delivery ART, Prototype Studio, managed Product Portfolio,
lifecycle-transition visibility, runtime readiness, model operations, agent
assistance, and authority-owned waiver or accepted-risk decision visibility.

## Graduation State

- lifecycle: `graduated`
- visibility tier: `private-internal`
- data mode: `real-readonly`
- mutation boundary: `prototype-local`
- runtime lane: `owner-repo-local-preview`
- durable source:
  [Governance Operations Console](https://github.com/mfshaf7/governance-operations-console)
- graduation record:
  `record://graduations/governance-operations-console-2026-07-31`

## Read First

- [`README.md`](README.md)
- [`system-design.md`](system-design.md)
- [`architecture/README.md`](architecture/README.md)
- [`operation-workbench-contract.md`](operation-workbench-contract.md)
- [`authority-decision-contract.md`](authority-decision-contract.md)
- [`domain-contracts/`](domain-contracts/README.md)
- [`surface-contracts/`](surface-contracts/README.md)
- [`teras-contract.md`](teras-contract.md)
- [`baseline-candidate-review.md`](baseline-candidate-review.md)
- [`implementation-audit.md`](implementation-audit.md)

## Success Signal

The prototype reaches baseline approval only when the operator workflow,
visual system, source-of-truth boundaries, data and mutation boundaries,
required diagrams, preview proof, and open post-baseline work are recorded and
accepted.

Baseline approval does not mean production authority, stage/prod readiness,
security acceptance, backend mutation approval, or source graduation.
