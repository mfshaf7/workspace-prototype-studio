# Governance Operations Console Prototype

This app is the first read-only prototype for the Workspace Governance
Operations Console.

It uses synthetic data only. It does not call OpenProject, WGCF, CGG, platform
runtime APIs, model providers, or identity services yet.

## Commands

```bash
npm run dev
npm run check
```

## Prototype Boundaries

- Visibility: `private-internal`
- Data mode: `synthetic`
- Mutation boundary: `read-only`
- Runtime lane: `prototype-devint`

The first screen is `Today`, a premium operator cockpit that makes active
fronts, blockers, parked scope, control proof, lanes, operator identity, and
model readiness visible without enabling write or model-backed workflows.

