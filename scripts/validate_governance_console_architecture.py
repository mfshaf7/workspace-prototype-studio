#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def require_mapping(errors: list[str], payload: dict, key: str) -> dict:
    value = payload.get(key)
    if not isinstance(value, dict) or not value:
        errors.append(f"{key}: must be a non-empty mapping")
        return {}
    return value


def require_known(
    errors: list[str],
    label: str,
    value: object,
    allowed: set[str],
) -> None:
    if value not in allowed:
        errors.append(f"{label}: invalid value {value!r}")


def validate_ids(errors: list[str], label: str, values: dict) -> None:
    for value_id in values:
        if not ID_RE.fullmatch(str(value_id)):
            errors.append(f"{label}: invalid kebab-case id {value_id!r}")


def normalize_projection_label(value: object) -> str:
    return " ".join(str(value).split()).casefold()


def markdown_table_rows(path: Path) -> dict[str, list[list[str]]]:
    rows: dict[str, list[list[str]]] = {}

    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2 or all(set(cell) <= {"-", ":"} for cell in cells):
            continue
        rows.setdefault(normalize_projection_label(cells[0]), []).append(cells[1:])

    return rows


def validate_implementation_projection(
    errors: list[str],
    *,
    entities: dict,
    path: Path,
    projection_label: str,
    status_offset: int,
) -> None:
    if not path.exists():
        return

    rows = markdown_table_rows(path)
    for entity_id, entity in entities.items():
        if not isinstance(entity, dict):
            continue
        label = entity.get("label")
        implementation = entity.get("implementation") or {}
        expected = [
            implementation.get("console"),
            implementation.get("backend_support"),
            implementation.get("live_adapter"),
        ]
        matches = rows.get(normalize_projection_label(label), [])

        if len(matches) != 1:
            errors.append(
                f"{projection_label}: expected exactly one row for "
                f"{entity_id!r} ({label!r}), found {len(matches)}"
            )
            continue

        actual = matches[0][status_offset : status_offset + 3]
        if actual != expected:
            errors.append(
                f"{projection_label}: {entity_id!r} status {actual!r} "
                f"does not match system-model.yaml {expected!r}"
            )


