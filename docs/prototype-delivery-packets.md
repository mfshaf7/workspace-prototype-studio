# Prototype Delivery Packets

## Purpose

A Prototype Delivery packet is the versioned, source-authoritative record that
prepares one `baseline-approved` prototype for later governed admission into
Workspace Delivery ART. The packet preserves Prototype truth; it does not
admit work, create Delivery records, select Delivery-owned planning metadata,
or claim graduation.

The emitter:

- binds the approved baseline and its digest
- binds an exact Git base, head, and tree
- carries objective, included and excluded scope, remaining work, posture,
  evidence, and resolved source custody
- requires an explicit operator decision reference
- writes one deterministic packet under `records/delivery-packets/`
- links the packet to the `baseline-approved` Prototype without changing lifecycle
- replays the same request without creating a duplicate
- rejects stale, malformed, conflicting, custody-incomplete, or tampered input

WGCF readiness, OOS Delivery application, Delivery-owned metadata, reciprocal
receipts, and final Prototype graduation remain separate downstream work. An
accepted Delivery target receipt is required before the Closure source action
changes lifecycle to `graduating`; packet creation alone is not acceptance.

## Prepare A Request

Create a YAML request outside `records/delivery-packets/` using
`schemas/prototype-delivery-request.schema.json`. The bound source revision must
already contain the approved Prototype registry entry and design-baseline
record.

```yaml
schema_version: 1
prototype_id: sample-prototype
title: Sample governed continuation
objective: Continue the approved prototype through governed Delivery.
included_scope:
  - Preserve the approved operator workflow.
excluded_scope:
  - Do not authorize production deployment.
remaining_work:
  - Wire the durable backend adapter.
evidence_refs:
  - record://evidence/preview-proof
custody:
  classification: existing-repo
  repository_mode: existing
  repository_gate_state: resolved
  owner: workspace-prototype-studio
  source_ref: repo://workspace-prototype-studio@main
  rationale: The governed source already has a durable repository.
authorization:
  decision: approved
  operator_id: operator:workspace-owner
  decision_ref: record://prototype-decisions/sample-delivery-handoff
source_revision:
  repository: workspace-prototype-studio
  ref: refs/heads/main
  base_commit: 1111111111111111111111111111111111111111
  head_commit: 2222222222222222222222222222222222222222
rationale: The approved baseline requires governed continuation.
```

Custody must be one of the contract-resolved shapes:

- `existing-repo` with `existing` and `resolved`
- `new-repo-required` with `new`, `resolved`, and the provisioned source ref
- `platform-internal` or `non-source-work` with `not-required` and a null
  source ref

Pending repository custody is not valid packet input.

## Emit And Validate

```bash
python3 scripts/prototype_delivery_packet.py \
  --repo-root . \
  emit \
  --request /path/to/prototype-delivery-request.yaml

python3 scripts/prototype_delivery_packet.py --repo-root . validate-all
make validate
```

The command returns a compact JSON acknowledgement with `emitted` or
`replayed`, the packet ref, digest, and local path. A rejected command returns a
bounded reason code and does not project a successful lifecycle change.

Review and commit the packet and `prototypes.yaml` together. The Prototype
remains `baseline-approved` with a staged packet reference. The source commit
bound by the packet intentionally precedes the commit that stores the packet;
this avoids self-referential provenance.

## Validation Boundary

Repository validation proves packet schema, deterministic identity, source
ancestry, source tree, baseline identity and digest, registry projection,
evidence completeness, and custody shape. It does not prove WGCF readiness or
Delivery application. Those authorities must produce their own later receipts.
