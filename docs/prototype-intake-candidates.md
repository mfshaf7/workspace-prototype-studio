# Prototype Intake Candidates

This is the primary operator path for projecting a baseline-approved prototype
as a possible Workspace Intake entrant. It is not the Delivery handoff command.
The adapter reads committed source and emits JSON; it writes no registry,
lifecycle, ART, remote repository, or active inventory state.

## Prepare And Emit

Supply a JSON input matching `$defs.input` in
[the candidate schema](../schemas/prototype-intake-candidate.schema.json):

- `schema_version`: `1`
- `prototype_id`: the stable id in committed `prototypes.yaml`
- `source_revision`: repository `workspace-prototype-studio`, a full branch ref,
  its exact 40-character head commit, and an ancestor base commit
- `suggested_target`: a `repo`, `product`, or `component` kind and slug name
- `rationale`: why this prototype should be evaluated as a workspace entrant

```bash
python3 scripts/prototype_intake_candidate.py emit --request request.json
python3 scripts/prototype_intake_candidate.py validate --candidate candidate.json
```

The caller captures the emitted JSON as its candidate artifact. Output carries
the committed name, prototype owner, lifecycle, posture, typed links, approved
baseline digest and evidence refs. The operator may suggest a different target
name without renaming the prototype or losing its stable source identity.
The source owner is context, not a new target-owner assignment.

Only `baseline-approved` and `graduating` sources with an approved, correctly
linked baseline are eligible. Missing, duplicate, stale, or uncommitted source
cannot supply candidate truth. The supplied checkout must be the trusted
Prototype source checkout; accepting arbitrary uploads is not this adapter's
authority or a replacement for service authentication.

## Submit Through Intake

Successful current-source validation emits a `source` object compatible with
Workspace Intake v2: class `prototype`, candidate ref, and candidate digest.
OOS/Console must retain the candidate artifact, revalidate current source before
submission, and bind this source object into the separate intake request.
The target is a suggestion. Requested classification, target owner routing,
canonical expected state and explicit acceptance belong to Workspace Intake.

The digest uses Prototype's existing canonical JSON encoding: sorted keys,
compact separators and ASCII-escaped Unicode. It binds `content`, not the
self-referential envelope. Workspace Intake treats this as an opaque source
digest; its own request/decision canonicalization is a different contract.

Identical input and committed source produce identical candidates. A rename or
new source commit produces new evidence linked to the same prototype id. It
does not overwrite, retire, or duplicate an already-admitted workspace record;
that decision remains in Workspace Intake.

## Cancel, Retry And History

Before submission, discard the candidate to stop: no source state was changed.
After OOS accepts the request, use its cancel/continue commands. Do not cancel
by deleting baseline evidence or rewinding the prototype lifecycle. Retained
candidates stay immutable evidence even when their intake request is cancelled.
There is deliberately no second Prototype intake workflow or cancellation store.

`validate --historical` verifies retained evidence against its original commit
after the source branch moves. It does not establish current submission
readiness. Default validation rejects that stale branch binding. The existing
[Delivery packet workflow](prototype-delivery-packets.md) remains responsible
for its own lifecycle transition and is unchanged by candidate emission.

## Validation

```bash
python3 -m unittest discover -s tests -p test_prototype_intake_candidate.py
make validate
```

Tests use isolated real Git repositories and fresh CLI subprocesses. They cover
complete and incomplete inputs, replay, discarded candidates, source and target
rename, stale history, lifecycle/approval gates, duplicate identity, forged
context/digests, uncommitted fixtures, foreign ownership and unrelated ancestry.
They do not claim live Workspace Intake, provider access, Security acceptance,
inventory activation or product publication.
