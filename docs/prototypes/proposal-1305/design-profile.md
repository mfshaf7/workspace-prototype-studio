# Console To-do design profile

## Status

Exploration. Source delivery is not Candidate or Baseline approval.

## Audience And Context

One person keeping a small list in their browser. The synthetic demonstration
proves add, complete, delete and reload persistence, not multi-user/cloud sync.

## Visual Direction

Quiet paper-like workspace: warm off-white canvas, white list, deep ink text
and muted teal actions. One task-entry form, list and remaining count.
No marketing panels, fake tasks, dashboard chrome or external assets.

## Typography

System sans-serif stack; comfortable 16px controls and task text. No font download.

## Color And Status Semantics

Dark ink for content; teal for actions and checked state. Completion also has a
checked checkbox and struck-through text. Textual storage errors and visible
focus rings; color is never the only signal.

## Pattern Inventory And Source Shape

Intentionally tiny standalone app. No existing shared primitive lives in this
source home. App-local HTML/CSS was explained before implementation; do not
couple it to Console/Teras or introduce a framework.

- index.html: semantic shell, labeled form, list and live status.
- styles.css: app-local shell, form, rows and responsive states.
- tasks.mjs: pure validation/transitions and bounded storage codec.
- app.mjs: DOM events/rendering and browser-local persistence adapter.
- tests/tasks.test.mjs: actual domain/codec behavior, not fixture app success.

## Responsive Policy

360px mobile through desktop; single-column max-width layout. Task text wraps;
controls remain visible. At least 44px touch targets and visible keyboard focus.
Respect reduced motion; retain native checkbox and keyboard semantics.

## Data And Source Of Truth

Synthetic tasks only. Browser localStorage is the sole persistent store.
The server serves read-only static files. No account, API, analytics, external
service or public hosting. Public source and local storage are not private/client
data controls. Start empty; do not seed artificial demonstration tasks.

## Interaction Rules

Enter adds non-blank text. Checkboxes toggle completion; labeled delete buttons
remove the selected task. Keep focus usable after updates. Persist an accepted
edit before reporting success; storage failure leaves the visible list unchanged
and reports failure. Retain invalid saved data rather than silently overwriting
it. Render task text as text, never HTML.

## Exploration Validation Contract

Run node --test prototypes/proposal-1305/tests/tasks.test.mjs for domain/codec
changes. Focused real-browser checks cover keyboard entry, complete/delete,
reload, malicious text, storage rejection, mobile overflow and screenshots.
Run Studio make validate before landing. Actual Console-managed Preview and
lifecycle verification follow reviewed merge; engineering proof is not acceptance.

## Baseline Review States

- Empty: honest empty state, entry affordance, no invented tasks.
- Ready: active/completed rows, long text wrapping, remaining count.
- Error/blocked: visible storage/invalid-data error; no false save success.
- Offline: no external dependencies; the loaded app remains browser-local.
- Keyboard/mobile: labeled controls, focus, no horizontal overflow.
- Modal/backend stale/loading: not applicable to this static local app.

## Authorship And Proof Limit

Operator requested Codex-authored code, not local-model drafting. Reviewed
external source is an explicit Console exercise input. Console must prove
Preview, approval and Delivery; this does not prove autonomous model app quality.
