from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from packages.prototype_delivery_packet.contract import PacketError, content_digest
from packages.prototype_landing.landing import SECRET_NAMES, SECRET_SUFFIXES


MAX_FILES = 500
MAX_BYTES = 5 * 1024 * 1024
MAX_FILE_BYTES = 1024 * 1024
REVISION = re.compile(r"^[0-9a-f]{40}$")
PROTOTYPE = re.compile(r"^prototype:([a-z0-9]+(?:-[a-z0-9]+)*)$")


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise PacketError(code, message)


def _git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    _require(result.returncode == 0, "source_unavailable", "Committed owner source is unavailable")
    return result.stdout


def _blob(root: Path, revision: str, path: str, *, optional: bool = False) -> bytes | None:
    target = f"{revision}:{path}"
    probe = subprocess.run(["git", "cat-file", "-e", target], cwd=root, capture_output=True)
    if probe.returncode and optional:
        return None
    _require(probe.returncode == 0, "source_unavailable", "Required committed owner file is absent")
    _require(int(_git(root, "cat-file", "-s", target)) <= MAX_FILE_BYTES,
             "source_bounds_exceeded", "Owner file exceeds the source bound")
    return _git(root, "show", target)


def _document(root: Path, revision: str, path: str, *, optional: bool = False) -> dict | None:
    raw = _blob(root, revision, path, optional=optional)
    if raw is None:
        return None
    try:
        value = yaml.safe_load(raw)
    except (ValueError, yaml.YAMLError) as error:
        raise PacketError("source_record_invalid", "Committed owner document is invalid") from error
    _require(isinstance(value, dict), "source_record_invalid", "Owner document must be an object")
    return value


def _schema(root: Path, name: str, value: dict) -> None:
    schema = json.loads((root / "schemas" / name).read_text())
    Draft202012Validator.check_schema(schema)
    _require(Draft202012Validator(schema).is_valid(value),
             "authoring_contract_invalid", "Owner preparation failed its closed contract")


