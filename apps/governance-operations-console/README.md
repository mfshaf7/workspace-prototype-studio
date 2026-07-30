# Governance Operations Console Prototype

This app is the first prototype-local workflow surface for the Workspace
Governance Operations Console.

The current prototype architecture is recorded in
[`../../docs/prototypes/governance-operations-console/system-design.md`](../../docs/prototypes/governance-operations-console/system-design.md).
Operation Workbench implementation rules are governed by
[`../../docs/prototypes/governance-operations-console/operation-workbench-contract.md`](../../docs/prototypes/governance-operations-console/operation-workbench-contract.md).
Current implementation is organized into Console Shell, Command Center,
Operation Workbench, domain workspaces, Lifecycle Transitions, Environment
Lifecycle, Runtime Readiness, Agent Console, product apps, Console Integration,
and Teras boundaries. Operation-domain internals remain private; reusable
cross-operation contracts and product-neutral interface behavior live only in
their explicit shared owners.

It uses synthetic workspace data plus bounded local read-only WSL resource
telemetry from `/proc`. It also has a local-only Ollama trial adapter for the
Agent Interaction Console. The adapter accepts manual operator prompts plus a
bounded synthetic context candidate in Focus mode. It does not inject live or
source-projected OpenProject, WGCF, CGG, repository, terminal, log, or platform
runtime context.

## Commands

```bash
npm run dev
npm run check
npm run architecture
npm run typecheck
npm run test:semantics
npm run test:system-simulation
```

`npm run dev` serves the locked prototype at
`http://127.0.0.1:3317`.

`npm run test:system-simulation` runs the isolated Focus Timer lifecycle proof.
It uses only Console-local state and explicit contract simulators under
`tests/system-simulation`; it does not mutate another repository or claim a
live backend result. Workspace Intake and active-inventory routes consume the
same production-shaped candidate, command, canonical-record, dependency, and
receipt contracts intended for future authority adapters.

## Prototype Boundaries

- Visibility: `private-internal`
- Data mode: `real-readonly`
- Mutation boundary: `prototype-local`
- Runtime lane: `prototype-devint`

The first screen is `Command Center`, an operator cockpit that composes
workspace pulse, actionable attention, governance activity, local WSL host
resources, operator identity, time, operation access, and model readiness
without enabling external-system writes or model-backed canonical mutation.

The WSL resource panel is intentionally narrow: CPU, RAM, virtual memory commit
pressure, network byte counters, and disk usage only. It does not read secrets,
environment variables, logs, repository content, OpenProject data, or client
data.

The Agent Interaction Console is the current implementation shape for the
broader cross-cutting `Agent Console` surface. It is intentionally narrow:

- provider: local Ollama through the server-side Next.js API route
- provider health: one lightweight, non-overlapping source probe with
  observed-time and stale-state semantics; model inventory is not expanded on
  the health polling path
- default endpoint: `http://host.docker.internal:11434`
- default model selection: `OLLAMA_MODEL` when set, otherwise a speed-balanced
  local preference list that currently starts with `llama3.1:8b`
- prompt scope: manual operator text only
- terminal behavior: `Enter` runs, `Shift+Enter` inserts a newline,
  `ArrowUp`/`ArrowDown` navigates prompt history, and local `help`, `status`,
  `mode`, `context`, `clear`, and `reset` commands work without model access
- session continuity: embedded and floating views share recent manual operator
  prompts, local model replies, prompt draft, and interaction mode as bounded
  page-lifetime browser state; use `reset` to clear both the screen and session
  context
- response mode: streamed local model output, so long-running prompts show
  terminal output as it arrives instead of waiting for a full blocking reply
- request lifecycle: one active request across embedded and floating views;
  the Run control becomes Cancel while active, cancellation reaches the
  provider stream, and timed-out or interrupted partial output is never added
  to session context
- denied input: obvious secret-like material
- context rule: General mode attaches no context; Focus mode may attach only a
  bounded synthetic candidate under `prototype-synthetic-only/v1`; live and
  source-projected candidates remain display-only and require governed CGG
  admission
- workspace mode: visible but unavailable until a governed workspace packet
  source exists
- mutation rule: model output does not mutate workspace, ART, repo, platform,
  security, or approval state
- local draft rule: workflow drafts, receipts, and advisor-filled metadata may
  change disposable browser-local prototype state only
