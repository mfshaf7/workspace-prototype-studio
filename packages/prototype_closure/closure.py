from __future__ import annotations

import copy
import fcntl
import hashlib
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from packages.prototype_delivery_packet.contract import (
    PacketError,
    canonical_json_bytes,
    content_digest,
    load_json,
    load_yaml,
    validate_schema,
)
from packages.prototype_delivery_packet.git_provenance import load_yaml_at_revision, run_git


CONTRACT_DIR = Path("contracts/prototype-closure")
HISTORY_DIR = Path("records/prototype-closure")
EVENT_TYPES = {
    "apply-delivery": "delivery-accepted",
    "graduate-source": "source-graduated",
    "retire-incubation": "incubation-retired",
    "reopen-incubation": "incubation-reopened",
}
SAFE_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _validator(repo_root: Path, filename: str) -> Draft202012Validator:
    schema = load_json(repo_root / CONTRACT_DIR / filename)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_contract_bundle(repo_root: Path) -> None:
    bundle = repo_root / CONTRACT_DIR
    manifest = load_json(bundle / "manifest.json")
    if manifest.get("authority_repo") != "workspace-governance":
        raise PacketError("contract_bundle_invalid", "Closure authority repo is invalid")
    if manifest.get("authority_commit") != "a35bcdc9514716d1b698d05ca9d288aca6490aeb":
        raise PacketError("contract_bundle_invalid", "Closure authority revision is invalid")
    security_review = manifest.get("security_review") or {}
    if security_review.get("decision") != "approved-with-findings" or not security_review.get("merge_commit"):
        raise PacketError("contract_bundle_invalid", "Closure security review is not accepted")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise PacketError("contract_bundle_invalid", "Closure contract manifest has no files")
    for name, expected in files.items():
        path = bundle / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise PacketError("contract_bundle_stale", f"synchronized Closure contract differs for {name}")
    contract = load_yaml(bundle / "prototype-closure.yaml")
    if contract.get("schema_version") != 2 or contract.get("owner_repo") != "workspace-governance":
        raise PacketError("contract_bundle_invalid", "Closure contract is not v2 workspace authority")


def _validate_request(repo_root: Path, request: dict[str, Any]) -> None:
    validate_schema(
        _validator(repo_root, "prototype-closure-request.schema.json"),
        request,
        code="request_invalid",
        label="Prototype Closure request",
    )
    if not SAFE_ID.fullmatch(request["prototype_id"]):
        raise PacketError("request_invalid", "prototype_id is not a safe registry id")


def _validate_event(repo_root: Path, event: dict[str, Any]) -> None:
    validate_schema(
        _validator(repo_root, "prototype-closure-history-event.schema.json"),
        event,
        code="event_invalid",
        label="Prototype Closure event",
    )


def _registry_item(registry: dict[str, Any], prototype_id: str) -> dict[str, Any]:
    matches = [item for item in registry.get("prototypes", []) if item.get("id") == prototype_id]
    if len(matches) != 1:
        raise PacketError("prototype_not_found", f"expected one registry item for {prototype_id}")
    return matches[0]


def _custody(item: dict[str, Any]) -> str:
    custody = item.get("source_custody")
    if custody:
        return custody
    if item["lifecycle"] == "graduated":
        raise PacketError("source_custody_missing", "graduated source custody must be explicit")
    return "incubation-repo"


def _history_paths(repo_root: Path, prototype_id: str) -> list[Path]:
    return sorted((repo_root / HISTORY_DIR / prototype_id / "history").glob("*.json"))