def _file_manifest(root: Path, revision: str, source_root: str) -> list[dict[str, Any]]:
    rows = _git(root, "ls-tree", "-r", "-z", revision, "--", source_root).split(b"\0")
    entries, total = [], 0
    for row in filter(None, rows):
        metadata, name = row.split(b"\t", 1)
        mode, kind, _object_id = metadata.split()
        path = name.decode("utf-8")
        parts = PurePosixPath(path).parts
        _require(mode in {b"100644", b"100755"} and kind == b"blob"
                 and re.fullmatch(r"[A-Za-z0-9._/-]{1,512}", path) is not None
                 and path.startswith(source_root + "/")
                 and all(not part.startswith(".") for part in parts)
                 and PurePosixPath(path).name not in SECRET_NAMES
                 and PurePosixPath(path).suffix.lower() not in SECRET_SUFFIXES,
                 "source_scope_denied", "Prototype context requires bounded regular non-secret source files")
        raw = _blob(root, revision, path)
        total += len(raw)
        _require(len(entries) < MAX_FILES and total <= MAX_BYTES,
                 "source_bounds_exceeded", "Prototype context exceeds the source bound")
        entries.append({"path": path, "content_digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                        "bytes": len(raw)})
    _require(bool(entries), "source_unavailable", "Prototype source has not been landed")
    return entries


def inspect_source(repo_root: Path, prototype_id: str, source_revision: str) -> dict[str, Any]:
    """Describe one exact committed source scope. Never mutate or authorize it."""
    root = repo_root.resolve()
    match = PROTOTYPE.fullmatch(prototype_id) if isinstance(prototype_id, str) else None
    _require(match is not None and len(prototype_id) <= 256, "prototype_identity_invalid", "Prototype identity is invalid")
    _require(isinstance(source_revision, str) and REVISION.fullmatch(source_revision) is not None,
             "source_revision_invalid", "Owner preparation requires an exact Git revision")
    _require(_git(root, "rev-parse", "HEAD").decode().strip() == source_revision,
             "source_revision_stale", "Owner checkout no longer matches the selected source revision")
    _require(not _git(root, "status", "--porcelain", "--untracked-files=normal").strip(),
             "dirty_worktree", "Owner preparation requires a clean committed source checkout")
    registry = _document(root, source_revision, "prototypes.yaml")
    _schema(root, "prototype-registry.schema.json", registry)
    slug = match.group(1)
    entries = [item for item in registry["prototypes"] if item["id"] == slug]
    _require(len(entries) == 1, "prototype_unknown", "Prototype identity is absent or ambiguous")
    entry = entries[0]
    _require(entry.get("project_phase", "incubating") == "incubating"
             and entry["lifecycle"] in {"exploring", "candidate", "baseline-approved"},
             "prototype_source_ineligible", "Prototype source custody is no longer in incubation")
    landing = _document(root, source_revision, f"records/prototype-landings/{slug}/record.json", optional=True)
    _require(landing is None or isinstance(landing.get("source"), dict),
             "source_record_invalid", "Landing source custody must be explicit")
    declared = entry.get("source_custody")
    landed = (landing or {}).get("source", {}).get("custody")
    _require(declared == "incubation-repo" or landed == "incubation-repo",
             "source_custody_unsupported", "This Studio producer requires explicit incubation custody")
    _require(all(value in (None, "incubation-repo") for value in (declared, landed)),
             "source_custody_unsupported", "Prototype source custody declarations conflict")
    source_root = f"prototypes/{slug}"
    if landing:
        _require(landing.get("id") == prototype_id
                 and landing["source"].get("ref") == f"repo://workspace-prototype-studio/{source_root}",
                 "source_custody_unsupported", "Landing does not bind this Studio source")
    design = f"docs/prototypes/{slug}/design-profile.md"
    _require(isinstance(entry["paths"], dict) and entry["paths"].get("design_profile") == design,
             "source_scope_denied", "Design source must stay inside the selected Prototype")
    design_raw = _blob(root, source_revision, design)
    return {
        "schema_version": 1, "status": "source-inspected",
        "subject": {"kind": "prototype", "prototype_id": prototype_id,
                    "registry_ref": f"record://prototypes/{slug}", "registry_revision": source_revision,
                    "source_ref": f"repo://workspace-prototype-studio/{source_root}",
                    "source_revision": source_revision},
        "prototype": entry,
        "model_source_scope": {"source_root": source_root, "design_profile": design},
        "source_manifest": _file_manifest(root, source_revision, source_root),
        "design_profile_digest": "sha256:" + hashlib.sha256(design_raw).hexdigest(),
        "delivery_packet_preparation": {
            "baseline_required": True, "readiness_evaluated": False,
            "lifecycle_allows_preparation": entry["lifecycle"] == "baseline-approved",
            "request_schema": "schemas/prototype-delivery-request.schema.json",
            "owner_command": "scripts/prototype_delivery_packet.py",
        },
        "authority": {"may_apply_source": False, "may_invoke_model": False,
                      "may_approve_baseline": False, "may_activate_runtime": False},
    }


def plan_preview(repo_root: Path, request: dict[str, Any]) -> dict[str, Any]:
    """Render a deterministic owner file plan; the source executor owns apply."""
    root = repo_root.resolve()
    _schema(root, "prototype-preview-preparation-request.schema.json", request)
    inspected = inspect_source(root, request["prototype_id"], request["source_revision"])
    entry = inspected["prototype"]
    slug = entry["id"]
    boundary = entry["mutation_boundary"]
    _require(boundary in {"none", "prototype-local"}
             and entry["data_mode"] in {"mock", "synthetic"}
             and entry["visibility_tier"] in {"private-internal", "operator-review"},
             "preview_boundary_unsupported", "Preview preparation supports only internal synthetic static review")
    profile_id = slug if re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", slug) else "prototype-" + hashlib.sha256(slug.encode()).hexdigest()[:16]
    profile = {
        "schema_version": 1, "profile_id": profile_id, "prototype_id": request["prototype_id"],
        "status": "active" if request["runtime_activation"] else "draft",
        "support_profile": request["support_profile"], "preview_mode": "static",
        "runtime_activation": request["runtime_activation"],
        "runtime": {"bind_host": "127.0.0.1", "port": request["port"],
                    "source_root": inspected["model_source_scope"]["source_root"], "health_path": "/__preview/health"},
        "boundary": {"visibility_tier": entry["visibility_tier"], "data_mode": entry["data_mode"],
                     "mutation_boundary": boundary,
                     "persistence_model": "browser-local" if boundary == "prototype-local" else "runtime-metadata-only",
                     "public_ingress": False, "external_network": False},
        "lifecycle": {"cleanup_owner": "Workspace Prototype Studio", "ttl_seconds": request["ttl_seconds"],
                      "retirement_rule": "Stop on owner request or retirement; browser-origin data requires explicit separate cleanup.",
                      "promotion_path": "Use approved Baseline and the existing Delivery packet before durable owner graduation."},
    }
    _schema(root, "prototype-preview-profile.schema.json", profile)
    path = f"records/prototype-preview-profiles/{slug}.yaml"
    others = _git(root, "ls-tree", "-r", "--name-only", request["source_revision"],
                  "--", "records/prototype-preview-profiles").decode().splitlines()
    for other in others:
        if other != path and re.fullmatch(r"records/prototype-preview-profiles/[a-z0-9-]+\.yaml", other):
            configured = _document(root, request["source_revision"], other)
            _require(not (configured.get("status") == "active" and configured.get("runtime_activation") is True
                          and isinstance(configured.get("runtime"), dict)
                          and configured["runtime"].get("port") == request["port"]),
                     "preview_port_conflict", "The selected port belongs to another committed Preview profile")
    prior = _blob(root, request["source_revision"], path, optional=True)
    body = {
        "schema_version": 1, "status": "preparation-only", "subject": inspected["subject"],
        "request_digest": content_digest(request), "operator": request["operator"],
        "changes": [{"operation": "write", "path": path,
                     "expected_content_digest": None if prior is None else "sha256:" + hashlib.sha256(prior).hexdigest(),
                     "content": yaml.safe_dump(profile, sort_keys=False)}],
        "authority": inspected["authority"],
    }
    return {**body, "plan_digest": content_digest(body)}
