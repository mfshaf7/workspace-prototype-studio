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
  --prototype-id prototype:sample-tool
```

OOS builds a versioned request under
`contracts/proposal-target-application/request.schema.json`. The request must
bind the current accepted Proposal version, prepared packet and digest,
resolved repository posture, OOS authorization receipt, target identity,
review branch, and exact target state returned above.

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
That packet is input to the separate Landing workflow; all Proposal-provided
name, objective, support, and custody context remains suggestion or constraint
until the operator accepts a Landing request.

## Failure And Replay

The operation fails closed for stale target state, dirty or detached source,
the wrong branch, an unaccepted or stale Proposal, a non-Prototype route,
unresolved or inconsistent repository custody, missing OOS approval, duplicate
Prototype identity, malformed evidence, and conflicting application or
idempotency identities. A failed first application leaves no record or history.

An exact replay creates no second capture and returns the same target and
receipt identities with outcome `replayed`. Reusing either the application id
or idempotency key for different content is rejected. Before apply, cancel by
not submitting the request. After source preparation, OOS owns review-branch
cleanup or continuation; deleting target evidence is not a workflow command.

Validate the contracts and every committed capture with:

```bash
make validate-proposal-target
```
