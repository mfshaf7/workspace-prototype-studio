# Prototype Maturity Source Operations

Workspace Prototype Studio owns the source transitions from `exploring` to
`candidate` and from `candidate` to `baseline-approved`. The governing contract
and artifact schemas are synchronized under `contracts/prototype-maturity/`.
Their manifest pins the exact Workspace Governance contract and Security
Architecture review accepted by this implementation.

## Authority Boundary

The source command consumes a maturity request, evidence packet, WGCF readiness
result, and explicit operator decision. It validates their schemas, digests,
bindings, current source state, transition-specific fields, evidence references,
and decision semantics before considering source mutation.

The command does not:

- evaluate readiness or evidence sufficiency
- make the maturity decision
- create or merge a pull request
- mutate source outside the Prototype registry and transition-owned records
- change project phase, custody, runtime, release, Security, Delivery, or
  Portfolio state
- emit a terminal maturity receipt

OOS owns durable workflow coordination and the terminal receipt. WGCF owns
readiness. The operator owns the decision. Source truth changes only through a
reviewed merge and is proven afterward by merged readback.

## Source Operation

Capture the exact optimistic-concurrency state before constructing the request:

```bash
python3 scripts/prototype_maturity.py state \
  --prototype-id prototype:sample-tool
```

After the complete artifact chain is available, prepare the decision:

```bash
python3 scripts/prototype_maturity.py apply \
  --request /path/to/request.json \
  --packet /path/to/packet.json \
  --readiness /path/to/readiness.json \
  --decision /path/to/decision.json \
  --output /path/outside/the/repository/source-result.json
```

Promotion requires a clean non-default branch matching the decision. Candidate
Promotion changes only:

- `prototypes.yaml`
- `records/prototype-maturity/<id>/candidate.json`
- `records/prototype-maturity/<id>/history/<decision-id>.json`

Baseline Promotion changes only:

- `prototypes.yaml`
- `records/design-baselines/<baseline-id>.yaml`
- `records/prototype-maturity/<id>/history/<decision-id>.json`

Block and route-closeout decisions write no Prototype source. Their source
result reports the unchanged lifecycle and routes the next action back to OOS.

## Merged Readback

After the reviewed source change is merged, read canonical authority from the
default branch:

```bash
python3 scripts/prototype_maturity.py readback \
  --decision /path/to/decision.json \
  --output /path/outside/the/repository/readback.json
```

Promotion readback requires the expected source revision to be an ancestor of
the current default-branch head, the target lifecycle to be present, and the
exact immutable decision to exist in source history. Non-promotion readback
requires the original lifecycle and record digest to remain unchanged.

The source result and readback paths must stay outside this repository. They
are workflow evidence for OOS custody, not canonical Prototype records.

## Recovery And Validation

Identical replay returns a replay result without another mutation. Conflicting
idempotency reuse, stale source, unsafe or unbounded values, unsupported
references, wrong branches, blocked readiness, path collisions, and write
failures stop without partial source state.

Validate synchronized contracts and all committed maturity records with:

```bash
make validate-maturity
```
