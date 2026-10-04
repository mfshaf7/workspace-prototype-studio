from __future__ import annotations

import copy
import fcntl
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator, FormatChecker

from packages.prototype_delivery_packet.contract import (
    PacketError,
    content_digest,
    load_json,
    load_yaml,
    validate_schema,
)


CONTRACT_DIR = Path("contracts/proposal-target-application")
CAPTURE_DIR = Path("records/prototype-captures")
SAFE_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SCHEMA_BY_TYPE = {
    "proposal-prototype-application": "request.schema.json",
    "proposal-routed-prototype-capture": "record.schema.json",
    "proposal-prototype-application-result": "result.schema.json",
}
DIGEST_BY_TYPE = {
    "proposal-prototype-application": "request_digest",
    "proposal-prototype-application-result": "result_digest",
}


@dataclass(frozen=True)
class ApplicationResult:
    status: str
    prototype_id: str
    target_record_ref: str
    source_revision: str
    result_path: Path


def _run_git(repo_root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo_root, check=False, capture_output=True, text=True, env=env
    )
    if result.returncode:
        raise PacketError("git_error", result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def _current_branch(repo_root: Path) -> str:
    branch = _run_git(repo_root, "branch", "--show-current")
    if not branch:
        raise PacketError("detached_head", "target application requires a named review branch")
    return branch


def _current_head(repo_root: Path) -> str:
    return _run_git(repo_root, "rev-parse", "HEAD")


def _require_clean(repo_root: Path) -> None:
    if _run_git(repo_root, "status", "--porcelain"):
        raise PacketError("dirty_worktree", "target application requires a clean source worktree")


def _worktree_revision(repo_root: Path) -> str:
    common_dir = Path(_run_git(repo_root, "rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    descriptor, name = tempfile.mkstemp(prefix="proposal-target-index-", dir=common_dir)
    os.close(descriptor)
    index_path = Path(name)
    index_path.unlink(missing_ok=True)
    env = dict(os.environ)
    env["GIT_INDEX_FILE"] = str(index_path)
    try:
        _run_git(repo_root, "read-tree", "HEAD", env=env)
        _run_git(repo_root, "add", "--all", env=env)
        tree = _run_git(repo_root, "write-tree", env=env)
    finally:
        index_path.unlink(missing_ok=True)
    return f"git-tree:{tree}"


def _validator(repo_root: Path, name: str) -> Draft202012Validator:
    schema = load_json(repo_root / CONTRACT_DIR / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_contracts(repo_root: Path) -> None:
    for name in SCHEMA_BY_TYPE.values():
        _validator(repo_root, name)


def _without_digest(artifact: dict[str, Any], field: str) -> dict[str, Any]:
    return {key: value for key, value in artifact.items() if key != field}


def _with_digest(payload: dict[str, Any], field: str) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result[field] = content_digest(result)
    return result


def validate_artifact(repo_root: Path, artifact: dict[str, Any]) -> None:
    artifact_type = str(artifact.get("artifact_type"))
    schema_name = SCHEMA_BY_TYPE.get(artifact_type)
    if schema_name is None:
        raise PacketError("artifact_type_invalid", f"unsupported target artifact {artifact_type!r}")
    validate_schema(
        _validator(repo_root, schema_name), artifact,
        code="artifact_invalid", label=artifact_type,
    )
    digest_field = DIGEST_BY_TYPE.get(artifact_type)
    if digest_field and artifact[digest_field] != content_digest(_without_digest(artifact, digest_field)):
        raise PacketError("artifact_digest_mismatch", f"{artifact_type} digest does not match its content")


def _slug(prototype_id: str) -> str:
    value = prototype_id.removeprefix("prototype:")
    if not SAFE_SLUG.fullmatch(value):
        raise PacketError("prototype_identity_invalid", "Prototype identity is not a safe kebab-case id")
    return value


def _request_ref(request: dict[str, Any]) -> dict[str, str]:
    return {"id": str(request["application_id"]), "digest": str(request["request_digest"])}


def _validate_request_semantics(request: dict[str, Any]) -> None:
    proposal_number = request["source"]["proposal_id"].removeprefix("idea-")
    record_number = request["source"]["record_ref"].rsplit("/", 1)[-1]
    if proposal_number != record_number:
        raise PacketError("proposal_identity_mismatch", "Proposal id and canonical record ref identify different records")
    custody = request["source"]["route"]["source_custody"]
    expected_mode = {
        "existing-repo": "existing",
        "new-repo-required": "new",
        "platform-internal": "not-required",
        "non-source-work": "not-required",
    }[custody["classification"]]
    if custody["repository_mode"] != expected_mode:
        raise PacketError("source_custody_invalid", "source custody classification and repository mode disagree")


def _entry_packet(request: dict[str, Any], slug: str) -> dict[str, Any]:
    source = request["source"]
    custody = source["route"]["source_custody"]
    packet = {
        "schema_version": 1,
        "artifact_type": "prototype-entry-packet",
        "entry_id": f"prototype-entry:proposal-routed:{slug}",
        "captured_at": request["requested_at"],
        "ingress_class": "proposal-routed",
        "source": {
            "authority": "workspace-proposals",
            "ref": source["record_ref"],
            "digest": source["handoff_packet_digest"],
            "revision": source["record_version"],
        },
        "suggestions": {
            "name": source["suggested_name"],
            "objective": source["suggested_objective"],
            "support_profile": None,
        },
        "constraints": [
            {"code": "proposal-route", "detail": source["route"]["rationale"]},
            {
                "code": "source-custody",
                "detail": (
                    f"{custody['classification']} / {custody['repository_mode']} / "
                    f"{custody['repository_gate_state']}: {custody['rationale']}"
                ),
            },
        ],
        "requested_by": request["operator_ref"],
    }
    packet["packet_digest"] = content_digest(packet)
    return packet


def _build_record(repo_root: Path, request: dict[str, Any]) -> dict[str, Any]:
    slug = _slug(request["target"]["prototype_id"])
    entry = _entry_packet(request, slug)
    entry_validator = _validator(repo_root, "../prototype-landing/prototype-landing-entry-packet.schema.json")
    validate_schema(entry_validator, entry, code="entry_packet_invalid", label="generated Prototype Entry Packet")
    return {
        "schema_version": 1,
        "artifact_type": "proposal-routed-prototype-capture",
        "record_ref": f"record://prototype-captures/{slug}",
        "prototype_id": request["target"]["prototype_id"],
        "lifecycle": "exploring",
        "landing_state": "captured",
        "application_ref": _request_ref(request),
        "proposal": {
            "proposal_id": request["source"]["proposal_id"],
            "record_ref": request["source"]["record_ref"],
            "record_version": request["source"]["record_version"],
            "handoff_packet_ref": request["source"]["handoff_packet_ref"],
            "handoff_packet_digest": request["source"]["handoff_packet_digest"],
            "route": copy.deepcopy(request["source"]["route"]),
        },
        "entry_packet": entry,
        "captured_at": request["requested_at"],
        "next_action": "prototype-landing",
    }


def _receipt_ref(request: dict[str, Any]) -> str:
    slug = _slug(request["target"]["prototype_id"])
    digest = content_digest({
        "application_id": request["application_id"],
        "packet_ref": request["source"]["handoff_packet_ref"],
        "proposal_id": request["source"]["proposal_id"],
        "prototype_id": request["target"]["prototype_id"],
    }).removeprefix("sha256:")
    return f"proposal-prototype-target-receipt:{slug}:{digest}"


def _build_result(
    repo_root: Path,
    request: dict[str, Any],
    record: dict[str, Any],
    *,
    branch: str,
    revision: str,
    replayed: bool,
) -> dict[str, Any]:
    registry_digest = content_digest(load_yaml(repo_root / "prototypes.yaml"))
    payload = {
        "schema_version": 1,
        "artifact_type": "proposal-prototype-application-result",
        "application_ref": _request_ref(request),
        "replayed": replayed,
        "readback": {
            "target_record_ref": record["record_ref"],
            "authority_state": "review-branch",
            "source_branch": branch,
            "source_revision": revision,
            "registry_digest": registry_digest,
            "record_digest": content_digest(record),
            "record": copy.deepcopy(record),
            "observed_at": record["captured_at"],
        },
        "receipt": {
            "receipt_ref": _receipt_ref(request),
            "owner": "workspace-prototype-studio",
            "source_record_ref": request["source"]["record_ref"],
            "source_record_version": request["source"]["record_version"],
            "source_packet_ref": request["source"]["handoff_packet_ref"],
            "target_record_ref": record["record_ref"],
            "prototype_id": record["prototype_id"],
            "outcome": "replayed" if replayed else "prepared",
            "recorded_at": record["captured_at"],
            "next_action": {"code": "prototype-landing", "owner_ref": "operator-orchestration-service"},
            "correlation_id": request["correlation_id"],
            "idempotency_key": request["idempotency_key"],
        },
    }
    result = _with_digest(payload, "result_digest")
    validate_artifact(repo_root, result)
    validate_artifact(repo_root, result["readback"]["record"])
    return result


class _Transaction:
    def __init__(self) -> None:
        self.original: dict[Path, bytes | None] = {}

    def write(self, path: Path, content: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.original.setdefault(path, path.read_bytes() if path.exists() else None)
        descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temporary = Path(name)
        try:
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def rollback(self) -> None:
        for path, content in reversed(tuple(self.original.items())):
            if content is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(content)
        for parent in sorted({path.parent for path in self.original}, key=lambda item: len(item.parts), reverse=True):
            try:
                parent.rmdir()
            except OSError:
                pass


@contextmanager
def _authority_lock(repo_root: Path) -> Iterator[None]:
    common_dir = Path(_run_git(repo_root, "rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    lock_path = common_dir / "proposal-prototype-target.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _ensure_output_outside_repo(repo_root: Path, output_path: Path) -> None:
    try:
        output_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return
    raise PacketError("output_boundary_invalid", "application result must be written outside Prototype Studio source")


def _history_requests(repo_root: Path) -> Iterator[tuple[Path, dict[str, Any]]]:
    for path in sorted((repo_root / CAPTURE_DIR).glob("*/history/*.json")):
        request = load_json(path)
        validate_artifact(repo_root, request)
        _validate_request_semantics(request)
        yield path, request


def _existing_request(repo_root: Path, request: dict[str, Any]) -> dict[str, Any] | None:
    for _, existing in _history_requests(repo_root):
        same_key = existing["idempotency_key"] == request["idempotency_key"]
        same_id = existing["application_id"] == request["application_id"]
        if same_key or same_id:
            if existing != request:
                raise PacketError("idempotency_conflict", "application id or idempotency key is bound to different content")
            return existing
    return None


def current_state(repo_root: Path, prototype_id: str) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    slug = _slug(prototype_id)
    record_path = repo_root / CAPTURE_DIR / slug / "record.json"
    record = load_json(record_path) if record_path.exists() else None
    registry = load_yaml(repo_root / "prototypes.yaml")
    registry_match = any(item.get("id") == slug for item in registry.get("prototypes", []))
    return {
        "prototype_id": prototype_id,
        "expected_state": {
            "source_revision": _current_head(repo_root),
            "registry_digest": content_digest(registry),
            "record_present": bool(record is not None or registry_match),
            "record_digest": content_digest(record) if record is not None else None,
        },
    }


def apply_application(
    *, repo_root: Path, request: dict[str, Any], output_path: Path
) -> ApplicationResult:
    repo_root = repo_root.resolve()
    output_path = output_path.resolve()
    _ensure_output_outside_repo(repo_root, output_path)
    validate_contracts(repo_root)
    validate_artifact(repo_root, request)
    _validate_request_semantics(request)
    branch = _current_branch(repo_root)
    if branch != request["source_branch"] or branch in {"main", "master"}:
        raise PacketError("source_branch_invalid", "request must bind the current non-default review branch")
    slug = _slug(request["target"]["prototype_id"])
    record_path = repo_root / CAPTURE_DIR / slug / "record.json"
    history_name = request["application_id"].replace(":", "-") + ".json"
    history_path = record_path.parent / "history" / history_name

    with _authority_lock(repo_root):
        if _existing_request(repo_root, request) is not None:
            if not record_path.is_file():
                raise PacketError("source_record_missing", "application history exists without its captured Prototype record")
            record = load_json(record_path)
            validate_artifact(repo_root, record)
            if record["application_ref"] != _request_ref(request):
                raise PacketError("source_record_conflict", "captured Prototype record binds another application")
            revision = _worktree_revision(repo_root)
            result = _build_result(repo_root, request, record, branch=branch, revision=revision, replayed=True)
            transaction = _Transaction()
            try:
                transaction.write(output_path, _json_bytes(result))
            except BaseException:
                transaction.rollback()
                raise
            return ApplicationResult("replayed", record["prototype_id"], record["record_ref"], revision, output_path)

        _require_clean(repo_root)
        expected = request["target"]["expected_state"]
        observed = current_state(repo_root, request["target"]["prototype_id"])["expected_state"]
        if expected != observed:
            raise PacketError("source_state_stale", "Prototype target state differs from the application precondition")
        if expected["record_present"] or expected["record_digest"] is not None:
            raise PacketError("source_state_invalid", "target application requires an absent Prototype identity")
        record = _build_record(repo_root, request)
        validate_artifact(repo_root, record)
        transaction = _Transaction()
        try:
            transaction.write(record_path, _json_bytes(record))
            transaction.write(history_path, _json_bytes(request))
            revision = _worktree_revision(repo_root)
            result = _build_result(repo_root, request, record, branch=branch, revision=revision, replayed=False)
            transaction.write(output_path, _json_bytes(result))
        except BaseException:
            transaction.rollback()
            raise
    return ApplicationResult("prepared", record["prototype_id"], record["record_ref"], revision, output_path)


def validate_capture_records(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    validate_contracts(repo_root)
    seen_keys: dict[str, str] = {}
    seen_ids: dict[str, str] = {}
    validated: list[Path] = []
    for record_path in sorted((repo_root / CAPTURE_DIR).glob("*/record.json")):
        record = load_json(record_path)
        validate_artifact(repo_root, record)
        slug = _slug(record["prototype_id"])
        if record_path != repo_root / CAPTURE_DIR / slug / "record.json":
            raise PacketError("source_record_path_invalid", f"capture record path differs for {slug}")
        expected_ref = f"record://prototype-captures/{slug}"
        if record["record_ref"] != expected_ref:
            raise PacketError("source_record_ref_invalid", f"capture record ref must be {expected_ref}")
        entry = record["entry_packet"]
        entry_validator = _validator(repo_root, "../prototype-landing/prototype-landing-entry-packet.schema.json")
        validate_schema(entry_validator, entry, code="entry_packet_invalid", label="captured Prototype Entry Packet")
        if entry["packet_digest"] != content_digest(_without_digest(entry, "packet_digest")):
            raise PacketError("entry_packet_digest_mismatch", f"capture record {slug} has a forged entry digest")
        history = sorted((record_path.parent / "history").glob("*.json"))
        if not history:
            raise PacketError("source_history_missing", f"capture record {slug} has no application history")
        matched = False
        for path in history:
            request = load_json(path)
            validate_artifact(repo_root, request)
            _validate_request_semantics(request)
            if request["target"]["prototype_id"] != record["prototype_id"]:
                raise PacketError("history_identity_mismatch", f"{path} belongs to another Prototype")
            if record["application_ref"] == _request_ref(request):
                matched = True
                if record != _build_record(repo_root, request):
                    raise PacketError("source_record_mismatch", f"capture record {slug} differs from its application")
            digest = request["request_digest"]
            prior_key = seen_keys.setdefault(request["idempotency_key"], digest)
            prior_id = seen_ids.setdefault(request["application_id"], digest)
            if prior_key != digest or prior_id != digest:
                raise PacketError("idempotency_conflict", "capture history reuses an application identity")
        if not matched:
            raise PacketError("source_record_unbound", f"capture record {slug} has no matching application")
        validated.append(record_path)
    return validated
