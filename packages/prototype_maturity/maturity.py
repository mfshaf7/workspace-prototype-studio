from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import re
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from packages.prototype_delivery_packet.contract import (
    PacketError,
    content_digest,
    load_json,
    load_yaml,
    validate_schema,
)


CONTRACT_DIR = Path("contracts/prototype-maturity")
MATURITY_RECORD_DIR = Path("records/prototype-maturity")
SCHEMA_BY_TYPE = {
    "prototype-maturity-request": "prototype-maturity-request.schema.json",
    "prototype-maturity-packet": "prototype-maturity-packet.schema.json",
    "prototype-maturity-readiness": "prototype-maturity-readiness.schema.json",
    "prototype-maturity-decision": "prototype-maturity-decision.schema.json",
    "prototype-maturity-readback": "prototype-maturity-readback.schema.json",
    "prototype-maturity-receipt": "prototype-maturity-receipt.schema.json",
}
DIGEST_FIELD_BY_TYPE = {
    "prototype-maturity-request": "request_digest",
    "prototype-maturity-packet": "packet_digest",
    "prototype-maturity-readiness": "readiness_digest",
    "prototype-maturity-decision": "decision_digest",
    "prototype-maturity-readback": "readback_digest",
    "prototype-maturity-receipt": "receipt_digest",
}
ID_FIELD_BY_TYPE = {
    "prototype-maturity-request": "request_id",
    "prototype-maturity-packet": "packet_id",
    "prototype-maturity-readiness": "readiness_id",
    "prototype-maturity-decision": "decision_id",
    "prototype-maturity-readback": "readback_id",
    "prototype-maturity-receipt": "receipt_id",
}
CHECK_IDS = {
    "request-integrity",
    "lifecycle-source-state",
    "source-version-freshness",
    "packet-integrity",
    "required-evidence",
    "boundary-coherence",
    "security-trigger-disposition",
    "open-issue-disposition",
}
TRANSITIONS = {
    "candidate-promotion": {
        "source": "exploring",
        "target": "candidate",
        "packet_kind": "candidate-evidence-packet",
        "sections": {
            "candidate-brief",
            "scope-and-non-goals",
            "boundaries-and-risks",
        },
        "promotion_decision": "promote-candidate",
        "decisions": {"promote-candidate", "block-promotion", "route-closeout"},
        "editable_fields": {
            "prototype-objective": "text",
            "target-user": "text",
            "expected-proof": "text",
            "accepted-scope": "list",
            "excluded-scope": "list",
            "boundary-clarifications": "text",
            "open-issue-disposition": "text",
        },
    },
    "baseline-promotion": {
        "source": "candidate",
        "target": "baseline-approved",
        "packet_kind": "baseline-packet",
        "sections": {
            "definition",
            "design-and-workflow",
            "evidence",
            "boundaries",
            "issues-and-risk-disposition",
        },
        "promotion_decision": "approve-baseline",
        "decisions": {"approve-baseline", "block-baseline", "route-closeout"},
        "editable_fields": {
            "baseline-title": "text",
            "baseline-statement": "text",
            "accepted-summary": "text",
            "excluded-summary": "text",
            "selected-evidence-refs": "list",
            "missing-evidence-disposition": "text",
            "issue-and-risk-disposition": "text",
        },
    },
}
PROMOTION_DECISIONS = {profile["promotion_decision"] for profile in TRANSITIONS.values()}
BLOCK_DECISIONS = {"block-promotion", "block-baseline"}
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
SAFE_REF = re.compile(
    r"^(?:record|repo|openproject|evidence|proof|security-review|console|wgcf)://"
    r"[A-Za-z0-9][A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]*$"
)
SAFE_HTTPS_REF = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[^\s]*)?$")
SECRET_MARKERS = (
    "-----BEGIN PRIVATE KEY-----",
    "-----BEGIN RSA PRIVATE KEY-----",
    "-----BEGIN OPENSSH PRIVATE KEY-----",
)
MAX_TEXT_LENGTH = 2000
MAX_LIST_ITEMS = 50
MAX_REF_LENGTH = 512


@dataclass(frozen=True)
class MaturityResult:
    status: str
    prototype_id: str
    source_revision: str
    source_result_path: Path


