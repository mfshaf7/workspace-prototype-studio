# Prototype Design Profile

## Status

`exploration`

## Audience And Context

Describe who uses the interface and where they use it.

## Visual Direction

Describe the desired feeling, density, and visual language.

## Typography

State the intended typography direction.

## Color And Status Semantics

Define the palette and what each status color means.

## Pattern Inventory

- Panel:
- Tray:
- Table:
- Modal:
- Form:
- Status card:
- Action control:

## Responsive Policy

State whether desktop, tablet, and mobile are supported, deferred, or blocked.

## Data And Source Of Truth

Define whether the view uses mock, synthetic, real-readonly, or real-mutable
data and where live data will come from later.

## Interaction Rules

Describe selection, expansion, guard, confirmation, and unsafe-exit behavior.

## Exploration Validation Contract

- During `exploration`, do not run full builds after ordinary visual tweaks.
- Keep the running preview server alive unless it is unhealthy or dependencies,
  config, or startup shape changed.
- Use focused typecheck for React, state, data-shape, or TypeScript changes.
- Use the smallest relevant Playwright or manual preview check for changed
  operator controls.
- Reserve full build or repo-wide validation for baseline, dependency,
  deployment, or explicit completion checkpoints.

## Baseline Review States

- Empty:
- Loading:
- Ready:
- Warning:
- Blocked:
- Error:
- Offline:
- Selected:
- Modal open:
