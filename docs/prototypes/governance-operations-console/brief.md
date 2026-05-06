# Workspace Governance Operations Console

## Purpose

Create the central operator face for the governed workspace system.

The console is not just a Workspace Governance Control Fabric UI. It should
eventually give operators one coherent view across Workspace Delivery ART,
Workspace Proposals, WGCF, CGG, platform runtime state, security review state,
and workspace-governance contracts.

## Users

- workspace operator
- delivery operator
- security reviewer
- future client reviewer for client-safe progress views

## Current Lifecycle

`candidate`

## Visibility And Data

- Visibility tier: `private-internal`
- Data mode: `synthetic`
- Mutation boundary: `read-only`

## Success Signal

The first design baseline shows a useful operator dashboard without depending
on Git as the runtime approval store.

## First Screen Candidate

The first screen is `Today`: a premium read-only operator cockpit that shows
operator identity, inactive model readiness, workspace pulse, the next safe
operator command, control proof, decision queue, lanes, and recent
operator-safe signals.

The visual direction is a calm premium command center, not a dense admin table.
The screen must make it clear within seconds what is active, blocked, parked,
healthy, and ready for operator decision.
