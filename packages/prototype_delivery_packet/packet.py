from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from packages.prototype_delivery_packet.contract import (
    PacketError,
    content_digest,
    load_json,
    load_yaml,
    schema_validator,
    validate_schema,
)
from packages.prototype_delivery_packet.git_provenance import (
    load_yaml_at_revision,
    validate_source_revision,
)


PACKET_RECORD_DIRECTORY = Path("records/delivery-packets")
PACKET_REF_PREFIX = "record://delivery-packets/"
PROTOTYPE_REF_PREFIX = "record://prototypes/"
BASELINE_REF_PREFIX = "record://design-baselines/"


@dataclass(frozen=True)
class EmitResult:
    status: str
    packet_path: Path
    packet_ref: str
    packet_digest: str


def _find_prototype(registry: dict[str, Any], prototype_id: str) -> dict[str, Any]:
    for prototype in registry.get("prototypes") or []:
        if isinstance(prototype, dict) and prototype.get("id") == prototype_id:
            return prototype
    raise PacketError("prototype_not_found", f"unknown prototype {prototype_id!r}")


def _baseline_path(baseline_ref: str) -> Path:
    if not baseline_ref.startswith(BASELINE_REF_PREFIX):
        raise PacketError(
            "baseline_binding_invalid",
            "design baseline ref must use record://design-baselines/<baseline-id>",
        )
    baseline_id = baseline_ref.removeprefix(BASELINE_REF_PREFIX)
    if not baseline_id or "/" in baseline_id or ".." in baseline_id:
        raise PacketError("baseline_binding_invalid", "design baseline ref is unsafe")
    return Path("records/design-baselines") / f"{baseline_id}.yaml"


def _baseline_version(baseline: dict[str, Any]) -> str:
    baseline_id = str(baseline["baseline_id"])
    return f"{baseline_id}@{content_digest(baseline)}"


def _packet_identity(prototype_id: str, digest: str) -> tuple[str, str]:
    packet_id = f"{prototype_id}-{digest.removeprefix('sha256:')}"
    return packet_id, f"{PACKET_REF_PREFIX}{packet_id}"


def _build_packet(repo_root: Path, request: dict[str, Any]) -> dict[str, Any]:
    source_revision = request["source_revision"]
    source_tree = validate_source_revision(
        repo_root,
        source_revision,
        require_ref_match=True,
    )
    head_commit = str(source_revision["head_commit"])
    registry = load_yaml_at_revision(repo_root, head_commit, Path("prototypes.yaml"))
    validate_schema(
        schema_validator(repo_root, "prototype-registry.schema.json"),
        registry,
        code="source_record_invalid",
        label="bound Prototype registry",
    )
    prototype = _find_prototype(registry, str(request["prototype_id"]))

    studio_repository = (registry.get("studio") or {}).get("owner_repo")
    if studio_repository != source_revision["repository"]:
        raise PacketError(
            "source_repository_mismatch",
            "request source repository does not match the Prototype registry owner",
        )
    if prototype.get("lifecycle") != "baseline-approved":
        raise PacketError(
            "lifecycle_not_eligible",
            "the bound source revision must show lifecycle baseline-approved",
        )

    baseline_ref = str(prototype.get("design_baseline_ref") or "")
    baseline_path = _baseline_path(baseline_ref)
    baseline = load_yaml_at_revision(repo_root, head_commit, baseline_path)
    validate_schema(
        schema_validator(repo_root, "design-baseline.schema.json"),
        baseline,
        code="baseline_binding_invalid",
        label="bound design baseline",
    )
    if baseline.get("prototype_id") != request["prototype_id"]:
        raise PacketError("baseline_binding_invalid", "baseline belongs to another prototype")
    if baseline.get("decision") != "approved":
        raise PacketError("baseline_not_approved", "design baseline decision is not approved")

    evidence_refs = sorted(
        set(baseline.get("evidence_refs") or [])
        | set(baseline.get("security_review_refs") or [])
        | set(request["evidence_refs"])
    )
    content = {
        "intent": "governed-delivery",
        "target": "workspace-delivery-art",
        "source": {
            "kind": "prototype",
            "prototype_id": request["prototype_id"],
            "record_ref": f"{PROTOTYPE_REF_PREFIX}{request['prototype_id']}",
            "record_version": head_commit,
            "lifecycle": "baseline-approved",
            "owner": prototype["owner"],
            "repository": source_revision["repository"],
            "revision": {
                "ref": source_revision["ref"],
                "base_commit": source_revision["base_commit"],
                "head_commit": head_commit,
                "tree": source_tree,
            },
        },
        "baseline": {
            "record_ref": baseline_ref,
            "baseline_id": baseline["baseline_id"],
            "schema_version": baseline["schema_version"],
            "version": _baseline_version(baseline),
            "record_digest": content_digest(baseline),
        },
        "work": {
            "title": request["title"],
            "objective": request["objective"],
            "included_scope": request["included_scope"],
            "excluded_scope": request["excluded_scope"],
            "remaining_work": request["remaining_work"],
        },
        "posture": {
            "visibility_tier": prototype["visibility_tier"],
            "data_mode": prototype["data_mode"],
            "mutation_boundary": prototype["mutation_boundary"],
        },
        "custody": request["custody"],
        "authorization": request["authorization"],
        "evidence_refs": evidence_refs,
        "rationale": request["rationale"],
    }
    digest = content_digest(content)
    packet_id, packet_ref = _packet_identity(str(request["prototype_id"]), digest)
    return {
        "schema_version": 1,
        "packet_id": packet_id,
        "packet_ref": packet_ref,
        "packet_digest": digest,
        "content": content,
    }


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _packet_bytes(packet: dict[str, Any]) -> bytes:
    return json.dumps(packet, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _existing_packets(repo_root: Path) -> list[tuple[Path, dict[str, Any]]]:
    record_dir = repo_root / PACKET_RECORD_DIRECTORY
    if not record_dir.exists():
        return []
    return [(path, load_json(path)) for path in sorted(record_dir.glob("*.json"))]


def _reject_conflicting_source_version(
    repo_root: Path,
    packet: dict[str, Any],
) -> None:
    source = packet["content"]["source"]
    for path, existing in _existing_packets(repo_root):
        existing_source = (existing.get("content") or {}).get("source") or {}
        same_source_version = (
            existing_source.get("record_ref") == source["record_ref"]
            and existing_source.get("record_version") == source["record_version"]
        )
        if same_source_version and existing.get("packet_digest") != packet["packet_digest"]:
            raise PacketError(
                "packet_conflict",
                f"{path.relative_to(repo_root)} already binds this source version "
                "to another packet",
            )


def _packet_relative_path(packet: dict[str, Any]) -> Path:
    return PACKET_RECORD_DIRECTORY / f"{packet['packet_id']}.json"


def _reject_self_referential_provenance(repo_root: Path, packet: dict[str, Any]) -> None:
    relative_path = _packet_relative_path(packet)
    head_commit = packet["content"]["source"]["revision"]["head_commit"]
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{head_commit}:{relative_path.as_posix()}"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        raise PacketError(
            "source_provenance_self_referential",
            "packet provenance cannot bind a source commit that already contains that packet",
        )


