# Prototype Closure Source

Prototype Studio owns the incubation registry and append-only Closure history.
The synchronized [v2 Closure contract](../contracts/prototype-closure/prototype-closure.yaml)
defines the four source transitions. OOS owns workflow coordination, accepted
target reconciliation, and the terminal receipt. Platform owns exact active
incubation runtime disposition. Studio does not grant any of those authorities.

## Operator Path

1. Confirm the active registry state and the exact Studio HEAD. A staged
   Delivery packet leaves lifecycle `baseline-approved`; it is not an accepted
   Delivery target.
2. OOS accepts the request and reconciles action-specific target, owner,
   runtime, or retained-source evidence. Its resolved authority input must bind
   the request digest. A reference string alone is not proof of acceptance.
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

The `resolved-authority` JSON is a source-preparation interface for OOS, not a
self-authenticating receipt. Repository review and OOS receipt reconciliation
must verify its producer and referenced evidence before merge and completion.
Until OOS provides that authenticated path, local preparation demonstrates the
source contract only; it does not prove live end-to-end Closure.
