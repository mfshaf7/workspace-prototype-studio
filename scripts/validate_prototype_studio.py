#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator, FormatChecker

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from packages.prototype_delivery_packet.packet import (  # noqa: E402
    PacketError,
    validate_packet_records,
)


LIFECYCLES = {
    "exploring",
    "candidate",
    "baseline-approved",
    "graduating",
    "graduated",
    "retired",
}
PORTFOLIOS = {"internal-product", "client-app", "workspace-system", "experiment"}
VISIBILITY_TIERS = {"private-internal", "operator-review", "client-review", "public-demo"}
DATA_MODES = {"mock", "synthetic", "real-readonly", "real-mutable"}
MUTATION_BOUNDARIES = {
    "none",
    "read-only",
    "prototype-local",
    "external-sandbox",
    "real-system",
}
LINKED_RECORD_ROLES = {
    "proposal-source",
    "delivery-initiative",
    "studio-anchor",
    "candidate-record",
    "baseline-record",
    "delivery-packet",
    "graduation-record",
    "retirement-record",
}
LINKED_RECORD_SYSTEMS = {"openproject", "repo", "prototype-studio"}
LINKED_RECORD_LEVELS = {"proposal", "epic", "feature", "user-story", "record", "repo"}
PROTOTYPE_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
OPENPROJECT_WORK_PACKAGE_RE = re.compile(r"^openproject://work_packages/[0-9]+$")
LINKED_RECORD_REF_RE = re.compile(r"^(openproject://work_packages/[0-9]+|repo://.+|record://.+)$")
DESIGN_BASELINE_REF_RE = re.compile(
    r"^record://design-baselines/([a-z0-9]+(?:-[a-z0-9]+)*)$"
)
DELIVERY_PACKET_REF_RE = re.compile(
    r"^record://delivery-packets/([a-z0-9]+(?:-[a-z0-9]+)*)$"
)


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def require_value(errors: list[str], label: str, payload: dict, key: str) -> None:
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{label}: missing {key}")