def _history(repo_root: Path, prototype_id: str) -> list[dict[str, Any]]:
    paths = _history_paths(repo_root, prototype_id)
    events = [load_json(path) for path in paths]
    prior_digest = None
    for index, (path, event) in enumerate(zip(paths, events), start=1):
        _validate_event(repo_root, event)
        if path.name != f"{index:04d}.json" or event["event_id"] != f"prototype-closure:{prototype_id}:{index:04d}":
            raise PacketError("history_invalid", "Closure event path or sequence differs")
        if event["prototype_id"] != prototype_id or event["prior_event_digest"] != prior_digest:
            raise PacketError("history_invalid", "Closure history prototype or prior digest differs")
        prior_registry = load_yaml_at_revision(
            repo_root, event["expected_source_revision"], Path("prototypes.yaml")
        )
        prior_item = _registry_item(prior_registry, prototype_id)
        if (
            prior_item["lifecycle"] != event["previous_lifecycle"]
            or _custody(prior_item) != event["previous_source_custody"]
        ):
            raise PacketError("history_invalid", "Closure event prior state differs from its source revision")
        prior_digest = content_digest(event)
    return events


def _resolved_ref(resolved: dict[str, Any], name: str) -> str:
    value = resolved.get(name)
    if not isinstance(value, str) or not value.strip():
        raise PacketError("authority_missing", f"reconciled authority lacks {name}")
    return value


def _event_for(
    request: dict[str, Any],
    resolved: dict[str, Any],
    item: dict[str, Any],
    prior_digest: str | None,
    sequence: int,
    now: str,
) -> dict[str, Any]:
    action = request["action"]
    event = {
        "schema_version": 2,
        "artifact_type": "prototype-closure-history-event",
        "event_id": f"prototype-closure:{request['prototype_id']}:{sequence:04d}",
        "request_ref": request["request_id"],
        "request_digest": content_digest(request),
        "prototype_id": request["prototype_id"],
        "event_type": EVENT_TYPES[action],
        "expected_source_revision": request["expected_source_revision"],
        "previous_lifecycle": item["lifecycle"],
        "previous_source_custody": _custody(item),
        "operator_id": request["operator_id"],
        "correlation_id": request["correlation_id"],
        "idempotency_key": request["idempotency_key"],
        "prior_event_digest": prior_digest,
        "recorded_at": now,
    }
    if action == "apply-delivery":
        if not item.get("delivery_packet_ref") or not item.get("design_baseline_ref"):
            raise PacketError("delivery_packet_missing", "Delivery application requires a staged packet and baseline")
        if _resolved_ref(resolved, "accepted_delivery_target_receipt_ref") != request["accepted_delivery_target_receipt_ref"]:
            raise PacketError("authority_mismatch", "accepted Delivery receipt differs from requested ingress receipt")
        if _resolved_ref(resolved, "target_delivery_ref") != request["target_delivery_ref"]:
            raise PacketError("authority_mismatch", "accepted Delivery target differs from requested ART target")
        event.update(
            observed_lifecycle="graduating",
            observed_source_custody="incubation-repo",
            accepted_baseline_receipt_ref=request["accepted_baseline_receipt_ref"],
            accepted_delivery_target_receipt_ref=request["accepted_delivery_target_receipt_ref"],
        )
    elif action == "graduate-source":
        if item.get("project_phase") != "delivery-governed":
            raise PacketError("project_phase_invalid", "source graduation requires Delivery-governed phase")
        if item.get("accepted_delivery_target_receipt_ref") != request["accepted_delivery_target_receipt_ref"]:
            raise PacketError("authority_mismatch", "graduation Delivery receipt differs from accepted Studio target")
        if resolved.get("durable_owner_acceptance_ref") != request["durable_owner_acceptance_ref"]:
            raise PacketError("authority_mismatch", "durable owner acceptance differs from request")
        for field in ("durable_owner_ref", "durable_repo_ref"):
            if resolved.get(field) != request[field]:
                raise PacketError("authority_mismatch", f"accepted {field} differs from request")
        custody = resolved.get("observed_source_custody")
        if custody not in {"dedicated-owner-repo", "shared-owner-repo"}:
            raise PacketError("custody_invalid", "graduation requires an accepted durable source custodian")
        event.update(
            observed_lifecycle="graduated",
            observed_source_custody=custody,
            accepted_delivery_target_receipt_ref=request["accepted_delivery_target_receipt_ref"],
            durable_owner_acceptance_ref=request["durable_owner_acceptance_ref"],
        )
        if request["transfer_strategy"] == "already-owned":
            if resolved.get("already_owned_source_proof_ref") != request["already_owned_source_proof_ref"]:
                raise PacketError("authority_mismatch", "already-owned source proof differs from request")
            event["already_owned_source_proof_ref"] = request["already_owned_source_proof_ref"]
        else:
            event["source_transfer_receipt_ref"] = _resolved_ref(resolved, "source_transfer_receipt_ref")
    elif action == "retire-incubation":
        if resolved.get("retention_plan_ref") != request["retention_plan_ref"]:
            raise PacketError("authority_mismatch", "retention plan differs from request")
        if resolved.get("runtime_disposition_plan_ref") != request["runtime_disposition_plan_ref"]:
            raise PacketError("authority_mismatch", "runtime disposition plan differs from request")
        event.update(
            observed_lifecycle="retired",
            observed_source_custody=_custody(item),
            retention_plan_ref=request["retention_plan_ref"],
            runtime_disposition_proof_ref=_resolved_ref(resolved, "runtime_disposition_proof_ref"),
        )
    else:
        if resolved.get("prior_retirement_receipt_ref") != request["prior_retirement_receipt_ref"]:
            raise PacketError("prior_retirement_mismatch", "resolved retirement receipt differs from request")
        if not item.get("retirement_ref") or resolved.get("prior_retirement_event_ref") != item["retirement_ref"]:
            raise PacketError("prior_retirement_mismatch", "resolved retirement event is not the active Studio record")
        event.update(
            observed_lifecycle="exploring",
            observed_source_custody="incubation-repo",
            prior_retirement_receipt_ref=request["prior_retirement_receipt_ref"],
            retained_source_readback_ref=_resolved_ref(resolved, "retained_source_readback_ref"),
        )
    return event


