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

Validate every profile before operating one:

```bash
make validate-preview-runtime
```

Start the current Client Review Portal profile with a unique request id:

```bash
python3 scripts/prototype_preview.py start \
  --profile records/prototype-preview-profiles/client-review-portal.yaml \
  --request-id operator-start-001
```

The same request id replays the original receipt. Reusing it for another
action fails closed. The command returns a digest-bound receipt and stores only
runtime metadata beneath the operator's runtime directory, outside the repo.

Inspect the safe projection or prove exact operating readback:

```bash
python3 scripts/prototype_preview.py status \
  --profile records/prototype-preview-profiles/client-review-portal.yaml
python3 scripts/prototype_preview.py proof \
  --profile records/prototype-preview-profiles/client-review-portal.yaml
```

Restart or stop with new request ids:

```bash
python3 scripts/prototype_preview.py restart \
  --profile records/prototype-preview-profiles/client-review-portal.yaml \
  --request-id operator-restart-001
python3 scripts/prototype_preview.py stop \
  --profile records/prototype-preview-profiles/client-review-portal.yaml \
  --request-id operator-stop-001
```

`status` is read-only. `proof` verifies the current process, exact profile,
source revision and digest, maturity claim, boundary controls, and latest
receipt without starting, restarting, or stopping anything. This makes it safe
for OOS operating-evidence acquisition after the exact Security gate has been
satisfied.

## Failure and recovery

- A non-loopback profile, public ingress, external network use, real data, or
  mutable boundary is invalid.
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
