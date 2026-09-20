# Prototype Closure Source

Prototype Studio owns the incubation registry and append-only Closure history.
The synchronized [v2 Closure contract](../contracts/prototype-closure/prototype-closure.yaml)
defines the four source transitions. OOS owns workflow coordination, accepted
target reconciliation, and the terminal receipt. Platform owns exact active
incubation runtime disposition. Studio does not grant any of those authorities.

## Operator Path

1. Confirm the active registry state and the exact Studio HEAD. A staged
   Delivery packet leaves lifecycle `baseline-approved`; it is not an accepted
   Delivery target. For `apply-delivery`, first apply the committed packet
   through OOS Prototype-to-Delivery ingress and read back the accepted receipt
   and exact ART Epic target. Existing-item attachment is not yet admitted.
2. OOS accepts the Closure request, including that ingress receipt and target,
   and reconciles action-specific owner, runtime, or retained-source evidence.
   Its resolved authority input must bind the request digest. A reference
   string alone is not proof of acceptance.
3. On a clean non-default review branch, prepare the Studio source event:

   ```sh
   python3 scripts/prototype_closure.py --repo-root . prepare \
     --request /path/to/closure-request.json \
     --resolved-authority /path/to/oos-resolved-authority.json
   ```

4. Review and merge the source change. The event binds the exact request,
   prior source revision, prior event digest, and reconciled authority refs.
   The source event never contains the future OOS terminal receipt.
5. On clean merged `main`, read back the exact event:

   ```sh
   python3 scripts/prototype_closure.py --repo-root . readback \
     --event records/prototype-closure/<prototype-id>/history/<sequence>.json
   ```

   OOS validates that readback with the accepted action evidence before it
   records a terminal receipt. If merge outcome is uncertain, reconcile source
   first; do not issue a terminal failed receipt.

`apply-delivery` moves project phase to `delivery-governed` and lifecycle to
`graduating` only after an accepted Delivery target receipt. Source custody
remains `incubation-repo`. `graduate-source` requires accepted durable ownership
and exact transfer or already-owned proof. `retire-incubation` preserves the
Delivery item and durable source, and requires exact runtime disposition proof.
`reopen-incubation` appends a new event and returns to exploration without
restoring a previous runtime. Prior candidate and baseline records remain
historical; a new promotion creates a new active candidate record and baseline.

## Studio Owner Evidence

Before a retirement request, prepare a reviewable retention plan on a clean
Studio source branch:

```sh
python3 scripts/prototype_closure.py --repo-root . prepare-retention \
  --prototype-id <id> --operator-id <operator> --reason <retirement-reason>
```

The command writes a content-addressed plan under
`records/prototype-closure/<id>/retention-plans/`. Review and merge it before
using its returned `record://` reference in a retirement request. It commits
the decision to retain Studio source and history; it does not revoke runtime
resources or retire an accepted Delivery item. WGCF and OOS must read the plan
from the exact trusted Studio main revision, not from a caller-supplied body.

The owner readback command supports both Studio fields:

```sh
python3 scripts/prototype_closure.py --repo-root . owner-readback \
  --field retention_plan_ref --prototype-id <id> \
  --source-revision <trusted-main-commit> --ref <retention-plan-ref> \
  --operator-id <operator> --reason <retirement-reason>
python3 scripts/prototype_closure.py --repo-root . owner-readback \
  --field retained_source_readback_ref --prototype-id <id> \
  --source-revision <trusted-main-commit>
```

Retained-source readback is available only after a committed retirement event
and only when every source path recorded for the prototype is still present.
Both readbacks fail if the trusted main revision differs from the requested
revision. The normal Closure runtime remains inactive until WGCF, OOS, and
Platform consume their respective owner proofs.

The `resolved-authority` JSON is a source-preparation interface for OOS, not a
self-authenticating receipt. Repository review and OOS receipt reconciliation
must verify its producer and referenced evidence before merge and completion.
Until OOS provides that authenticated path, local preparation demonstrates the
source contract only; it does not prove live end-to-end Closure.
