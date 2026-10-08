# Proposal Target Application

This is the Workspace Prototype Studio owner surface for applying one accepted
Workspace Proposal routed to `prototype`. It creates one target-owned,
`exploring` Prototype capture in Landing state `captured` and returns an exact
readback plus deterministic target receipt.

It deliberately stops there. It does not run Prototype Landing, add the
Prototype to `prototypes.yaml`, create incubation source or documentation,
approve a design baseline, change the Proposal from `accepted`, or claim that
the Proposal is implemented.

## Apply

Read the current optimistic-concurrency state from the clean target branch:

```bash
python3 scripts/proposal_target_application.py state \
  --prototype-id prototype:proposal-851
```

OOS builds a versioned request under
`contracts/proposal-target-application/request.schema.json`. The request must
bind the current accepted Proposal version, prepared packet and digest,
enumerated repository posture, OOS authorization receipt, generated target
identity, digest-derived review branch, and exact target state returned above.

Prototype Studio is public. The request boundary therefore accepts only opaque
canonical references, digests, generated identifiers and labels, timestamps,
and enumerated route or custody posture. It rejects operator identifiers,
Proposal-provided names or objectives, rationale text, custody owner or source
references, and every other unreviewed free-form field before a branch can be
prepared. Private Proposal content stays in the canonical Proposal authority
and OOS transaction state.

Apply it from that same non-default review branch:

```bash
python3 scripts/proposal_target_application.py apply \
  --request /path/to/application.json \
  --output /path/outside/the/repository/result.json
```

The result path must be outside the repository. The source operation writes
only:

- `records/prototype-captures/<id>/record.json`
- the exact immutable application under that record's `history/`

The capture contains a digest-bound `proposal-routed` Prototype Entry Packet.
Its display label is generated from the Proposal number, its objective and
support suggestion are empty, its requester is the OOS service identity, and
its constraints contain only enumerated posture. The packet is input to the
separate Landing workflow; descriptive Proposal content may enter public source
only through that later workflow's separately reviewed admission boundary.

## Failure And Replay

The operation fails closed for stale target state, dirty or detached source,
the wrong branch, an unaccepted or stale Proposal, a non-Prototype route,
unresolved or inconsistent repository custody, missing OOS approval, duplicate
Prototype identity, malformed evidence, free-form or operator fields, and a
conflicting application identity. A failed first application leaves no record
or history.

An exact replay creates no second capture and returns the same target and
receipt identities with outcome `replayed`. Reusing the application id for
different content is rejected. Before apply, cancel by
not submitting the request. After source preparation, OOS owns review-branch
cleanup or continuation; deleting target evidence is not a workflow command.

Validate the contracts and every committed capture with:

```bash
make validate-proposal-target
```