def validate_model(model_path: Path) -> list[str]:
    errors: list[str] = []
    model = load_yaml(model_path)
    console_docs_dir = model_path.parent.parent
    legacy_diagram_path = console_docs_dir / "architecture-diagrams.md"

    if legacy_diagram_path.exists():
        errors.append(
            "legacy architecture-diagrams.md must remain retired; "
            "use architecture/system-model.yaml and registered views"
        )

    if model.get("schema_version") != 1:
        errors.append("schema_version must be 1")

    system = require_mapping(errors, model, "system")
    vocabularies = require_mapping(errors, model, "vocabularies")
    authorities = require_mapping(errors, model, "authorities")
    capabilities = require_mapping(errors, model, "capabilities")
    transitions = require_mapping(errors, model, "transitions")
    state_families = require_mapping(errors, model, "state_families")
    views = require_mapping(errors, model, "views")

    validate_ids(errors, "authorities", authorities)
    validate_ids(errors, "capabilities", capabilities)
    validate_ids(errors, "transitions", transitions)
    validate_ids(errors, "state_families", state_families)
    validate_ids(errors, "views", views)

    if system.get("id") != "governance-operations-console":
        errors.append("system.id must be governance-operations-console")

    design_statuses = set(vocabularies.get("design_status") or [])
    console_statuses = set(vocabularies.get("console_implementation") or [])
    backend_statuses = set(vocabularies.get("backend_support") or [])
    adapter_statuses = set(vocabularies.get("adapter_status") or [])
    delivery_phases = set(vocabularies.get("delivery_phase") or [])

    authority_ids = set(authorities)
    capability_ids = set(capabilities)
    transition_ids = set(transitions)

    if "workspace-product-intake" in capability_ids:
        errors.append(
            "capabilities.workspace-product-intake: obsolete standalone domain "
            "must remain absent"
        )

    required_intake_capabilities = {
        "workspace-intake": {
            "kind": "authority-workflow",
            "canonical_records": {
                "workspace-governance/contracts/intake-register.yaml",
            },
        },
        "workspace-active-inventory": {
            "kind": "canonical-registry",
            "canonical_records": {
                "workspace-governance/contracts/repos.yaml",
                "workspace-governance/contracts/products.yaml",
                "workspace-governance/contracts/components.yaml",
            },
        },
    }
    for capability_id, expected in required_intake_capabilities.items():
        capability = capabilities.get(capability_id)
        if not isinstance(capability, dict):
            errors.append(f"capabilities.{capability_id}: required")
            continue
        if capability.get("kind") != expected["kind"]:
            errors.append(
                f"capabilities.{capability_id}.kind: must be "
                f"{expected['kind']!r}"
            )
        if set(capability.get("canonical_records") or []) != expected[
            "canonical_records"
        ]:
            errors.append(
                f"capabilities.{capability_id}.canonical_records: must be "
                f"{sorted(expected['canonical_records'])!r}"
            )

    intake_visibility = capabilities.get("workspace-intake", {}).get(
        "operator_visibility", ""
    )
    if "No standalone Operation Workbench domain is required." not in str(
        intake_visibility
    ):
        errors.append(
            "capabilities.workspace-intake.operator_visibility: must prohibit "
            "a standalone Operation Workbench domain"
        )

    required_intake_transitions = {
        "repository-to-workspace-intake": ("repository", "workspace-intake"),
        "prototype-to-workspace-intake": ("prototype", "workspace-intake"),
        "delivery-to-workspace-intake": ("delivery", "workspace-intake"),
        "workspace-intake-to-active-inventory": (
            "workspace-intake",
            "workspace-active-inventory",
        ),
        "active-product-to-portfolio": (
            "workspace-active-inventory",
            "portfolio",
        ),
    }
    for transition_id, (source, target) in required_intake_transitions.items():
        transition = transitions.get(transition_id)
        if not isinstance(transition, dict):
            errors.append(f"transitions.{transition_id}: required")
            continue
        if transition.get("source") != source:
            errors.append(
                f"transitions.{transition_id}.source: must be {source!r}"
            )
        if transition.get("target") != target:
            errors.append(
                f"transitions.{transition_id}.target: must be {target!r}"
            )

    for obsolete_transition in {
        "delivery-to-product-intake",
        "product-intake-to-portfolio",
        "repository-request-admission",
    }:
        if obsolete_transition in transition_ids:
            errors.append(
                f"transitions.{obsolete_transition}: obsolete transition must "
                "remain absent"
            )

    for authority_id, authority in authorities.items():
        if not isinstance(authority, dict):
            errors.append(f"authorities.{authority_id}: must be a mapping")
            continue
        implementation = authority.get("implementation") or {}
        require_known(
            errors,
            f"authorities.{authority_id}.implementation.backend_support",
            implementation.get("backend_support"),
            backend_statuses,
        )
        require_known(
            errors,
            f"authorities.{authority_id}.implementation.delivery_phase",
            implementation.get("delivery_phase"),
            delivery_phases,
        )

    for capability_id, capability in capabilities.items():
        if not isinstance(capability, dict):
            errors.append(f"capabilities.{capability_id}: must be a mapping")
            continue
        require_known(
            errors,
            f"capabilities.{capability_id}.design_status",
            capability.get("design_status"),
            design_statuses,
        )
        for authority_ref in capability.get("authority_refs") or []:
            if authority_ref not in authority_ids:
                errors.append(
                    f"capabilities.{capability_id}.authority_refs: unknown {authority_ref!r}"
                )
        implementation = capability.get("implementation") or {}
        require_known(
            errors,
            f"capabilities.{capability_id}.implementation.console",
            implementation.get("console"),
            console_statuses,
        )
        require_known(
            errors,
            f"capabilities.{capability_id}.implementation.backend_support",
            implementation.get("backend_support"),
            backend_statuses,
        )
        require_known(
            errors,
            f"capabilities.{capability_id}.implementation.live_adapter",
            implementation.get("live_adapter"),
            adapter_statuses,
        )
        require_known(
            errors,
            f"capabilities.{capability_id}.implementation.delivery_phase",
            implementation.get("delivery_phase"),
            delivery_phases,
        )

    owner_fields = {
        "validation_owner",
        "admission_owner",
        "execution_owner",
        "mutation_owner",
        "receipt_owner",
    }
    for transition_id, transition in transitions.items():
        if not isinstance(transition, dict):
            errors.append(f"transitions.{transition_id}: must be a mapping")
            continue
        for endpoint in ("source", "target"):
            if transition.get(endpoint) not in capability_ids:
                errors.append(
                    f"transitions.{transition_id}.{endpoint}: unknown capability "
                    f"{transition.get(endpoint)!r}"
                )
        for owner_field in owner_fields:
            if transition.get(owner_field) not in authority_ids:
                errors.append(
                    f"transitions.{transition_id}.{owner_field}: unknown authority "
                    f"{transition.get(owner_field)!r}"
                )
        require_known(
            errors,
            f"transitions.{transition_id}.design_status",
            transition.get("design_status"),
            design_statuses,
        )
        implementation = transition.get("implementation") or {}
        require_known(
            errors,
            f"transitions.{transition_id}.implementation.console",
            implementation.get("console"),
            console_statuses,
        )
        require_known(
            errors,
            f"transitions.{transition_id}.implementation.backend_support",
            implementation.get("backend_support"),
            backend_statuses,
        )
        require_known(
            errors,
            f"transitions.{transition_id}.implementation.live_adapter",
            implementation.get("live_adapter"),
            adapter_statuses,
        )
        require_known(
            errors,
            f"transitions.{transition_id}.implementation.delivery_phase",
            implementation.get("delivery_phase"),
            delivery_phases,
        )

    for family_id, family in state_families.items():
        if not isinstance(family, dict):
            errors.append(f"state_families.{family_id}: must be a mapping")
            continue
        owner = family.get("owner")
        if (
            owner not in authority_ids
            and owner not in capability_ids
            and owner != "source-authority"
        ):
            errors.append(f"state_families.{family_id}.owner: unknown {owner!r}")
        values = family.get("values")
        if not isinstance(values, list) or not values:
            errors.append(f"state_families.{family_id}.values: must be a non-empty list")
        elif len(values) != len(set(values)):
            errors.append(f"state_families.{family_id}.values: contains duplicates")

    workspace_intake_values = state_families.get("workspace-intake", {}).get(
        "values"
    )
    if workspace_intake_values != ["out-of-scope", "proposed", "admitted"]:
        errors.append(
            "state_families.workspace-intake.values: must remain "
            "['out-of-scope', 'proposed', 'admitted']"
        )

    architecture_dir = model_path.parent
    covered_authorities: set[str] = set()
    covered_capabilities: set[str] = set()
    covered_transitions: set[str] = set()

    for view_id, view in views.items():
        if not isinstance(view, dict):
            errors.append(f"views.{view_id}: must be a mapping")
            continue
        output = view.get("output")
        if not isinstance(output, str) or not output:
            errors.append(f"views.{view_id}.output: required")
        else:
            output_path = architecture_dir / output
            if not output_path.exists():
                errors.append(f"views.{view_id}.output: missing {output}")
            elif "system-model.yaml" not in output_path.read_text(encoding="utf-8"):
                errors.append(
                    f"views.{view_id}.output: must identify system-model.yaml as its source"
                )

        for ref in view.get("authority_refs") or []:
            if ref not in authority_ids:
                errors.append(f"views.{view_id}.authority_refs: unknown {ref!r}")
            covered_authorities.add(ref)
        for ref in view.get("capability_refs") or []:
            if ref not in capability_ids:
                errors.append(f"views.{view_id}.capability_refs: unknown {ref!r}")
            covered_capabilities.add(ref)
        for ref in view.get("transition_refs") or []:
            if ref not in transition_ids:
                errors.append(f"views.{view_id}.transition_refs: unknown {ref!r}")
            covered_transitions.add(ref)

    for missing in sorted(authority_ids - covered_authorities):
        errors.append(f"view coverage: authority {missing!r} is not covered")
    for missing in sorted(capability_ids - covered_capabilities):
        errors.append(f"view coverage: capability {missing!r} is not covered")
    for missing in sorted(transition_ids - covered_transitions):
        errors.append(f"view coverage: transition {missing!r} is not covered")

    required_view_terms = {
        "views/01-system-context.md": [
            "Operation Workbench<br/>7 operation domains",
        ],
        "views/02-operator-surfaces.md": [
            "No standalone Product Intake operation",
        ],
        "views/04-lifecycle.md": [
            "Workspace Intake classification",
            "Active inventory promotion",
        ],
        "views/05-handoffs.md": [
            "Classification and promotion are separate workflows and receipts.",
            "Workspace Intake classification",
            "Active inventory promotion",
        ],
    }
    for output, terms in required_view_terms.items():
        output_path = architecture_dir / output
        if not output_path.exists():
            continue
        source = output_path.read_text(encoding="utf-8")
        for term in terms:
            if term not in source:
                errors.append(
                    f"{output}: missing Workspace Intake architecture term {term!r}"
                )

    validate_implementation_projection(
        errors,
        entities=capabilities,
        path=architecture_dir / "views/07-capability-maturity.md",
        projection_label="views/07-capability-maturity.md capabilities",
        status_offset=0,
    )
    validate_implementation_projection(
        errors,
        entities=transitions,
        path=architecture_dir / "views/07-capability-maturity.md",
        projection_label="views/07-capability-maturity.md transitions",
        status_offset=0,
    )
    validate_implementation_projection(
        errors,
        entities=transitions,
        path=architecture_dir / "views/05-handoffs.md",
        projection_label="views/05-handoffs.md transitions",
        status_offset=1,
    )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(
            "docs/prototypes/governance-operations-console/architecture/system-model.yaml"
        ),
    )
    args = parser.parse_args()
    model_path = args.model.resolve()

    if not model_path.exists():
        print(f"ERROR: missing architecture model: {model_path}")
        return 1

    errors = validate_model(model_path)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("governance console architecture valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