def _prepare_registry_projection(
    repo_root: Path,
    packet: dict[str, Any],
) -> tuple[Path, dict[str, Any], bool]:
    registry_path = repo_root / "prototypes.yaml"
    registry = load_yaml(registry_path)
    source = packet["content"]["source"]
    prototype = _find_prototype(registry, source["prototype_id"])

    expected_values = {
        "owner": source["owner"],
        "design_baseline_ref": packet["content"]["baseline"]["record_ref"],
        **packet["content"]["posture"],
    }
    for key, expected in expected_values.items():
        if prototype.get(key) != expected:
            raise PacketError(
                "source_projection_stale",
                f"current prototype {key} no longer matches the packet source version",
            )

    lifecycle = prototype.get("lifecycle")
    active_ref = prototype.get("delivery_packet_ref")
    if lifecycle == "baseline-approved" and active_ref == packet["packet_ref"]:
        return registry_path, registry, False
    if lifecycle != "baseline-approved":
        raise PacketError(
            "source_projection_conflict",
            f"current prototype lifecycle {lifecycle!r} cannot accept this packet",
        )
    if active_ref not in (None, packet["packet_ref"]):
        raise PacketError(
            "source_projection_conflict",
            "current prototype already points to another Delivery packet",
        )

    prototype["delivery_packet_ref"] = packet["packet_ref"]
    linked_records = prototype.setdefault("linked_records", [])
    if not any(
        isinstance(record, dict) and record.get("ref") == packet["packet_ref"]
        for record in linked_records
    ):
        linked_records.append(
            {
                "role": "delivery-packet",
                "ref": packet["packet_ref"],
                "system": "prototype-studio",
                "level": "record",
                "label": "Prototype Delivery packet",
            }
        )
    return registry_path, registry, True


def _update_registry_projection(
    registry_path: Path,
    registry: dict[str, Any],
    *,
    changed: bool,
) -> None:
    if not changed:
        return
    rendered = yaml.safe_dump(registry, sort_keys=False, allow_unicode=False)
    _atomic_write(registry_path, rendered)


def emit_packet(repo_root: Path, request_path: Path) -> EmitResult:
    repo_root = repo_root.resolve()
    request = load_yaml(request_path.resolve())
    validate_schema(
        schema_validator(repo_root, "prototype-delivery-request.schema.json"),
        request,
        code="malformed_request",
        label="Prototype Delivery request",
    )
    packet = _build_packet(repo_root, request)
    validate_schema(
        schema_validator(repo_root, "prototype-delivery-packet.schema.json"),
        packet,
        code="malformed_packet",
        label="generated Prototype Delivery packet",
    )
    _reject_conflicting_source_version(repo_root, packet)
    _reject_self_referential_provenance(repo_root, packet)
    registry_path, registry, registry_changed = _prepare_registry_projection(
        repo_root,
        packet,
    )

    packet_path = repo_root / _packet_relative_path(packet)
    expected_bytes = _packet_bytes(packet)
    if packet_path.exists():
        if packet_path.read_bytes() != expected_bytes:
            raise PacketError(
                "packet_conflict",
                f"{packet_path.relative_to(repo_root)} exists with conflicting content",
            )
        status = "replayed"
    else:
        _atomic_write(packet_path, expected_bytes.decode("utf-8"))
        status = "emitted"

    _update_registry_projection(
        registry_path,
        registry,
        changed=registry_changed,
    )
    return EmitResult(
        status=status,
        packet_path=packet_path,
        packet_ref=packet["packet_ref"],
        packet_digest=packet["packet_digest"],
    )


