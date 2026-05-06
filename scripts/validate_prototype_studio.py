#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


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
PROTOTYPE_ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def require_value(errors: list[str], label: str, payload: dict, key: str) -> None:
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        errors.append(f"{label}: missing {key}")


def validate_registry(repo_root: Path, errors: list[str]) -> None:
    registry_path = repo_root / "prototypes.yaml"
    if not registry_path.exists():
        errors.append("missing prototypes.yaml")
        return

    registry = load_yaml(registry_path)
    if registry.get("schema_version") != 1:
        errors.append("prototypes.yaml: schema_version must be 1")

    prototypes = registry.get("prototypes")
    if not isinstance(prototypes, list) or not prototypes:
        errors.append("prototypes.yaml: prototypes must be a non-empty list")
        return

    seen_ids: set[str] = set()
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

        paths = prototype.get("paths") or {}
        if not isinstance(paths, dict):
            errors.append(f"{label}: paths must be an object")
            continue
        for path_key in ("brief", "backlog", "change_log", "decision_log"):
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
        if lifecycle in {"graduating", "graduated"} and not prototype.get("graduation_ref"):
            errors.append(f"{label}: graduation_ref required for lifecycle {lifecycle}")
        if lifecycle == "retired" and not prototype.get("retirement_ref"):
            errors.append(f"{label}: retirement_ref required for retired prototypes")


def validate_records(repo_root: Path, errors: list[str]) -> None:
    record_dirs = {
        "records/design-baselines": "prototype_id",
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
    validate_registry(repo_root, errors)
    validate_records(repo_root, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("prototype studio valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