def _updated_registry(registry: dict[str, Any], event: dict[str, Any], resolved: dict[str, Any]) -> dict[str, Any]:
    updated = copy.deepcopy(registry)
    item = _registry_item(updated, event["prototype_id"])
    item["lifecycle"] = event["observed_lifecycle"]
    item["source_custody"] = event["observed_source_custody"]
    item["closure_event_ref"] = f"record://prototype-closure/{event['prototype_id']}/history/{event['event_id']}"
    if event["event_type"] == "delivery-accepted":
        item["project_phase"] = "delivery-governed"
        item["delivery_target_ref"] = resolved["target_delivery_ref"]
        item["accepted_delivery_target_receipt_ref"] = event["accepted_delivery_target_receipt_ref"]
    elif event["event_type"] == "source-graduated":
        item["graduation_ref"] = item["closure_event_ref"]
        item["durable_owner_ref"] = resolved["durable_owner_ref"]
        item["durable_repo_ref"] = resolved["durable_repo_ref"]
    elif event["event_type"] == "incubation-retired":
        item["retirement_ref"] = item["closure_event_ref"]
    elif event["event_type"] == "incubation-reopened":
        for field in ("candidate_record_ref", "design_baseline_ref", "delivery_packet_ref"):
            item.pop(field, None)
    return updated


@contextmanager
def _lock(repo_root: Path) -> Iterator[None]:
    common = Path(run_git(repo_root, "rev-parse", "--git-common-dir"))
    if not common.is_absolute():
        common = (repo_root / common).resolve()
    with (common / "prototype-closure.lock").open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _write_source(writes: dict[Path, bytes]) -> None:
    originals: dict[Path, bytes | None] = {}
    try:
        for path, content in writes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            originals[path] = path.read_bytes() if path.exists() else None
            descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            try:
                with os.fdopen(descriptor, "wb") as stream:
                    stream.write(content)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(name, path)
            finally:
                Path(name).unlink(missing_ok=True)
    except BaseException:
        for path, original in reversed(tuple(originals.items())):
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise


def prepare_transition(
    repo_root: Path,
    request: dict[str, Any],
    resolved: dict[str, Any],
    *,
    recorded_at: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    repo_root = repo_root.resolve()
    validate_contract_bundle(repo_root)
    _validate_request(repo_root, request)
    if (
        resolved.get("artifact_type") != "prototype-closure-resolved-authority"
        or resolved.get("issuer") != "operator-orchestration-service"
    ):
        raise PacketError("authority_invalid", "Closure source preparation requires OOS-reconciled authority")
    if resolved.get("request_digest") != content_digest(request):
        raise PacketError("authority_mismatch", "reconciled authority does not bind the exact request")
    branch = run_git(repo_root, "branch", "--show-current")
    if not branch or branch in {"main", "master"}:
        raise PacketError("source_branch_invalid", "Closure source change requires a named non-default review branch")
    now = recorded_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with _lock(repo_root):
        all_paths = sorted((repo_root / HISTORY_DIR).glob("*/history/*.json"))
        for existing_path in all_paths:
            existing = load_json(existing_path)
            if existing.get("idempotency_key") != request["idempotency_key"]:
                continue
            _history(repo_root, existing["prototype_id"])
            if existing.get("request_digest") != content_digest(request):
                raise PacketError("idempotency_conflict", "idempotency key is bound to a different request")
            if request["action"] == "apply-delivery":
                for key in ("accepted_delivery_target_receipt_ref", "target_delivery_ref"):
                    if resolved.get(key) != request[key]:
                        raise PacketError("idempotency_conflict", f"reconciled {key} changed under the same key")
            for key in (
                "accepted_delivery_target_receipt_ref", "durable_owner_acceptance_ref",
                "source_transfer_receipt_ref", "runtime_disposition_proof_ref", "retained_source_readback_ref",
            ):
                if key in existing and existing[key] != resolved.get(key) and existing[key] != request.get(key):
                    raise PacketError("idempotency_conflict", f"reconciled {key} changed under the same key")
            if (
                "observed_source_custody" in resolved
                and resolved["observed_source_custody"] != existing["observed_source_custody"]
            ):
                raise PacketError("idempotency_conflict", "source custody changed under the same key")
            return existing_path, existing
        head = run_git(repo_root, "rev-parse", "HEAD")
        if request["expected_source_revision"] != head:
            raise PacketError("source_revision_stale", "Closure request does not name current source HEAD")
        if run_git(repo_root, "status", "--porcelain"):
            raise PacketError("dirty_worktree", "Closure source preparation requires a clean worktree")
        registry = load_yaml(repo_root / "prototypes.yaml")
        item = _registry_item(registry, request["prototype_id"])
        if item["lifecycle"] != request["expected_lifecycle"]:
            raise PacketError("lifecycle_stale", "Closure request lifecycle differs from source")
        history = _history(repo_root, request["prototype_id"])
        prior_digest = content_digest(history[-1]) if history else None
        event = _event_for(request, resolved, item, prior_digest, len(history) + 1, now)
        _validate_event(repo_root, event)
        event_path = repo_root / HISTORY_DIR / request["prototype_id"] / "history" / f"{len(history) + 1:04d}.json"
        if event_path.exists():
            raise PacketError("history_collision", "Closure event would overwrite source history")
        updated = _updated_registry(registry, event, resolved)
        validate_schema(
            Draft202012Validator(load_json(repo_root / "schemas/prototype-registry.schema.json")),
            updated,
            code="registry_invalid",
            label="updated Prototype registry",
        )
        _write_source({
            event_path: canonical_json_bytes(event) + b"\n",
            repo_root / "prototypes.yaml": yaml.safe_dump(updated, sort_keys=False).encode("utf-8"),
        })
    return event_path, event


def readback_transition(
    repo_root: Path,
    event_path: Path,
    *,
    observed_at: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    validate_contract_bundle(repo_root)
    if run_git(repo_root, "branch", "--show-current") not in {"main", "master"}:
        raise PacketError("authority_branch_invalid", "Closure readback requires merged default-branch source")
    if run_git(repo_root, "status", "--porcelain"):
        raise PacketError("dirty_worktree", "merged Closure readback requires clean source")
    path = event_path.resolve()
    try:
        relative = path.relative_to(repo_root)
    except ValueError as error:
        raise PacketError("event_path_invalid", "event is outside Prototype Studio") from error
    if relative.parts[:2] != HISTORY_DIR.parts or not path.is_file():
        raise PacketError("event_path_invalid", "Closure event path is invalid")
    event = load_json(path)
    _validate_event(repo_root, event)
    events = _history(repo_root, event["prototype_id"])
    if not events or events[-1] != event:
        raise PacketError("readback_invalid", "Closure event is not the current source event")
    item = _registry_item(load_yaml(repo_root / "prototypes.yaml"), event["prototype_id"])
    if item["lifecycle"] != event["observed_lifecycle"] or _custody(item) != event["observed_source_custody"]:
        raise PacketError("readback_invalid", "registry lifecycle or source custody differs from event")
    head = run_git(repo_root, "rev-parse", "HEAD")
    if head == event["expected_source_revision"]:
        raise PacketError("readback_invalid", "Closure source revision did not advance")
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", event["expected_source_revision"], head],
        cwd=repo_root, check=False, capture_output=True,
    )
    if result.returncode:
        raise PacketError("readback_invalid", "expected revision is not an ancestor of merged source")
    now = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    observed_time = datetime.fromisoformat(now.replace("Z", "+00:00"))
    event_time = datetime.fromisoformat(event["recorded_at"].replace("Z", "+00:00"))
    if observed_time < event_time:
        raise PacketError("readback_invalid", "merged readback predates the source event")
    readback = {
        "schema_version": 2,
        "artifact_type": "prototype-closure-studio-readback",
        "readback_id": f"prototype-closure-readback:{event['event_id']}:{head}",
        "prototype_id": event["prototype_id"],
        "source_event_ref": event["event_id"],
        "source_event_digest": content_digest(event),
        "merged_source_revision": head,
        "observed_lifecycle": item["lifecycle"],
        "observed_source_custody": _custody(item),
        "observed_at": now,
    }
    validate_schema(
        _validator(repo_root, "prototype-closure-studio-readback.schema.json"),
        readback,
        code="readback_invalid",
        label="Prototype Closure merged readback",
    )
    return readback


def validate_closure_records(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    validate_contract_bundle(repo_root)
    registry = load_yaml(repo_root / "prototypes.yaml")
    paths = sorted((repo_root / HISTORY_DIR).glob("*/history/*.json"))
    for prototype_id in sorted({path.parent.parent.name for path in paths}):
        events = _history(repo_root, prototype_id)
        last = events[-1]
        item = _registry_item(registry, prototype_id)
        expected_ref = f"record://prototype-closure/{prototype_id}/history/{last['event_id']}"
        reopened_then_promoted = (
            last["event_type"] == "incubation-reopened"
            and item["lifecycle"] in {"candidate", "baseline-approved"}
        )
        if (
            item.get("closure_event_ref") != expected_ref
            or _custody(item) != last["observed_source_custody"]
            or (item["lifecycle"] != last["observed_lifecycle"] and not reopened_then_promoted)
        ):
            raise PacketError("history_state_mismatch", f"{prototype_id} registry differs from latest Closure event")
        for previous, current in zip(events, events[1:]):
            reopened_then_promoted = (
                previous["event_type"] == "incubation-reopened"
                and current["previous_lifecycle"] in {"candidate", "baseline-approved"}
            )
            if (
                (current["previous_lifecycle"] != previous["observed_lifecycle"] and not reopened_then_promoted)
                or current["previous_source_custody"] != previous["observed_source_custody"]
            ):
                raise PacketError("history_state_mismatch", f"{prototype_id} Closure event chain changes state")
    return paths
