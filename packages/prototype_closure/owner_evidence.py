"""Committed Studio proof for Closure retirement and retained-source reopen."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from packages.prototype_closure.closure import (
    HISTORY_DIR,
    SAFE_ID,
    _custody,
    _lock,
    _registry_item,
    _write_source,
    validate_contract_bundle,
)
from packages.prototype_delivery_packet.contract import (
    PacketError,
    canonical_json_bytes,
    content_digest,
    load_json,
    load_yaml,
    validate_schema,
)
from packages.prototype_delivery_packet.git_provenance import load_yaml_at_revision, run_git


PLAN_REF = re.compile(r"^record://prototype-closure/([a-z0-9]+(?:-[a-z0-9]+)*)/retention-plans/([0-9a-f]{64})$")
SOURCE_REF = re.compile(r"^record://prototype-closure/([a-z0-9]+(?:-[a-z0-9]+)*)/retained-source/([0-9a-f]{40})$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def _plan_validator(repo_root: Path) -> Draft202012Validator:
    schema = load_json(repo_root / "schemas/prototype-closure-retention-plan.schema.json")
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _trusted_revision(repo_root: Path, expected_revision: str) -> str:
    if not COMMIT.fullmatch(expected_revision):
        raise PacketError("source_revision_invalid", "expected source revision is not a commit")
    revision = run_git(repo_root, "rev-parse", "--verify", "refs/remotes/origin/main^{commit}")
    if revision != expected_revision:
        raise PacketError("source_revision_stale", "trusted Studio main differs from the requested source revision")
    return revision


def _committed_json(repo_root: Path, revision: str, relative_path: Path) -> dict[str, Any]:
    raw = run_git(repo_root, "show", f"{revision}:{relative_path.as_posix()}")
    try:
        value = json.loads(raw)
    except ValueError as error:
        raise PacketError("source_record_invalid", "committed Studio proof is not JSON") from error
    if not isinstance(value, dict):
        raise PacketError("source_record_invalid", "committed Studio proof is not an object")
    return value


def _committed_item(repo_root: Path, revision: str, prototype_id: str) -> dict[str, Any]:
    registry = load_yaml_at_revision(repo_root, revision, Path("prototypes.yaml"))
    return _registry_item(registry, prototype_id)


def _safe_source_path(raw_path: str) -> str:
    if not isinstance(raw_path, str):
        raise PacketError("retained_source_invalid", "retained source path is invalid")
    path = PurePosixPath(raw_path)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise PacketError("retained_source_invalid", "retained source path escapes Studio")
    return path.as_posix()


def _object_oid(repo_root: Path, revision: str, path: str) -> str:
    oid = run_git(repo_root, "rev-parse", "--verify", f"{revision}:{path}")
    if not COMMIT.fullmatch(oid):
        raise PacketError("retained_source_invalid", "Studio source object id is invalid")
    return oid


def _retained_files(repo_root: Path, revision: str, item: dict[str, Any]) -> list[dict[str, str]]:
    paths = item.get("paths")
    if not isinstance(paths, dict):
        raise PacketError("retained_source_invalid", "Studio registry source paths are invalid")
    retained = []
    for path in sorted({_safe_source_path(raw_path) for raw_path in paths.values()}):
        oid = _object_oid(repo_root, revision, path)
        if run_git(repo_root, "cat-file", "-t", oid) != "blob":
            raise PacketError("retained_source_invalid", "declared Studio source path is not a file")
        retained.append({"path": path, "oid": oid})
    return retained


def _verify_retained_objects(repo_root: Path, revision: str, item: dict[str, Any], plan: dict[str, Any]) -> None:
    if _retained_files(repo_root, revision, item) != plan["retained_files"]:
        raise PacketError("retained_source_changed", "declared Studio files differ from the retention plan")
    source_tree = f"prototypes/{plan['prototype_id']}"
    tree_present = bool(run_git(repo_root, "ls-tree", "-r", "--name-only", revision, "--", source_tree))
    if tree_present != (plan["source_tree_path"] is not None):
        raise PacketError("retained_source_changed", "prototype source tree presence changed")
    if tree_present and _object_oid(repo_root, revision, source_tree) != plan["source_tree_oid"]:
        raise PacketError("retained_source_changed", "prototype source tree differs from the retention plan")


def validate_retention_plan_records(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    validator = _plan_validator(repo_root)
    paths = sorted((repo_root / HISTORY_DIR).glob("*/retention-plans/*.json"))
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(repo_root):
            raise PacketError("retention_path_invalid", "retention plan cannot be a symlink")
        relative = path.relative_to(repo_root / HISTORY_DIR)
        if len(relative.parts) != 3 or not SAFE_ID.fullmatch(relative.parts[0]):
            raise PacketError("retention_path_invalid", "retention plan path is invalid")
        plan = load_json(path)
        validate_schema(validator, plan, code="retention_plan_invalid", label="retention plan")
        if (
            plan["prototype_id"] != relative.parts[0]
            or plan["source_tree_path"] not in {None, f"prototypes/{relative.parts[0]}"}
            or (plan["source_tree_path"] is None) != (plan["source_tree_oid"] is None)
            or path.stem != content_digest(plan).removeprefix("sha256:")
            or not plan["operator_id"].strip()
            or not plan["retirement_reason"].strip()
        ):
            raise PacketError("retention_plan_mismatch", "retention plan content differs from its path")
    return paths


def prepare_retention_plan(
    repo_root: Path,
    prototype_id: str,
    operator_id: str,
    retirement_reason: str,
    *,
    created_at: str | None = None,
) -> tuple[Path, str, dict[str, Any]]:
    repo_root = repo_root.resolve()
    validate_contract_bundle(repo_root)
    if not SAFE_ID.fullmatch(prototype_id):
        raise PacketError("prototype_id_invalid", "prototype id is not source-safe")
    if not operator_id.strip() or not retirement_reason.strip():
        raise PacketError("retention_decision_missing", "operator and retirement reason are required")
    if run_git(repo_root, "branch", "--show-current") in {"", "main", "master"}:
        raise PacketError("source_branch_invalid", "retention plan requires a review branch")
    if run_git(repo_root, "status", "--porcelain"):
        raise PacketError("dirty_worktree", "retention plan preparation requires clean source")
    with _lock(repo_root):
        revision = run_git(repo_root, "rev-parse", "HEAD")
        item = _registry_item(load_yaml(repo_root / "prototypes.yaml"), prototype_id)
        if item["lifecycle"] not in {"exploring", "candidate", "baseline-approved", "graduating"}:
            raise PacketError("lifecycle_invalid", "only active incubation can prepare retirement")
        source_tree = f"prototypes/{prototype_id}"
        has_source_tree = bool(run_git(repo_root, "ls-tree", "-r", "--name-only", revision, "--", source_tree))
        retained_files = _retained_files(repo_root, revision, item)
        if not retained_files and not has_source_tree:
            raise PacketError("retained_source_unavailable", "prototype has no committed source to retain")
        plan = {
            "schema_version": 1,
            "artifact_type": "prototype-closure-retention-plan",
            "prototype_id": prototype_id,
            "basis_revision": revision,
            "basis_lifecycle": item["lifecycle"],
            "basis_source_custody": _custody(item),
            "source_tree_path": source_tree if has_source_tree else None,
            "source_tree_oid": _object_oid(repo_root, revision, source_tree) if has_source_tree else None,
            "retained_files": retained_files,
            "retention_mode": "retain-studio-source-and-history",
            "operator_id": operator_id.strip(),
            "retirement_reason": retirement_reason.strip(),
            "created_at": created_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
        validate_schema(_plan_validator(repo_root), plan, code="retention_plan_invalid", label="retention plan")
        digest = content_digest(plan)
        path = repo_root / HISTORY_DIR / prototype_id / "retention-plans" / f"{digest.removeprefix('sha256:')}.json"
        if path.exists():
            if load_json(path) != plan:
                raise PacketError("retention_plan_conflict", "retention plan digest path has different content")
        else:
            _write_source({path: canonical_json_bytes(plan) + b"\n"})
        ref = f"record://prototype-closure/{prototype_id}/retention-plans/{digest.removeprefix('sha256:')}"
        return path, ref, plan


def read_retention_plan(
    repo_root: Path, ref: str, expected_source_revision: str,
    expected_operator_id: str, expected_retirement_reason: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    match = PLAN_REF.fullmatch(ref)
    if not match:
        raise PacketError("retention_ref_invalid", "retention plan reference is invalid")
    prototype_id, digest_hex = match.groups()
    revision = _trusted_revision(repo_root, expected_source_revision)
    relative_path = HISTORY_DIR / prototype_id / "retention-plans" / f"{digest_hex}.json"
    plan = _committed_json(repo_root, revision, relative_path)
    validate_schema(_plan_validator(repo_root), plan, code="retention_plan_invalid", label="retention plan")
    if (
        plan["prototype_id"] != prototype_id
        or plan["source_tree_path"] not in {None, f"prototypes/{prototype_id}"}
        or (plan["source_tree_path"] is None) != (plan["source_tree_oid"] is None)
        or content_digest(plan) != f"sha256:{digest_hex}"
    ):
        raise PacketError("retention_plan_mismatch", "committed retention plan differs from its reference")
    if (
        not expected_operator_id.strip()
        or not expected_retirement_reason.strip()
        or plan["operator_id"] != expected_operator_id
        or plan["retirement_reason"] != expected_retirement_reason
    ):
        raise PacketError("retention_decision_mismatch", "committed retention decision differs from request")
    basis = _committed_item(repo_root, plan["basis_revision"], prototype_id)
    current = _committed_item(repo_root, revision, prototype_id)
    run_git(repo_root, "merge-base", "--is-ancestor", plan["basis_revision"], revision)
    if (
        basis["lifecycle"] != plan["basis_lifecycle"]
        or _custody(basis) != plan["basis_source_custody"]
        or current["lifecycle"] != plan["basis_lifecycle"]
        or _custody(current) != plan["basis_source_custody"]
    ):
        raise PacketError("retention_plan_stale", "retention plan no longer matches committed Studio state")
    _verify_retained_objects(repo_root, revision, current, plan)
    return {
        "ref": ref,
        "owner_ref": "workspace-prototype-studio",
        "digest": f"sha256:{digest_hex}",
        "state": "accepted",
        "subject_ref": None,
        "source_revision": revision,
        "source_packet_ref": None,
        "prototype_id": prototype_id,
    }


def read_retained_source(
    repo_root: Path, prototype_id: str, expected_source_revision: str, ref: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    if not SAFE_ID.fullmatch(prototype_id):
        raise PacketError("prototype_id_invalid", "prototype id is not source-safe")
    if ref is None:
        ref = f"record://prototype-closure/{prototype_id}/retained-source/{expected_source_revision}"
    match = SOURCE_REF.fullmatch(ref)
    if not match:
        raise PacketError("retained_ref_invalid", "retained source reference is invalid")
    named_prototype_id, named_revision = match.groups()
    if named_prototype_id != prototype_id:
        raise PacketError("retained_ref_invalid", "retained source reference binds another prototype")
    revision = _trusted_revision(repo_root, expected_source_revision)
    if named_revision != revision:
        raise PacketError("retained_source_stale", "retained source reference is not current Studio main")
    item = _committed_item(repo_root, revision, prototype_id)
    if item["lifecycle"] != "retired" or _custody(item) != "incubation-repo":
        raise PacketError("retained_source_unavailable", "Studio source is not retained for reopen")
    retirement_ref = item.get("retirement_ref")
    if not isinstance(retirement_ref, str) or not retirement_ref.startswith(
        f"record://prototype-closure/{prototype_id}/history/prototype-closure:{prototype_id}:"
    ):
        raise PacketError("retirement_source_invalid", "active retirement event is missing")
    sequence = retirement_ref.rsplit(":", 1)[-1]
    if not re.fullmatch(r"[0-9]{4}", sequence):
        raise PacketError("retirement_source_invalid", "retirement event sequence is invalid")
    event = _committed_json(repo_root, revision, HISTORY_DIR / prototype_id / "history" / f"{sequence}.json")
    if (
        event.get("event_type") != "incubation-retired"
        or event.get("prototype_id") != prototype_id
        or event.get("event_id") != f"prototype-closure:{prototype_id}:{sequence}"
        or event.get("observed_lifecycle") != "retired"
        or item.get("closure_event_ref") != retirement_ref
    ):
        raise PacketError("retirement_source_invalid", "retirement history does not bind this prototype")
    plan_ref = event.get("retention_plan_ref")
    plan_match = PLAN_REF.fullmatch(plan_ref) if isinstance(plan_ref, str) else None
    if plan_match is None or plan_match.group(1) != prototype_id:
        raise PacketError("retention_plan_invalid", "retirement history lacks the Studio plan")
    plan = _committed_json(
        repo_root, revision,
        HISTORY_DIR / prototype_id / "retention-plans" / f"{plan_match.group(2)}.json",
    )
    validate_schema(_plan_validator(repo_root), plan, code="retention_plan_invalid", label="retention plan")
    if (
        plan["prototype_id"] != prototype_id
        or plan["source_tree_path"] not in {None, f"prototypes/{prototype_id}"}
        or (plan["source_tree_path"] is None) != (plan["source_tree_oid"] is None)
        or content_digest(plan) != f"sha256:{plan_match.group(2)}"
    ):
        raise PacketError("retention_plan_mismatch", "committed retirement plan digest differs")
    _verify_retained_objects(repo_root, revision, item, plan)
    return {
        "ref": ref,
        "owner_ref": "workspace-prototype-studio",
        "digest": content_digest({"record": item, "retirement_event": event}),
        "state": "accepted",
        "subject_ref": retirement_ref,
        "source_revision": revision,
        "source_packet_ref": None,
        "prototype_id": prototype_id,
    }