def _validate_packet_identity(packet: dict[str, Any]) -> None:
    digest = content_digest(packet["content"])
    if packet["packet_digest"] != digest:
        raise PacketError("packet_digest_mismatch", "packet content digest does not match")
    prototype_id = packet["content"]["source"]["prototype_id"]
    expected_id, expected_ref = _packet_identity(prototype_id, digest)
    if packet["packet_id"] != expected_id or packet["packet_ref"] != expected_ref:
        raise PacketError("packet_identity_mismatch", "packet identity is not deterministic")


def _validate_packet_source(repo_root: Path, packet: dict[str, Any]) -> None:
    source = packet["content"]["source"]
    revision = source["revision"]
    tree = validate_source_revision(repo_root, revision, require_ref_match=False)
    if source["record_version"] != revision["head_commit"]:
        raise PacketError(
            "source_version_mismatch",
            "source record version must equal the bound head commit",
        )
    if revision["tree"] != tree:
        raise PacketError("source_tree_mismatch", "source tree does not match head commit")
    _reject_self_referential_provenance(repo_root, packet)


def _validate_packet_bindings(repo_root: Path, packet: dict[str, Any]) -> None:
    source = packet["content"]["source"]
    registry = load_yaml_at_revision(repo_root, source["record_version"], Path("prototypes.yaml"))
    prototype = _find_prototype(registry, source["prototype_id"])
    if prototype.get("lifecycle") != "baseline-approved":
        raise PacketError(
            "source_projection_mismatch",
            "the packet's bound source revision is not baseline-approved",
        )
    expected_values = {
        "owner": source["owner"],
        "design_baseline_ref": packet["content"]["baseline"]["record_ref"],
        **packet["content"]["posture"],
    }
    for key, expected in expected_values.items():
        if prototype.get(key) != expected:
            raise PacketError(
                "source_projection_mismatch",
                f"bound prototype {key} does not match packet content",
            )

    baseline_ref = packet["content"]["baseline"]["record_ref"]
    baseline = load_yaml(repo_root / _baseline_path(baseline_ref))
    baseline_binding = packet["content"]["baseline"]
    if baseline.get("prototype_id") != source["prototype_id"]:
        raise PacketError("baseline_binding_invalid", "baseline belongs to another prototype")
    if baseline.get("decision") != "approved":
        raise PacketError("baseline_not_approved", "design baseline is not approved")
    if baseline_binding["baseline_id"] != baseline.get("baseline_id"):
        raise PacketError("baseline_binding_invalid", "baseline id does not match")
    if baseline_binding["schema_version"] != baseline.get("schema_version"):
        raise PacketError("baseline_binding_invalid", "baseline schema version does not match")
    if baseline_binding["record_digest"] != content_digest(baseline):
        raise PacketError("baseline_binding_invalid", "baseline digest does not match")
    if baseline_binding["version"] != _baseline_version(baseline):
        raise PacketError("baseline_binding_invalid", "baseline version does not match")
    required_evidence = set(baseline.get("evidence_refs") or []) | set(
        baseline.get("security_review_refs") or []
    )
    missing_evidence = required_evidence - set(packet["content"]["evidence_refs"])
    if missing_evidence:
        raise PacketError(
            "baseline_binding_invalid",
            f"packet omits baseline evidence refs {sorted(missing_evidence)!r}",
        )


def validate_packet_file(repo_root: Path, packet_path: Path) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    packet_path = packet_path.resolve()
    packet = load_json(packet_path)
    validate_schema(
        schema_validator(repo_root, "prototype-delivery-packet.schema.json"),
        packet,
        code="malformed_packet",
        label="Prototype Delivery packet",
    )
    expected_path = (repo_root / _packet_relative_path(packet)).resolve()
    if packet_path != expected_path:
        raise PacketError(
            "packet_path_mismatch",
            f"packet must live at {expected_path.relative_to(repo_root)}",
        )
    _validate_packet_identity(packet)
    _validate_packet_source(repo_root, packet)
    _validate_packet_bindings(repo_root, packet)
    return packet


def validate_packet_records(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    validated: list[Path] = []
    source_versions: dict[tuple[str, str], str] = {}
    for path, packet in _existing_packets(repo_root):
        validate_packet_file(repo_root, path)
        source = packet["content"]["source"]
        key = (source["record_ref"], source["record_version"])
        previous_digest = source_versions.setdefault(key, packet["packet_digest"])
        if previous_digest != packet["packet_digest"]:
            raise PacketError(
                "packet_conflict",
                f"multiple packets bind source version {source['record_version']}",
            )
        validated.append(path)
    return validated
