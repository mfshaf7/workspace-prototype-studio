# Prototype Landing

Prototype Landing is the normal source-authoritative path for creating an
`exploring` Prototype in this repository. The authority contract and artifact
schemas are synchronized under `contracts/prototype-landing/`; their manifest
pins the exact Workspace Governance revision and security review used by this
implementation.

## Authority Boundary

Workspace Prototype Studio accepts an immutable Entry Packet, operator-accepted
request, mutation plan, WGCF readiness result, and approved apply command. It
then prepares only Prototype Studio source on the current non-default branch.

The owner command does not:

- decide readiness
- create or merge a pull request
- mutate referenced external source
- activate preview runtime or credentials
- approve a baseline, create Delivery work, or publish a product
- claim merged or terminal workflow success

Those boundaries remain with WGCF, OOS, Platform, Security, and the relevant
downstream owner.

## Source Operation

First capture the current optimistic-concurrency bindings:

```bash
python3 scripts/prototype_landing.py state \
  --prototype-id prototype:sample-tool
```

After the request, plan, readiness, and apply artifacts bind that state, run
the source operation from the clean review branch:

```bash
python3 scripts/prototype_landing.py apply \
  --entry /path/to/entry.json \
  --request /path/to/request.json \
  --plan /path/to/plan.json \
  --readiness /path/to/readiness.json \
  --apply /path/to/apply.json \
  --output-dir /path/outside/the/repository/landing-evidence
```

`--output-dir` must be outside this repository. It receives the review-branch
readback and source-phase receipt for custody by the workflow authority. The
command leaves a reviewable source diff; it does not commit or merge it.

The mutation plan uses exact repository-relative targets:

| Output | Target |
| --- | --- |
| `registry-record` | `prototypes.yaml` |
| `prototype-docs` | `docs/prototypes/<id>` |
| `prototype-source` | `prototypes/<id>` |
| `fixtures` | `fixtures/prototypes/<id>` |
| `preview-profile-draft` | `records/prototype-preview-profiles/<id>.yaml` |
| `validation-plan` | `records/prototype-landings/<id>/validation-plan.yaml` |

Every Landing requires the registry and documentation outputs. New or imported
Studio source also requires `prototype-source`. Reference-only custody cannot
copy source or fixtures. A preview profile remains a non-activating draft.

## Imported Source

Imported content is untrusted. Calculate the bounded canonical digest before
building the request:

```bash
python3 scripts/prototype_landing.py digest-import --source /path/to/source
```

Then pass the same directory with `--import-root` during apply. The command
rejects links, special files, secret-bearing file names, private-key material,
overlong paths, excessive file counts, excessive file size, and digest drift.
It never executes imported content.

## Result And Recovery

The source operation creates:

- one stable registry identity independent of editable name and objective
- one canonical Landing source record
- one immutable apply artifact in the Prototype history
- generated documentation and only the plan-authorized local outputs
- a Git-tree readback and source-preparation receipt

An exact idempotent replay performs no source mutation and emits a replay
receipt. Conflicting keys, stale source, blocked readiness, malformed artifacts,
unsafe imports, dirty source, and write failure leave source unchanged. OOS
later owns review, exact-head merge, merged-authority readback, and the terminal
receipt.

Validate all synchronized contracts and committed Landing records with:

```bash
make validate-landing
```
