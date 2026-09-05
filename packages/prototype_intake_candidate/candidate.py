from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import Any

from packages.prototype_delivery_packet.contract import (
    PacketError,
    content_digest,
    schema_validator,
    validate_schema,
)
from packages.prototype_delivery_packet.git_provenance import (
    load_yaml_at_revision,
    validate_source_revision,
)


SCHEMA = "prototype-intake-candidate.schema.json"


def build_candidate(
    repo_root: Path, request: dict[str, Any], *, historical: bool = False
) -> dict[str, Any]:
    """Project committed source only; no registry, lifecycle or remote writes."""
    validator = schema_validator(repo_root, SCHEMA)
    input_validator = validator.evolve(schema={
        "$defs": validator.schema["$defs"], "$ref": "#/$defs/input"
    })
    validate_schema(input_validator, request, code="candidate_input_invalid", label="candidate input")
    revision = request["source_revision"]
    tree = validate_source_revision(repo_root, revision, require_ref_match=not historical)
    head = revision["head_commit"]
    registry = load_yaml_at_revision(repo_root, head, Path("prototypes.yaml"))
    validate_schema(schema_validator(repo_root, "prototype-registry.schema.json"), registry,
                    code="source_record_invalid", label="committed Prototype registry")
    if (registry.get("studio") or {}).get("owner_repo") != revision["repository"]:
        raise PacketError("source_repository_mismatch", "registry owner differs from source repository")
    matches = [item for item in registry["prototypes"] if item["id"] == request["prototype_id"]]
    if len(matches) != 1:
        raise PacketError("prototype_identity_invalid", "source must contain exactly one matching prototype")
    prototype = matches[0]
    if prototype["lifecycle"] not in {"baseline-approved", "graduating"}:
        raise PacketError("lifecycle_not_eligible", "intake candidates require an approved baseline")
    if prototype["lifecycle"] == "graduating" and not prototype.get("delivery_packet_ref"):
        raise PacketError("source_record_invalid", "graduating source is missing its delivery packet link")
    baseline_ref = prototype.get("design_baseline_ref") or ""
    match = re.fullmatch(r"record://design-baselines/([a-z0-9]+(?:-[a-z0-9]+)*)", baseline_ref)
    if not match:
        raise PacketError("baseline_binding_invalid", "source must link a safe design baseline record")
    baseline = load_yaml_at_revision(repo_root, head, Path("records/design-baselines") / f"{match[1]}.yaml")
    validate_schema(schema_validator(repo_root, "design-baseline.schema.json"), baseline,
                    code="baseline_binding_invalid", label="committed design baseline")
    if baseline["prototype_id"] != prototype["id"] or baseline["baseline_id"] != match[1]:
        raise PacketError("baseline_binding_invalid", "baseline identity differs from source linkage")
    if baseline["decision"] != "approved":
        raise PacketError("baseline_not_approved", "baseline decision is not approved")

    content = {
        "request": copy.deepcopy(request),
        "source": {
            "record_ref": f"record://prototypes/{prototype['id']}",
            "record_version": head,
            "record_digest": content_digest(prototype),
            "tree": tree,
            **{key: prototype[key] for key in (
                "name", "lifecycle", "owner", "visibility_tier", "data_mode", "mutation_boundary"
            )},
            "linked_records": copy.deepcopy(prototype.get("linked_records") or []),
            "delivery_packet_ref": prototype.get("delivery_packet_ref"),
        },
        "baseline": {"record_ref": baseline_ref, "record_digest": content_digest(baseline)},
        "evidence_refs": sorted(set(baseline["evidence_refs"]) | set(baseline.get("security_review_refs") or [])),
        "authority": "source-candidate-only",
    }
    digest = content_digest(content)
    candidate = {
        "schema_version": 1,
        "artifact_type": "prototype-intake-candidate",
        "candidate_ref": f"record://intake-candidates/{digest.removeprefix('sha256:')}",
        "candidate_digest": digest,
        "content": content,
    }
    validate_schema(validator, candidate, code="candidate_invalid", label="candidate")
    return candidate


def validate_candidate(
    repo_root: Path, candidate: dict[str, Any], *, historical: bool = False
) -> dict[str, Any]:
    validate_schema(schema_validator(repo_root, SCHEMA), candidate,
                    code="candidate_invalid", label="candidate")
    expected = build_candidate(repo_root, candidate["content"]["request"], historical=historical)
    if candidate != expected:
        raise PacketError("candidate_source_mismatch", "candidate does not match its committed source and digest")
    return {
        "valid": True,
        "mode": "historical" if historical else "current-source",
        "source": {
            "class": "prototype",
            "ref": candidate["candidate_ref"],
            "digest": candidate["candidate_digest"],
        },
        "canonical_mutation": False,
    }