def validate_registry(repo_root: Path, errors: list[str]) -> dict[str, dict]:
    registry_path = repo_root / "prototypes.yaml"
    if not registry_path.exists():
        errors.append("missing prototypes.yaml")
        return {}

    registry = load_yaml(registry_path)
    schema_path = repo_root / "schemas/prototype-registry.schema.json"
    if not schema_path.exists():
        errors.append("missing schemas/prototype-registry.schema.json")
    else:
        schema = load_json(schema_path)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for schema_error in sorted(
            validator.iter_errors(registry),
            key=lambda item: list(item.absolute_path),
        ):
            errors.append(
                f"prototypes.yaml: {schema_error_path(schema_error)}: "
                f"{schema_error.message}"
            )
    if registry.get("schema_version") != 1:
        errors.append("prototypes.yaml: schema_version must be 1")

    prototypes = registry.get("prototypes")
    if not isinstance(prototypes, list) or not prototypes:
        errors.append("prototypes.yaml: prototypes must be a non-empty list")
        return {}

    seen_ids: set[str] = set()
    prototypes_by_id: dict[str, dict] = {}
    for index, prototype in enumerate(prototypes):
        label = f"prototypes[{index}]"
        if not isinstance(prototype, dict):
            errors.append(f"{label}: must be an object")
            continue

        for key in (
            "id",
            "name",
            "portfolio",
            "lifecycle",
            "owner",
            "visibility_tier",
            "data_mode",
            "mutation_boundary",
            "paths",
        ):
            require_value(errors, label, prototype, key)

        prototype_id = str(prototype.get("id") or "")
        if not PROTOTYPE_ID_RE.match(prototype_id):
            errors.append(f"{label}: id must be kebab-case")
        if prototype_id in seen_ids:
            errors.append(f"{label}: duplicate id {prototype_id}")
        seen_ids.add(prototype_id)
        if prototype_id:
            prototypes_by_id[prototype_id] = prototype

        if prototype.get("portfolio") not in PORTFOLIOS:
            errors.append(f"{label}: invalid portfolio {prototype.get('portfolio')!r}")
        if prototype.get("lifecycle") not in LIFECYCLES:
            errors.append(f"{label}: invalid lifecycle {prototype.get('lifecycle')!r}")
        if prototype.get("visibility_tier") not in VISIBILITY_TIERS:
            errors.append(
                f"{label}: invalid visibility_tier {prototype.get('visibility_tier')!r}"
            )
        if prototype.get("data_mode") not in DATA_MODES:
            errors.append(f"{label}: invalid data_mode {prototype.get('data_mode')!r}")
        if prototype.get("mutation_boundary") not in MUTATION_BOUNDARIES:
            errors.append(
                f"{label}: invalid mutation_boundary {prototype.get('mutation_boundary')!r}"
            )
        if "delivery_refs" in prototype:
            errors.append(f"{label}: delivery_refs is retired; use typed linked_records")

        linked_records = prototype.get("linked_records") or []
        if linked_records and not isinstance(linked_records, list):
            errors.append(f"{label}: linked_records must be a list")
        elif isinstance(linked_records, list):
            for record_index, record in enumerate(linked_records):
                record_label = f"{label}.linked_records[{record_index}]"
                if not isinstance(record, dict):
                    errors.append(f"{record_label}: must be an object")
                    continue
                for key in ("role", "ref", "system", "level", "label"):
                    require_value(errors, record_label, record, key)
                if record.get("role") not in LINKED_RECORD_ROLES:
                    errors.append(f"{record_label}: invalid role {record.get('role')!r}")
                if record.get("system") not in LINKED_RECORD_SYSTEMS:
                    errors.append(f"{record_label}: invalid system {record.get('system')!r}")
                if record.get("level") not in LINKED_RECORD_LEVELS:
                    errors.append(f"{record_label}: invalid level {record.get('level')!r}")
                record_ref = str(record.get("ref") or "")
                if not LINKED_RECORD_REF_RE.match(record_ref):
                    errors.append(f"{record_label}: invalid ref {record_ref!r}")
                parent_ref = record.get("parent_ref")
                if parent_ref and not OPENPROJECT_WORK_PACKAGE_RE.match(str(parent_ref)):
                    errors.append(f"{record_label}: invalid parent_ref {parent_ref!r}")

        paths = prototype.get("paths") or {}
        if not isinstance(paths, dict):
            errors.append(f"{label}: paths must be an object")
            continue
        for path_key in ("brief", "backlog", "design_profile", "change_log", "decision_log"):
            relative_path = paths.get(path_key)
            if not relative_path:
                errors.append(f"{label}: missing paths.{path_key}")
                continue
            if not (repo_root / relative_path).exists():
                errors.append(f"{label}: missing file for paths.{path_key}: {relative_path}")

        security_refs = prototype.get("security_review_refs") or []
        risky_visibility = prototype.get("visibility_tier") in {"client-review", "public-demo"}
        risky_data = prototype.get("data_mode") in {"real-readonly", "real-mutable"}
        risky_mutation = prototype.get("mutation_boundary") in {
            "external-sandbox",
            "real-system",
        }
        if (risky_visibility or risky_data or risky_mutation) and not security_refs:
            errors.append(
                f"{label}: security_review_refs required for client-visible, real-data, or external/real mutation prototypes"
            )

        lifecycle = prototype.get("lifecycle")
        if lifecycle in {"baseline-approved", "graduating", "graduated"} and not prototype.get(
            "design_baseline_ref"
        ):
            errors.append(f"{label}: design_baseline_ref required for lifecycle {lifecycle}")
        if lifecycle == "graduating":
            packet_ref = prototype.get("delivery_packet_ref")
            if not packet_ref:
                errors.append(f"{label}: delivery_packet_ref required for lifecycle graduating")
            elif not DELIVERY_PACKET_REF_RE.match(str(packet_ref)):
                errors.append(f"{label}: invalid delivery_packet_ref {packet_ref!r}")
            linked_packets = [
                record
                for record in linked_records
                if isinstance(record, dict)
                and record.get("role") == "delivery-packet"
                and record.get("ref") == packet_ref
            ]
            if not linked_packets:
                errors.append(
                    f"{label}: linked_records must include active delivery_packet_ref"
                )
        if lifecycle == "graduated" and not prototype.get("graduation_ref"):
            errors.append(f"{label}: graduation_ref required for lifecycle graduated")
        if lifecycle == "retired" and not prototype.get("retirement_ref"):
            errors.append(f"{label}: retirement_ref required for retired prototypes")

    return prototypes_by_id


def schema_error_path(error) -> str:
    if not error.absolute_path:
        return "<root>"
    return ".".join(str(part) for part in error.absolute_path)