def _run_git(repo_root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode:
        raise PacketError("git_error", result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def current_branch(repo_root: Path) -> str:
    branch = _run_git(repo_root, "branch", "--show-current")
    if not branch:
        raise PacketError("detached_head", "Prototype maturity requires a named branch")
    return branch


def current_head(repo_root: Path) -> str:
    return _run_git(repo_root, "rev-parse", "HEAD")


def _require_clean_worktree(repo_root: Path) -> None:
    if _run_git(repo_root, "status", "--porcelain"):
        raise PacketError("dirty_worktree", "Prototype maturity requires a clean source worktree")


def _worktree_revision(repo_root: Path) -> str:
    common_dir = Path(_run_git(repo_root, "rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    descriptor, index_name = tempfile.mkstemp(prefix="prototype-maturity-index-", dir=common_dir)
    os.close(descriptor)
    index_path = Path(index_name)
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


def _schema_validator(repo_root: Path, name: str) -> Draft202012Validator:
    schema = load_json(repo_root / CONTRACT_DIR / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _local_schema_validator(repo_root: Path, name: str) -> Draft202012Validator:
    schema = load_json(repo_root / "schemas" / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_contract_bundle(repo_root: Path) -> None:
    bundle = repo_root / CONTRACT_DIR
    manifest = load_json(bundle / "manifest.json")
    if manifest.get("authority_repo") != "workspace-governance":
        raise PacketError("contract_bundle_invalid", "Prototype maturity authority repo is invalid")
    security_review = manifest.get("security_review") or {}
    if security_review.get("decision") != "approved-with-findings":
        raise PacketError("contract_bundle_invalid", "Prototype maturity security review is not accepted")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise PacketError("contract_bundle_invalid", "Prototype maturity manifest has no files")
    for name, expected in files.items():
        path = bundle / name
        if not path.is_file():
            raise PacketError("contract_bundle_invalid", f"missing synchronized contract file {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise PacketError("contract_bundle_stale", f"synchronized contract digest differs for {name}")
    validate_schema(
        _schema_validator(repo_root, "prototype-maturity.schema.json"),
        load_yaml(bundle / "prototype-maturity.yaml"),
        code="contract_bundle_invalid",
        label="Prototype maturity contract",
    )


def validate_artifact(repo_root: Path, artifact: dict[str, Any]) -> None:
    artifact_type = str(artifact.get("artifact_type") or "")
    schema_name = SCHEMA_BY_TYPE.get(artifact_type)
    if schema_name is None:
        raise PacketError("artifact_type_invalid", f"unsupported maturity artifact {artifact_type!r}")
    validate_schema(
        _schema_validator(repo_root, schema_name),
        artifact,
        code="artifact_invalid",
        label=artifact_type,
    )
    digest_field = DIGEST_FIELD_BY_TYPE[artifact_type]
    body = {key: value for key, value in artifact.items() if key != digest_field}
    if artifact[digest_field] != content_digest(body):
        raise PacketError("artifact_digest_mismatch", f"{artifact_type} digest does not match its content")


def _artifact_ref(artifact: dict[str, Any]) -> dict[str, str]:
    artifact_type = str(artifact["artifact_type"])
    return {
        "id": str(artifact[ID_FIELD_BY_TYPE[artifact_type]]),
        "digest": str(artifact[DIGEST_FIELD_BY_TYPE[artifact_type]]),
    }


def _require_ref(actual: Any, expected: dict[str, str], label: str) -> None:
    if actual != expected:
        raise PacketError("artifact_binding_invalid", f"{label} does not bind the exact artifact")


def _validate_text(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise PacketError("editable_values_invalid", f"{label} must be non-empty text")
    if len(value) > MAX_TEXT_LENGTH:
        raise PacketError("editable_values_invalid", f"{label} exceeds {MAX_TEXT_LENGTH} characters")
    if any(marker in value for marker in SECRET_MARKERS) or "\x00" in value:
        raise PacketError("unsafe_content", f"{label} contains prohibited content")


def _validate_ref(value: Any, label: str) -> None:
    _validate_text(value, label)
    assert isinstance(value, str)
    if len(value) > MAX_REF_LENGTH:
        raise PacketError("reference_invalid", f"{label} exceeds {MAX_REF_LENGTH} characters")
    if not (SAFE_REF.fullmatch(value) or SAFE_HTTPS_REF.fullmatch(value)):
        raise PacketError("reference_invalid", f"{label} uses an unsupported reference form")
    if "\\" in value or any(part == ".." for part in value.split("/")):
        raise PacketError("reference_invalid", f"{label} contains an unsafe path")


def _validate_list(value: Any, label: str, *, refs: bool = False) -> None:
    if not isinstance(value, list) or not value or len(value) > MAX_LIST_ITEMS:
        raise PacketError(
            "editable_values_invalid",
            f"{label} must contain between 1 and {MAX_LIST_ITEMS} unique items",
        )
    if any(not isinstance(item, str) for item in value):
        raise PacketError("editable_values_invalid", f"{label} items must be text")
    if len(value) != len(set(value)):
        raise PacketError("editable_values_invalid", f"{label} must not contain duplicates")
    for index, item in enumerate(value):
        if refs:
            _validate_ref(item, f"{label}[{index}]")
        else:
            _validate_text(item, f"{label}[{index}]")


def _validate_ref_collection(value: Any, label: str, *, required: bool) -> None:
    if not isinstance(value, list) or len(value) > MAX_LIST_ITEMS:
        raise PacketError("reference_invalid", f"{label} must be a bounded reference list")
    if required and not value:
        raise PacketError("reference_invalid", f"{label} must contain evidence")
    if any(not isinstance(item, str) for item in value) or len(value) != len(set(value)):
        raise PacketError("reference_invalid", f"{label} must contain unique text references")
    for index, item in enumerate(value):
        _validate_ref(item, f"{label}[{index}]")


def _validate_editable_values(transition: str, values: Any) -> None:
    if not isinstance(values, dict):
        raise PacketError("editable_values_invalid", "editable_values must be an object")
    profile = TRANSITIONS[transition]
    expected = profile["editable_fields"]
    if set(values) != set(expected):
        raise PacketError(
            "editable_values_invalid",
            f"{transition} editable_values must contain the exact transition fields",
        )
    for name, kind in expected.items():
        if kind == "text":
            _validate_text(values[name], name)
        else:
            _validate_list(
                values[name],
                name,
                refs=name == "selected-evidence-refs",
            )


def _validate_chain(
    request: dict[str, Any],
    packet: dict[str, Any],
    readiness: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    transition = str(request["transition"])
    profile = TRANSITIONS.get(transition)
    if profile is None:
        raise PacketError("transition_invalid", f"unsupported Prototype maturity transition {transition!r}")
    _require_ref(packet["request_ref"], _artifact_ref(request), "packet request")
    _require_ref(readiness["request_ref"], _artifact_ref(request), "readiness request")
    _require_ref(readiness["packet_ref"], _artifact_ref(packet), "readiness packet")
    _require_ref(decision["request_ref"], _artifact_ref(request), "decision request")
    _require_ref(decision["packet_ref"], _artifact_ref(packet), "decision packet")
    _require_ref(decision["readiness_ref"], _artifact_ref(readiness), "decision readiness")
    if any(item["prototype_id"] != request["prototype_id"] for item in (packet, readiness, decision)):
        raise PacketError("prototype_identity_mismatch", "maturity artifacts bind different Prototype identities")
    if any(item["transition"] != transition for item in (packet, readiness, decision)):
        raise PacketError("transition_mismatch", "maturity artifacts bind different transitions")
    if (
        request["source_lifecycle"] != profile["source"]
        or request["target_lifecycle"] != profile["target"]
        or request["expected_state"]["lifecycle"] != profile["source"]
    ):
        raise PacketError("lifecycle_pair_invalid", "request lifecycle pair differs from the transition")
    if packet["packet_kind"] != profile["packet_kind"]:
        raise PacketError("packet_kind_invalid", "packet kind differs from the transition")
    sections = packet["sections"]
    section_ids = [section["id"] for section in sections]
    if len(section_ids) != len(set(section_ids)) or set(section_ids) != profile["sections"]:
        raise PacketError("packet_sections_invalid", "packet must contain each transition section exactly once")
    for section in sections:
        _validate_ref_collection(
            section["evidence_refs"],
            f"packet section {section['id']} evidence_refs",
            required=decision["decision"] == profile["promotion_decision"],
        )
        if section.get("note") is not None:
            _validate_text(section["note"], f"packet section {section['id']} note")
    check_ids = [check["id"] for check in readiness["checks"]]
    if len(check_ids) != len(set(check_ids)) or set(check_ids) != CHECK_IDS:
        raise PacketError("readiness_invalid", "readiness must contain each maturity check exactly once")
    check_states = {check["state"] for check in readiness["checks"]}
    if readiness["outcome"] == "ready" and check_states != {"ready"}:
        raise PacketError("readiness_invalid", "ready outcome requires every maturity check to be ready")
    if readiness["outcome"] == "blocked" and "blocked" not in check_states:
        raise PacketError("readiness_invalid", "blocked outcome requires a blocked maturity check")
    if readiness["outcome"] == "stale" and "stale" not in check_states:
        raise PacketError("readiness_invalid", "stale outcome requires a stale maturity check")
    if readiness["outcome"] == "ready" and any(
        finding["severity"] == "blocking" for finding in readiness["findings"]
    ):
        raise PacketError("readiness_invalid", "ready outcome cannot contain a blocking finding")
    for check in readiness["checks"]:
        _validate_ref_collection(
            check["evidence_refs"],
            f"readiness check {check['id']} evidence_refs",
            required=True,
        )
    for index, finding in enumerate(readiness["findings"]):
        _validate_text(finding["code"], f"readiness finding {index} code")
        _validate_text(finding["detail"], f"readiness finding {index} detail")
        if finding.get("owner_ref") is not None:
            _validate_text(finding["owner_ref"], f"readiness finding {index} owner_ref")
        if finding.get("required_fix") is not None:
            _validate_text(finding["required_fix"], f"readiness finding {index} required_fix")
    if readiness["observed_state"] != request["expected_state"] or decision["expected_state"] != request["expected_state"]:
        raise PacketError("expected_state_mismatch", "request, readiness, and decision source states differ")
    if decision["decision"] not in profile["decisions"]:
        raise PacketError("decision_invalid", "decision does not belong to the selected transition")
    blocker = decision["blocker"]
    if decision["decision"] in BLOCK_DECISIONS:
        if not isinstance(blocker, dict) or not all(blocker.get(key) for key in ("issue_ref", "owner_ref", "required_fix")):
            raise PacketError("blocker_invalid", "block decisions require an issue ref, owner, and required fix")
        _validate_ref(blocker["issue_ref"], "blocker issue_ref")
        _validate_text(blocker["owner_ref"], "blocker owner_ref")
        _validate_text(blocker["required_fix"], "blocker required_fix")
    elif blocker is not None:
        raise PacketError("blocker_invalid", "non-block decisions cannot carry blocker metadata")
    if request["correlation_id"] != decision["correlation_id"]:
        raise PacketError("correlation_mismatch", "request and decision correlation ids differ")
    if request["idempotency_key"] != decision["idempotency_key"]:
        raise PacketError("idempotency_mismatch", "request and decision idempotency keys differ")
    for label, value in (
        ("request operator_ref", request["operator_ref"]),
        ("decision operator_ref", decision["operator_ref"]),
        ("correlation_id", request["correlation_id"]),
        ("idempotency_key", request["idempotency_key"]),
    ):
        _validate_text(value, label)
    _validate_list(request["inputs"]["source_refs"], "source_refs", refs=True)
    _validate_editable_values(transition, request["inputs"]["editable_values"])
    if decision["decision"] == profile["promotion_decision"]:
        if readiness["outcome"] != "ready" or any(check["state"] != "ready" for check in readiness["checks"]):
            raise PacketError("readiness_denied", "promotion requires every readiness check to be ready")
        if any(section["state"] != "ready" for section in sections):
            raise PacketError("packet_not_ready", "promotion requires every packet section to be ready")
    return profile


def _slug(prototype_id: str) -> str:
    value = prototype_id.removeprefix("prototype:")
    if prototype_id != f"prototype:{value}" or not SAFE_ID.fullmatch(value):
        raise PacketError("prototype_identity_invalid", "Prototype identity is not a safe source id")
    return value


def _registry_item(registry: dict[str, Any], slug: str) -> dict[str, Any]:
    matches = [item for item in registry.get("prototypes", []) if item.get("id") == slug]
    if len(matches) != 1:
        raise PacketError("prototype_record_invalid", f"Prototype registry must contain exactly one {slug} record")
    return matches[0]


def _landing_record_path(repo_root: Path, slug: str) -> Path:
    return repo_root / "records" / "prototype-landings" / slug / "record.json"


def _require_landed(repo_root: Path, item: dict[str, Any], slug: str) -> None:
    expected_ref = f"record://prototype-landings/{slug}"
    if item.get("landing_record_ref") != expected_ref:
        raise PacketError("landing_evidence_missing", "Prototype maturity requires a canonical Landing record")
    record_path = _landing_record_path(repo_root, slug)
    if not record_path.is_file():
        raise PacketError("landing_evidence_missing", "Prototype Landing record does not resolve")
    record = load_json(record_path)
    if record.get("id") != f"prototype:{slug}":
        raise PacketError("landing_evidence_invalid", "Prototype Landing identity differs from the registry")


def current_state(repo_root: Path, prototype_id: str) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    slug = _slug(prototype_id)
    registry = load_yaml(repo_root / "prototypes.yaml")
    item = _registry_item(registry, slug)
    _require_landed(repo_root, item, slug)
    return {
        "prototype_id": prototype_id,
        "expected_state": {
            "source_revision": current_head(repo_root),
            "record_digest": content_digest(item),
            "lifecycle": item["lifecycle"],
        },
    }


def _require_expected_state(repo_root: Path, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str]:
    slug = _slug(request["prototype_id"])
    registry = load_yaml(repo_root / "prototypes.yaml")
    item = _registry_item(registry, slug)
    _require_landed(repo_root, item, slug)
    actual = {
        "source_revision": current_head(repo_root),
        "record_digest": content_digest(item),
        "lifecycle": item["lifecycle"],
    }
    if actual != request["expected_state"]:
        raise PacketError("source_state_stale", "Prototype source state differs from the maturity request")
    return registry, item, slug


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _yaml_bytes(payload: dict[str, Any]) -> bytes:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False).encode("utf-8")


def _with_digest(payload: dict[str, Any], field: str) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result[field] = content_digest(result)
    return result


def _sequence(artifact_id: str) -> str:
    value = artifact_id.rsplit(":", 1)[-1]
    if not value.isdigit():
        raise PacketError("artifact_identity_invalid", "maturity artifact id has no numeric sequence")
    return value


def _safe_history_name(decision: dict[str, Any]) -> str:
    return decision["decision_id"].replace(":", "-") + ".json"


def _candidate_record(
    request: dict[str, Any],
    packet: dict[str, Any],
    readiness: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    slug = _slug(request["prototype_id"])
    return _with_digest(
        {
            "schema_version": 1,
            "artifact_type": "prototype-candidate-record",
            "record_id": f"prototype-candidate:{slug}:{_sequence(decision['decision_id'])}",
            "prototype_id": request["prototype_id"],
            "promoted_at": decision["decided_at"],
            "promoted_by": decision["operator_ref"],
            "request_ref": _artifact_ref(request),
            "packet_ref": _artifact_ref(packet),
            "readiness_ref": _artifact_ref(readiness),
            "decision_ref": _artifact_ref(decision),
            "expected_state": copy.deepcopy(request["expected_state"]),
            "accepted_values": copy.deepcopy(request["inputs"]["editable_values"]),
        },
        "record_digest",
    )


def _packet_evidence(packet: dict[str, Any]) -> list[str]:
    refs = {
        ref
        for section in packet["sections"]
        for ref in section["evidence_refs"]
    }
    return sorted(refs)


def _baseline_id(slug: str, decision: dict[str, Any]) -> str:
    return f"{slug}-baseline-{_sequence(decision['decision_id'])}"


def _baseline_record(
    item: dict[str, Any],
    request: dict[str, Any],
    packet: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    values = request["inputs"]["editable_values"]
    evidence_refs = sorted(set(_packet_evidence(packet)) | set(values["selected-evidence-refs"]))
    constraints = [
        values["excluded-summary"],
        values["missing-evidence-disposition"],
        values["issue-and-risk-disposition"],
        "Baseline approval is local Prototype maturity only and grants no cross-domain authority.",
    ]
    return {
        "schema_version": 1,
        "prototype_id": _slug(request["prototype_id"]),
        "baseline_id": _baseline_id(_slug(request["prototype_id"]), decision),
        "approved_on": decision["decided_at"][:10],
        "approved_by": decision["operator_ref"],
        "decision": "approved",
        "title": values["baseline-title"],
        "statement": values["baseline-statement"],
        "accepted_summary": values["accepted-summary"],
        "excluded_summary": values["excluded-summary"],
        "missing_evidence_disposition": values["missing-evidence-disposition"],
        "issue_and_risk_disposition": values["issue-and-risk-disposition"],
        "source_refs": copy.deepcopy(request["inputs"]["source_refs"]),
        "art_refs": [
            ref for ref in request["inputs"]["source_refs"] if ref.startswith("openproject://")
        ],
        "security_review_refs": copy.deepcopy(item.get("security_review_refs") or []),
        "evidence_refs": evidence_refs,
        "constraints": constraints,
    }


def _append_link(item: dict[str, Any], link: dict[str, str]) -> None:
    links = item.setdefault("linked_records", [])
    if any(existing.get("role") == link["role"] and existing.get("ref") == link["ref"] for existing in links):
        raise PacketError("source_target_conflict", f"Prototype already links {link['ref']}")
    links.append(link)


def _require_candidate_record(repo_root: Path, item: dict[str, Any], slug: str) -> None:
    candidate_ref = item.get("candidate_record_ref") or f"record://prototype-maturity/{slug}/candidate"
    prefix = f"record://prototype-maturity/{slug}/"
    stem = str(candidate_ref).removeprefix(prefix)
    if not str(candidate_ref).startswith(prefix) or not re.fullmatch(r"candidate(?:-[0-9a-f]{12})?", stem):
        raise PacketError("candidate_evidence_invalid", "active candidate record reference is invalid")
    candidate_path = repo_root / MATURITY_RECORD_DIR / slug / f"{stem}.json"
    if not candidate_path.is_file():
        raise PacketError("candidate_evidence_missing", "Baseline Promotion requires a candidate record")
    candidate = load_json(candidate_path)
    validate_schema(
        _local_schema_validator(repo_root, "prototype-candidate-record.schema.json"),
        candidate,
        code="candidate_evidence_invalid",
        label="Prototype candidate record",
    )
    body = {key: value for key, value in candidate.items() if key != "record_digest"}
    links = [
        link
        for link in item.get("linked_records", [])
        if link.get("role") == "candidate-record" and link.get("ref") == candidate_ref
    ]
    if (
        candidate.get("prototype_id") != f"prototype:{slug}"
        or candidate.get("record_digest") != content_digest(body)
        or len(links) != 1
    ):
        raise PacketError("candidate_evidence_invalid", "candidate record and registry linkage disagree")


def _prepare_writes(
    repo_root: Path,
    registry: dict[str, Any],
    item: dict[str, Any],
    request: dict[str, Any],
    packet: dict[str, Any],
    readiness: dict[str, Any],
    decision: dict[str, Any],
) -> tuple[dict[Path, bytes], dict[str, Any], dict[str, Any]]:
    slug = _slug(request["prototype_id"])
    updated_registry = copy.deepcopy(registry)
    updated_item = _registry_item(updated_registry, slug)
    transition = request["transition"]
    updated_item["lifecycle"] = TRANSITIONS[transition]["target"]
    writes: dict[Path, bytes] = {}

    if transition == "candidate-promotion":
        candidate = _candidate_record(request, packet, readiness, decision)
        candidate_stem = (
            f"candidate-{content_digest(request).removeprefix('sha256:')[:12]}"
            if (repo_root / MATURITY_RECORD_DIR / slug / "candidate.json").exists()
            else "candidate"
        )
        candidate_path = repo_root / MATURITY_RECORD_DIR / slug / f"{candidate_stem}.json"
        candidate_ref = f"record://prototype-maturity/{slug}/{candidate_stem}"
        updated_item["candidate_record_ref"] = candidate_ref
        _append_link(
            updated_item,
            {
                "role": "candidate-record",
                "ref": candidate_ref,
                "system": "prototype-studio",
                "level": "record",
                "label": "Prototype Candidate Promotion record",
            },
        )
        validate_schema(
            _local_schema_validator(repo_root, "prototype-candidate-record.schema.json"),
            candidate,
            code="source_record_invalid",
            label="Prototype candidate record",
        )
        writes[candidate_path] = _json_bytes(candidate)
    else:
        _require_candidate_record(repo_root, item, slug)
        baseline = _baseline_record(item, request, packet, decision)
        baseline_id = baseline["baseline_id"]
        baseline_ref = f"record://design-baselines/{baseline_id}"
        updated_item["design_baseline_ref"] = baseline_ref
        _append_link(
            updated_item,
            {
                "role": "baseline-record",
                "ref": baseline_ref,
                "system": "prototype-studio",
                "level": "record",
                "label": request["inputs"]["editable_values"]["baseline-title"],
            },
        )
        validate_schema(
            _local_schema_validator(repo_root, "design-baseline.schema.json"),
            baseline,
            code="source_record_invalid",
            label="Prototype design baseline",
        )
        writes[repo_root / "records" / "design-baselines" / f"{baseline_id}.yaml"] = _yaml_bytes(baseline)

    validate_schema(
        _local_schema_validator(repo_root, "prototype-registry.schema.json"),
        updated_registry,
        code="source_record_invalid",
        label="updated Prototype registry",
    )
    writes[repo_root / "prototypes.yaml"] = _yaml_bytes(updated_registry)
    history_path = repo_root / MATURITY_RECORD_DIR / slug / "history" / _safe_history_name(decision)
    writes[history_path] = _json_bytes(decision)
    collisions = [
        path.relative_to(repo_root)
        for path in writes
        if path != repo_root / "prototypes.yaml" and path.exists()
    ]
    if collisions:
        raise PacketError(
            "source_target_conflict",
            "maturity transition would overwrite source: " + ", ".join(map(str, collisions)),
        )
    return writes, updated_registry, updated_item


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
    lock_path = common_dir / "prototype-maturity.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _ensure_output_outside_repo(repo_root: Path, output_path: Path) -> None:
    try:
        output_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return
    raise PacketError("output_boundary_invalid", "maturity evidence output must be outside Prototype Studio")


def _write_evidence(transaction: _Transaction, path: Path, payload: dict[str, Any]) -> None:
    content = _json_bytes(payload)
    if path.exists():
        if path.read_bytes() == content:
            return
        raise PacketError("evidence_conflict", f"maturity evidence already exists at {path}")
    transaction.write(path, content)


def _existing_decision(repo_root: Path, idempotency_key: str) -> dict[str, Any] | None:
    for path in sorted((repo_root / MATURITY_RECORD_DIR).glob("*/history/*.json")):
        artifact = load_json(path)
        if artifact.get("artifact_type") != "prototype-maturity-decision":
            continue
        validate_artifact(repo_root, artifact)
        if artifact.get("idempotency_key") == idempotency_key:
            return artifact
    return None


def _source_result(
    *,
    decision: dict[str, Any],
    item: dict[str, Any],
    branch: str,
    revision: str,
    changed_paths: list[str],
    outcome: str,
    now: str,
) -> dict[str, Any]:
    if decision["decision"] in PROMOTION_DECISIONS:
        next_action = {"code": "review-source", "owner_ref": "operator-orchestration-service"}
    elif decision["decision"] == "route-closeout":
        next_action = {"code": "prototype-closeout", "owner_ref": "operator-orchestration-service"}
    else:
        next_action = {"code": "resolve-blocker", "owner_ref": decision["blocker"]["owner_ref"]}
    payload = _with_digest(
        {
            "schema_version": 1,
            "artifact_type": "prototype-maturity-source-result",
            "result_id": (
                f"prototype-maturity-source-result:{_slug(decision['prototype_id'])}:"
                f"{_sequence(decision['decision_id'])}"
            ),
            "prepared_at": now,
            "decision_ref": _artifact_ref(decision),
            "prototype_id": decision["prototype_id"],
            "transition": decision["transition"],
            "decision": decision["decision"],
            "outcome": outcome,
            "source_branch": branch,
            "source_revision": revision,
            "record_digest": content_digest(item),
            "changed_paths": changed_paths,
            "next_action": next_action,
        },
        "result_digest",
    )
    return payload


def apply_maturity(
    *,
    repo_root: Path,
    request: dict[str, Any],
    packet: dict[str, Any],
    readiness: dict[str, Any],
    decision: dict[str, Any],
    output_path: Path,
    prepared_at: str | None = None,
) -> MaturityResult:
    repo_root = repo_root.resolve()
    output_path = output_path.resolve()
    _ensure_output_outside_repo(repo_root, output_path)
    validate_contract_bundle(repo_root)
    for artifact in (request, packet, readiness, decision):
        validate_artifact(repo_root, artifact)
    profile = _validate_chain(request, packet, readiness, decision)
    branch = current_branch(repo_root)
    now = prepared_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    with _authority_lock(repo_root):
        slug = _slug(request["prototype_id"])
        registry = load_yaml(repo_root / "prototypes.yaml")
        item = _registry_item(registry, slug)
        _require_landed(repo_root, item, slug)
        is_promotion = decision["decision"] == profile["promotion_decision"]
        if is_promotion and (branch in {"main", "master"} or branch != decision["source_branch"]):
            raise PacketError("source_branch_invalid", "promotion must bind the current non-default review branch")
        existing = _existing_decision(repo_root, request["idempotency_key"])
        if existing is not None:
            if existing != decision:
                raise PacketError("idempotency_conflict", "idempotency key is bound to another maturity decision")
            if not is_promotion:
                raise PacketError("source_history_invalid", "non-promotion decisions cannot have source history")
            if item["lifecycle"] != profile["target"]:
                raise PacketError("replay_state_invalid", "maturity history and current lifecycle disagree")
            revision = _worktree_revision(repo_root)
            result = _source_result(
                decision=decision,
                item=item,
                branch=branch,
                revision=revision,
                changed_paths=[],
                outcome="replayed",
                now=now,
            )
            validate_schema(
                _local_schema_validator(repo_root, "prototype-maturity-source-result.schema.json"),
                result,
                code="source_result_invalid",
                label="Prototype maturity source result",
            )
            transaction = _Transaction()
            try:
                _write_evidence(transaction, output_path, result)
            except BaseException:
                transaction.rollback()
                raise
            return MaturityResult("replayed", request["prototype_id"], revision, output_path)

        registry, item, slug = _require_expected_state(repo_root, request)
        if not is_promotion:
            result = _source_result(
                decision=decision,
                item=item,
                branch=branch,
                revision=current_head(repo_root),
                changed_paths=[],
                outcome="unchanged",
                now=now,
            )
            validate_schema(
                _local_schema_validator(repo_root, "prototype-maturity-source-result.schema.json"),
                result,
                code="source_result_invalid",
                label="Prototype maturity source result",
            )
            transaction = _Transaction()
            try:
                _write_evidence(transaction, output_path, result)
            except BaseException:
                transaction.rollback()
                raise
            return MaturityResult("unchanged", request["prototype_id"], current_head(repo_root), output_path)

        _require_clean_worktree(repo_root)
        writes, _, updated_item = _prepare_writes(
            repo_root,
            registry,
            item,
            request,
            packet,
            readiness,
            decision,
        )
        transaction = _Transaction()
        try:
            for path, content in sorted(writes.items(), key=lambda entry: str(entry[0])):
                transaction.write(path, content)
            revision = _worktree_revision(repo_root)
            changed_paths = sorted(str(path.relative_to(repo_root)) for path in writes)
            result = _source_result(
                decision=decision,
                item=updated_item,
                branch=branch,
                revision=revision,
                changed_paths=changed_paths,
                outcome="prepared",
                now=now,
            )
            validate_schema(
                _local_schema_validator(repo_root, "prototype-maturity-source-result.schema.json"),
                result,
                code="source_result_invalid",
                label="Prototype maturity source result",
            )
            _write_evidence(transaction, output_path, result)
        except BaseException:
            transaction.rollback()
            raise
    return MaturityResult("prepared", request["prototype_id"], revision, output_path)


def readback_maturity(
    *,
    repo_root: Path,
    decision: dict[str, Any],
    output_path: Path,
    observed_at: str | None = None,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    output_path = output_path.resolve()
    _ensure_output_outside_repo(repo_root, output_path)
    validate_contract_bundle(repo_root)
    validate_artifact(repo_root, decision)
    profile = TRANSITIONS[decision["transition"]]
    slug = _slug(decision["prototype_id"])
    registry = load_yaml(repo_root / "prototypes.yaml")
    item = _registry_item(registry, slug)
    _require_landed(repo_root, item, slug)
    promotion = decision["decision"] == profile["promotion_decision"]
    branch = current_branch(repo_root)
    head = current_head(repo_root)
    expected = decision["expected_state"]

    if promotion:
        if branch not in {"main", "master"}:
            raise PacketError("authority_branch_invalid", "merged maturity readback requires the default branch")
        if item["lifecycle"] != profile["target"]:
            raise PacketError("merged_readback_invalid", "merged source does not show the target lifecycle")
        _require_candidate_record(repo_root, item, slug)
        if decision["transition"] == "baseline-promotion":
            baseline_id = _baseline_id(slug, decision)
            expected_ref = f"record://design-baselines/{baseline_id}"
            baseline_path = repo_root / "records" / "design-baselines" / f"{baseline_id}.yaml"
            if item.get("design_baseline_ref") != expected_ref or not baseline_path.is_file():
                raise PacketError("merged_readback_invalid", "merged source does not contain the exact baseline record")
        history_path = repo_root / MATURITY_RECORD_DIR / slug / "history" / _safe_history_name(decision)
        if not history_path.is_file() or load_json(history_path) != decision:
            raise PacketError("merged_readback_invalid", "merged source does not contain the exact maturity decision")
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", expected["source_revision"], head],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise PacketError("source_history_invalid", "expected source revision is not an ancestor of merged source")
        authority_state = "merged-authority"
    else:
        if item["lifecycle"] != profile["source"] or content_digest(item) != expected["record_digest"]:
            raise PacketError("unchanged_readback_invalid", "non-promotion readback does not preserve source state")
        authority_state = "unchanged-authority"

    now = observed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    readback = _with_digest(
        {
            "schema_version": 1,
            "artifact_type": "prototype-maturity-readback",
            "readback_id": f"prototype-maturity-readback:{slug}:{_sequence(decision['decision_id'])}",
            "observed_at": now,
            "decision_ref": _artifact_ref(decision),
            "prototype_id": decision["prototype_id"],
            "transition": decision["transition"],
            "decision": decision["decision"],
            "authority_state": authority_state,
            "source_revision": head,
            "record_digest": content_digest(item),
            "observed_lifecycle": item["lifecycle"],
            "record_ref": f"record://prototype-registry/{slug}",
        },
        "readback_digest",
    )
    validate_artifact(repo_root, readback)
    transaction = _Transaction()
    try:
        _write_evidence(transaction, output_path, readback)
    except BaseException:
        transaction.rollback()
        raise
    return readback


def validate_maturity_records(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    validate_contract_bundle(repo_root)
    registry = load_yaml(repo_root / "prototypes.yaml")
    registry_by_id = {item["id"]: item for item in registry.get("prototypes", [])}
    candidate_validator = _local_schema_validator(repo_root, "prototype-candidate-record.schema.json")
    validated: list[Path] = []
    used_keys: dict[str, str] = {}
    candidate_decision_refs: dict[str, set[tuple[str, str]]] = {}

    for candidate_path in sorted((repo_root / MATURITY_RECORD_DIR).glob("*/candidate*.json")):
        candidate = load_json(candidate_path)
        validate_schema(
            candidate_validator,
            candidate,
            code="source_record_invalid",
            label=str(candidate_path.relative_to(repo_root)),
        )
        body = {key: value for key, value in candidate.items() if key != "record_digest"}
        if candidate["record_digest"] != content_digest(body):
            raise PacketError("source_record_invalid", f"{candidate_path} digest does not match")
        slug = _slug(candidate["prototype_id"])
        if not re.fullmatch(r"candidate(?:-[0-9a-f]{12})?\.json", candidate_path.name) or candidate_path.parent.name != slug:
            raise PacketError("source_record_path_invalid", f"candidate record path differs for {slug}")
        item = registry_by_id.get(slug)
        expected_ref = f"record://prototype-maturity/{slug}/{candidate_path.stem}"
        links = [
            link for link in (item or {}).get("linked_records", [])
            if link.get("role") == "candidate-record" and link.get("ref") == expected_ref
        ]
        if len(links) != 1:
            raise PacketError("source_record_unlinked", f"candidate record {slug} is not linked exactly once")
        active_ref = (item or {}).get("candidate_record_ref")
        if (item or {}).get("lifecycle") == "exploring":
            closure_ref = str((item or {}).get("closure_event_ref") or "")
            prefix = f"record://prototype-closure/{slug}/history/prototype-closure:{slug}:"
            if not closure_ref.startswith(prefix) or not closure_ref.removeprefix(prefix).isdigit():
                raise PacketError("source_record_invalid", f"candidate record {slug} has exploring registry state without reopen")
            sequence = int(closure_ref.removeprefix(prefix))
            reopen_path = repo_root / "records" / "prototype-closure" / slug / "history" / f"{sequence:04d}.json"
            if not reopen_path.is_file() or load_json(reopen_path).get("event_type") != "incubation-reopened":
                raise PacketError("source_record_invalid", f"candidate record {slug} lacks a valid reopen event")
            if active_ref == expected_ref:
                raise PacketError("source_record_invalid", f"candidate record {slug} is still active after reopen")
        decision_ref = candidate["decision_ref"]
        candidate_decision_refs.setdefault(slug, set()).add((decision_ref["id"], decision_ref["digest"]))
        validated.append(candidate_path)

    history_refs: set[tuple[str, str]] = set()
    for history_path in sorted((repo_root / MATURITY_RECORD_DIR).glob("*/history/*.json")):
        decision = load_json(history_path)
        validate_artifact(repo_root, decision)
        slug = _slug(decision["prototype_id"])
        if history_path.parent.parent.name != slug or history_path.name != _safe_history_name(decision):
            raise PacketError("source_history_invalid", f"maturity history path differs for {decision['decision_id']}")
        previous = used_keys.setdefault(decision["idempotency_key"], decision["decision_digest"])
        if previous != decision["decision_digest"]:
            raise PacketError("idempotency_conflict", f"conflicting maturity history for {decision['idempotency_key']}")
        if decision["decision"] not in PROMOTION_DECISIONS:
            raise PacketError("source_history_invalid", "non-promotion decisions cannot be stored in source history")
        history_refs.add((decision["decision_id"], decision["decision_digest"]))
        item = registry_by_id.get(slug) or {}
        if decision["transition"] == "candidate-promotion":
            if (decision["decision_id"], decision["decision_digest"]) not in candidate_decision_refs.get(slug, set()):
                raise PacketError("source_history_invalid", f"candidate record {slug} does not bind its decision")
        else:
            baseline_id = _baseline_id(slug, decision)
            baseline_path = repo_root / "records" / "design-baselines" / f"{baseline_id}.yaml"
            baseline = load_yaml(baseline_path)
            required_fields = {
                "title",
                "statement",
                "accepted_summary",
                "excluded_summary",
                "missing_evidence_disposition",
                "issue_and_risk_disposition",
            }
            if any(not baseline.get(field) for field in required_fields):
                raise PacketError("source_history_invalid", f"baseline record {baseline_id} is incomplete")
            expected_ref = f"record://design-baselines/{baseline_id}"
            if not any(
                link.get("role") == "baseline-record" and link.get("ref") == expected_ref
                for link in item.get("linked_records", [])
            ):
                raise PacketError("source_history_invalid", f"baseline record {baseline_id} is not linked")
        validated.append(history_path)
    missing_history = [
        slug
        for slug, decision_refs in candidate_decision_refs.items()
        if not decision_refs.issubset(history_refs)
    ]
    if missing_history:
        raise PacketError(
            "source_history_invalid",
            "candidate records are missing immutable decision history: " + ", ".join(missing_history),
        )
    return validated
