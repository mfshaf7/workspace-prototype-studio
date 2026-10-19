# Prototype Authoring Owner Preparation

## Availability and authority

This is the source-owned, read-only preparation boundary for later Console/OOS
authoring. It does not make the complete Console workflow operational, invoke
a model, apply source, approve a design, create a Delivery packet or activate
a Preview. OOS and the isolated source executor must consume the exact owner
plan; Security and Platform must accept and commission the complete source
chain before the new purpose operates.

Use this as the primary Studio procedure for source/design scope and executable
Preview preparation. Existing [Maturity](prototype-maturity.md) remains the only
Candidate/Baseline producer, and [Delivery packets](prototype-delivery-packets.md)
remain the only packet producer. A preparation is neither their receipt nor
evidence that an app exists.

## Procedure

1. Read the exact committed Studio snapshot and selected Prototype. OOS must
   prove canonical owner/Landing/currentness and bind the authenticated caller,
   operator, session and execution before it uses this scope for source actions.
2. Inspect only that Prototype's committed application and draft design scope:

   ```bash
   python3 scripts/prototype_authoring.py --repo-root . inspect \
     --prototype-id prototype:sample-tool --source-revision <exact-Git-commit>
   ```

   The result carries its actual Prototype identity, independent registry and
   source binding, safe file names/digests, design digest and finite model scope.
   It contains no raw app contents. Stage source context through CGG before
   model use; the inspected registry record is not itself a model-safe packet.
   Only explicit Studio incubation custody is supported by this producer.
   Dedicated/private source custody must use its own admitted owner path rather
   than silently writing into public Studio. Unknown, ambiguous, stale, dirty,
   graduated, symlinked, credential-shaped or cross-Prototype scope is denied.
3. Review Preview intent with a closed JSON request matching
   `schemas/prototype-preview-preparation-request.schema.json`. Bind the exact
   source revision, Prototype, operator/decision reference, port, support mode,
   activation intent and TTL. The caller cannot supply arbitrary paths,
   commands, source contents, policy, boundary labels or credentials.
4. Render the exact deterministic owner file plan:

   ```bash
   python3 scripts/prototype_authoring.py --repo-root . plan-preview \
     --request /path/to/reviewed-preview-request.json
   ```

   This does not write files. It derives the source/profile path and boundary
   from the committed registry, returns one profile change with its previous
   content digest, and binds request/operator/source/plan digests. It rejects
   conflicting active committed Preview ports; the runtime independently checks
   actual port/process availability when starting. A returned port is not a
   reservation or proof that a process is running.
5. The future OOS action must accept that exact plan and apply it through the
   existing Gary/executor transaction, owner validation and exact-head human
   review. It cannot treat arbitrary caller/model file plans as owner authority.
   No second mutation journal, default-branch write or owner-success receipt is
   provided by this command. Crash recovery belongs to the existing immutable
   source action, not a new Studio coordination store.
6. After reviewed merge, use the existing [Preview procedure](devint-prototype-preview.md).
   Record real browser behavior separately from server/profile proof. Source
   generation, running Preview, design acceptance and Delivery readiness are
   separate facts.
7. After real Baseline acceptance, prepare the existing Delivery request and
   invoke its existing deterministic emitter on the owner review branch through
   OOS. Preserve baseline digest, Git base/head/tree, custody and operator
   decision. Inspection reports lifecycle applicability only; it does not
   evaluate packet readiness or manufacture a baseline/transfer receipt.

## Model and source boundary

Model-writable files belong only under the selected Prototype application root
and its exact draft design-profile path. Registry lifecycle, executable Preview
profile, policy, schema, CI, credentials, approval, baseline, transfer evidence
and publication manifests are not model-writable. Deterministic owner commands
and the reviewed source executor retain those boundaries.

The current public synthetic demo does not qualify private/client custody.
Neither a `private-internal` record label nor a plan digest creates provider
access control. No arbitrary language/toolchain, backend service, package
distribution, stage/prod or external hosting capability is implied.

## Failure and recovery

Preparation is read-only and deterministic for the same committed source and
request. Repeating it needs no mutation/replay journal. If source or accepted
intent changes, prepare again and obtain exact new acceptance before applying;
never reuse an acknowledged source-action identity with different content.

The CLI returns bounded `rejected` codes without echoing raw input. Dirty or
stale source, unsupported custody/boundary, absent source/design, wrong
Prototype, unsafe files, malformed request and committed port conflict are
actionable denials, not successful app generation. Do not bypass them with an
ambient human push, another repository, fake ART identity or raw model context.

## Validation

Run `python3 -m unittest discover -s tests -p test_prototype_authoring.py` for
temporary real-Git owner preparation and isolated loopback process proof.
Run `make validate` from the clean committed owner head before landing. Tests
do not write the real demo or create live lifecycle records. Browser-local
add/complete/delete/reload operation remains separate actual Console proof.