def validate_design_baseline_records(
    repo_root: Path,
    prototypes_by_id: dict[str, dict],
    errors: list[str],
) -> None:
    relative_dir = "records/design-baselines"
    record_dir = repo_root / relative_dir
    if not record_dir.exists():
        errors.append(f"missing record directory: {relative_dir}")
        return

    schema_path = repo_root / "schemas/design-baseline.schema.json"
    if not schema_path.exists():
        errors.append("missing schemas/design-baseline.schema.json")
        return

    schema = load_json(schema_path)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    records_by_id: dict[str, dict] = {}

    for path in sorted(record_dir.glob("*.yaml")):
        relative_path = path.relative_to(repo_root)
        payload = load_yaml(path)
        for schema_error in sorted(
            validator.iter_errors(payload),
            key=lambda item: list(item.absolute_path),
        ):
            errors.append(
                f"{relative_path}: {schema_error_path(schema_error)}: "
                f"{schema_error.message}"
            )

        baseline_id = payload.get("baseline_id")
        prototype_id = payload.get("prototype_id")
        if isinstance(baseline_id, str):
            if path.stem != baseline_id:
                errors.append(
                    f"{relative_path}: filename must match baseline_id {baseline_id!r}"
                )
            if baseline_id in records_by_id:
                errors.append(f"{relative_path}: duplicate baseline_id {baseline_id!r}")
            records_by_id[baseline_id] = payload
        if isinstance(prototype_id, str) and prototype_id not in prototypes_by_id:
            errors.append(
                f"{relative_path}: unknown prototype_id {prototype_id!r}"
            )

    for prototype_id, prototype in prototypes_by_id.items():
        lifecycle = prototype.get("lifecycle")
        if lifecycle not in {"baseline-approved", "graduating", "graduated"}:
            continue

        baseline_ref = prototype.get("design_baseline_ref")
        match = (
            DESIGN_BASELINE_REF_RE.match(str(baseline_ref))
            if baseline_ref
            else None
        )
        if not match:
            errors.append(
                f"prototype {prototype_id}: design_baseline_ref must use "
                "record://design-baselines/<baseline-id>"
            )
            continue

        baseline_id = match.group(1)
        baseline = records_by_id.get(baseline_id)
        if baseline is None:
            errors.append(
                f"prototype {prototype_id}: design_baseline_ref does not resolve "
                f"to records/design-baselines/{baseline_id}.yaml"
            )
            continue
        if baseline.get("prototype_id") != prototype_id:
            errors.append(
                f"prototype {prototype_id}: baseline {baseline_id} belongs to "
                f"{baseline.get('prototype_id')!r}"
            )
        if baseline.get("decision") != "approved":
            errors.append(
                f"prototype {prototype_id}: active design baseline decision must be approved"
            )

        registry_security_refs = set(prototype.get("security_review_refs") or [])
        baseline_security_refs = set(baseline.get("security_review_refs") or [])
        risky_visibility = prototype.get("visibility_tier") in {
            "client-review",
            "public-demo",
        }
        risky_data = prototype.get("data_mode") in {
            "real-readonly",
            "real-mutable",
        }
        risky_mutation = prototype.get("mutation_boundary") in {
            "external-sandbox",
            "real-system",
        }
        if (
            risky_visibility or risky_data or risky_mutation
        ) and not baseline_security_refs:
            errors.append(
                f"prototype {prototype_id}: approved baseline must bind security_review_refs"
            )
        missing_security_refs = registry_security_refs - baseline_security_refs
        if missing_security_refs:
            errors.append(
                f"prototype {prototype_id}: baseline {baseline_id} is missing "
                f"registry security refs {sorted(missing_security_refs)!r}"
            )

        linked_baselines = [
            record
            for record in prototype.get("linked_records") or []
            if isinstance(record, dict)
            and record.get("role") == "baseline-record"
            and record.get("ref") == baseline_ref
        ]
        if not linked_baselines:
            errors.append(
                f"prototype {prototype_id}: linked_records must include the active "
                f"baseline ref {baseline_ref}"
            )


def validate_other_records(repo_root: Path, errors: list[str]) -> None:
    record_dirs = {
        "records/graduations": "prototype_id",
        "records/retirements": "prototype_id",
    }
    for relative_dir, required_key in record_dirs.items():
        record_dir = repo_root / relative_dir
        if not record_dir.exists():
            errors.append(f"missing record directory: {relative_dir}")
            continue
        for path in sorted(record_dir.glob("*.yaml")):
            payload = load_yaml(path)
            if payload.get("schema_version") != 1:
                errors.append(f"{path.relative_to(repo_root)}: schema_version must be 1")
            if not payload.get(required_key):
                errors.append(f"{path.relative_to(repo_root)}: missing {required_key}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()

    errors: list[str] = []
    prototypes_by_id = validate_registry(repo_root, errors)
    validate_design_baseline_records(repo_root, prototypes_by_id, errors)
    validate_other_records(repo_root, errors)
    try:
        validate_packet_records(repo_root)
    except PacketError as error:
        errors.append(f"Prototype Delivery packets: {error.code}: {error}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("prototype studio valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
