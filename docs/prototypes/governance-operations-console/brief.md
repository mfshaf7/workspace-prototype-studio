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

