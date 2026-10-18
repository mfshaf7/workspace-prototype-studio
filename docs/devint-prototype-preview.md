# Prototype Preview Runtime

`prototype-devint` is a lane class, not a new environment name.

The technical environment remains `dev-integration`. The lane class tells the
operator that the runtime is for prototype preview and is not governed stage,
prod, or release evidence.

Prototype devint profiles must declare:

- source repos
- runtime shape
- data mode
- mutation boundary
- persistence model
- cleanup owner
- TTL or retirement rule
- promotion or graduation path

The Workspace Prototype Studio owns the local Preview Runtime. It is a small
loopback-only static process for incubation review. It is not a shared Platform
environment, does not open public ingress, does not call external services, and
does not grant stage, production, release, or security acceptance.

## Primary operator commands

Landing may first emit an inert six-field draft under the profile directory.
`schemas/prototype-preview-draft.schema.json` validates that closed metadata
shape, its known Prototype and matching filename. It does not assign a port,
authorize serving source, or admit a runtime. `validate-all` validates both
these drafts and fully configured profiles; it does not skip draft validation.
Runtime commands still require the separate complete profile schema and its
existing activation and boundary checks. A valid Landing draft is not a
runnable profile, Preview proof, or product implementation.

The [owner preparation procedure](prototype-authoring.md) renders a complete
profile change plan without writing or activating it. Registry and runtime
enforce the same exact Prototype/source/boundary binding. The schema admits
only two persistence tuples: `none`/`runtime-metadata-only`, or
`prototype-local`/`browser-local`, with mock/synthetic internal review and no
backend writes or external services. Mixed tuples and durable/backend storage
remain invalid. The new tuple needs exact-source Security acceptance and
coherent commissioning; the older none-only decision does not authorize it.

Browser-local data belongs to its reviewed browser origin, not the server's
runtime metadata or a durable backend. It survives reload and may survive
server stop/restart; stopping does not erase browser storage. The runtime proof
tests actual denied HTTP write methods and reports its storage declaration,
but explicitly sets `browser_operation_proven: false`. Only a separate real
browser exercise can prove app persistence. CSP disables connections/forms/
workers and external subresources for this static profile; it is not a general
hostile-JavaScript browser/network sandbox or private-client isolation proof.

Validate every profile before operating one:

```bash
make validate-preview-runtime
```

Read the current owner projection, then start the Client Review Portal profile
with that exact reviewed state and a unique request id:

```bash
PROFILE=records/prototype-preview-profiles/client-review-portal.yaml
EXPECTED="$(python3 scripts/prototype_preview.py status --profile "$PROFILE")"
python3 scripts/prototype_preview.py start \
  --profile "$PROFILE" \
  --request-id operator-start-001 \
  --expected-state "$EXPECTED"
```

The same request id replays the original receipt. Reusing it for another
action fails closed. The command returns a digest-bound receipt and stores only
runtime metadata beneath the operator's runtime directory, outside the repo.
The owner compares the expected instance, runtime state, profile digest, source
digest, and source revision while holding the same lock used for mutation. A
changed state is rejected before any action.

Inspect the safe projection or prove exact operating readback:

```bash
python3 scripts/prototype_preview.py status \
  --profile records/prototype-preview-profiles/client-review-portal.yaml
python3 scripts/prototype_preview.py proof \
  --profile records/prototype-preview-profiles/client-review-portal.yaml
```

Restart or stop with new request ids:

```bash
EXPECTED="$(python3 scripts/prototype_preview.py status --profile "$PROFILE")"
python3 scripts/prototype_preview.py restart \
  --profile "$PROFILE" \
  --request-id operator-restart-001 \
  --expected-state "$EXPECTED"
EXPECTED="$(python3 scripts/prototype_preview.py status --profile "$PROFILE")"
python3 scripts/prototype_preview.py stop \
  --profile "$PROFILE" \
  --request-id operator-stop-001 \
  --expected-state "$EXPECTED"
```

`status` is read-only. `proof` verifies the current process, exact profile,
source revision and digest, maturity claim, boundary controls, and latest
receipt without starting, restarting, or stopping anything. This makes it safe
for OOS operating-evidence acquisition after the exact Security gate has been
satisfied.

## Failure and recovery

- A non-loopback profile, public ingress, configured external services, real
  data, server mutation or persistence outside the two admitted tuples is invalid.
- A dirty checkout, untracked served file, ignored served file, or symlinked
  served file is rejected before status, mutation, or proof can claim the
  reviewed source revision.
- A stale PID or health mismatch is reported as `stale`; commands do not kill
  an unverified process.
- A port conflict fails start and points to the operator-private runtime log.
- Static serving denies traversal, dotfiles, directories, symlinks, and every
  mutation method.
- Stop removes live state but preserves command receipts for review. The
  cleanup owner is Workspace Prototype Studio.

Security review of the exact Studio and Console revisions remains required by
`gate:preview-runtime-operating-acceptance` before OOS accepts the Feature as
operating-ready.
