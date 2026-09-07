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


CONTRACT_DIR = Path("contracts/prototype-landing")
LANDING_RECORD_DIR = Path("records/prototype-landings")
SCHEMA_BY_TYPE = {
    "prototype-entry-packet": "prototype-landing-entry-packet.schema.json",
    "prototype-landing-request": "prototype-landing-request.schema.json",
    "prototype-landing-plan": "prototype-landing-plan.schema.json",
    "prototype-landing-readiness": "prototype-landing-readiness.schema.json",
    "prototype-landing-apply": "prototype-landing-apply.schema.json",
    "prototype-landing-readback": "prototype-landing-readback.schema.json",
    "prototype-landing-receipt": "prototype-landing-receipt.schema.json",
}
DIGEST_FIELD_BY_TYPE = {
    "prototype-entry-packet": "packet_digest",
    "prototype-landing-request": "request_digest",
    "prototype-landing-plan": "plan_digest",
    "prototype-landing-readiness": "readiness_digest",
    "prototype-landing-apply": "apply_digest",
    "prototype-landing-readback": "readback_digest",
    "prototype-landing-receipt": "receipt_digest",
}
SUPPORT_DIMENSIONS = {
    "source",
    "studio-home",
    "interface",
    "runtime",
    "data",
    "integration",
    "tooling",
    "evidence",
    "visibility",
    "recovery",
}
CUSTODY_BY_POSTURE = {
    "create-studio-source": "incubation-repo",
    "use-existing-studio-source": "incubation-repo",
    "reference-dedicated-owner-source": "dedicated-owner-repo",
    "reference-shared-owner-source": "shared-owner-repo",
    "import-to-studio": "incubation-repo",
}
REFERENCE_ONLY_POSTURES = {
    "reference-dedicated-owner-source",
    "reference-shared-owner-source",
}
VISIBILITY_MAP = {
    "private": "private-internal",
    "operator-review": "operator-review",
    "client-review": "client-review",
    "public-demo": "public-demo",
}
MUTATION_MAP = {
    "none": "none",
    "local-only": "prototype-local",
    "sandbox": "external-sandbox",
    "real-system-blocked": "real-system",
}
SECRET_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    "credentials",
    "credentials.json",
    "id_rsa",
    "id_ed25519",
}
SECRET_SUFFIXES = {".key", ".pem", ".p12", ".pfx"}
SECRET_MARKERS = (
    b"-----BEGIN PRIVATE KEY-----",
    b"-----BEGIN RSA PRIVATE KEY-----",
    b"-----BEGIN OPENSSH PRIVATE KEY-----",
)
MAX_IMPORT_FILES = 500
MAX_IMPORT_FILE_BYTES = 1024 * 1024
MAX_IMPORT_TOTAL_BYTES = 5 * 1024 * 1024
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True)
class LandingResult:
    status: str
    prototype_id: str
    source_revision: str
    readback_path: Path
    receipt_path: Path


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
        raise PacketError("detached_head", "Prototype Landing requires a named review branch")
    return branch


def current_head(repo_root: Path) -> str:
    return _run_git(repo_root, "rev-parse", "HEAD")


def _require_clean_worktree(repo_root: Path) -> None:
    if _run_git(repo_root, "status", "--porcelain"):
        raise PacketError("dirty_worktree", "Prototype Landing requires a clean source worktree")


def _worktree_revision(repo_root: Path) -> str:
    common_dir = Path(_run_git(repo_root, "rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    common_dir.mkdir(parents=True, exist_ok=True)
    descriptor, index_name = tempfile.mkstemp(prefix="prototype-landing-index-", dir=common_dir)
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


def validate_contract_bundle(repo_root: Path) -> None:
    bundle = repo_root / CONTRACT_DIR
    manifest = load_json(bundle / "manifest.json")
    if manifest.get("authority_repo") != "workspace-governance":
        raise PacketError("contract_bundle_invalid", "Prototype Landing authority repo is invalid")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files:
        raise PacketError("contract_bundle_invalid", "Prototype Landing manifest has no files")
    for name, expected in files.items():
        path = bundle / name
        if not path.is_file():
            raise PacketError("contract_bundle_invalid", f"missing synchronized contract file {name}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise PacketError("contract_bundle_stale", f"synchronized contract digest differs for {name}")
    contract = load_yaml(bundle / "prototype-landing.yaml")
    validate_schema(
        _schema_validator(repo_root, "prototype-landing.schema.json"),
        contract,
        code="contract_bundle_invalid",
        label="Prototype Landing contract",
    )


def _artifact_ref(artifact: dict[str, Any]) -> dict[str, str]:
    artifact_type = str(artifact["artifact_type"])
    id_fields = {
        "prototype-entry-packet": "entry_id",
        "prototype-landing-request": "request_id",
        "prototype-landing-plan": "plan_id",
        "prototype-landing-readiness": "readiness_id",
        "prototype-landing-apply": "apply_id",
        "prototype-landing-readback": "readback_id",
    }
    return {
        "id": str(artifact[id_fields[artifact_type]]),
        "digest": str(artifact[DIGEST_FIELD_BY_TYPE[artifact_type]]),
    }


def _with_digest(payload: dict[str, Any]) -> dict[str, Any]:
    artifact_type = str(payload["artifact_type"])
    result = copy.deepcopy(payload)
    result[DIGEST_FIELD_BY_TYPE[artifact_type]] = content_digest(result)
    return result


def validate_artifact(repo_root: Path, artifact: dict[str, Any]) -> None:
    artifact_type = artifact.get("artifact_type")
    schema_name = SCHEMA_BY_TYPE.get(str(artifact_type))
    if schema_name is None:
        raise PacketError("artifact_type_invalid", f"unsupported Landing artifact {artifact_type!r}")
    validate_schema(
        _schema_validator(repo_root, schema_name),
        artifact,
        code="artifact_invalid",
        label=str(artifact_type),
    )
    digest_field = DIGEST_FIELD_BY_TYPE[str(artifact_type)]
    body = {key: value for key, value in artifact.items() if key != digest_field}
    if artifact[digest_field] != content_digest(body):
        raise PacketError("artifact_digest_mismatch", f"{artifact_type} digest does not match its content")


def _require_ref(actual: Any, expected: dict[str, str], label: str) -> None:
    if actual != expected:
        raise PacketError("artifact_binding_invalid", f"{label} does not bind the exact artifact")


def _validate_chain(
    entry: dict[str, Any],
    request: dict[str, Any],
    plan: dict[str, Any],
    readiness: dict[str, Any],
    apply: dict[str, Any],
) -> None:
    _require_ref(request["entry_packet_ref"], _artifact_ref(entry), "request entry packet")
    _require_ref(plan["request_ref"], _artifact_ref(request), "plan request")
    _require_ref(readiness["request_ref"], _artifact_ref(request), "readiness request")
    _require_ref(readiness["plan_ref"], _artifact_ref(plan), "readiness plan")
    _require_ref(apply["request_ref"], _artifact_ref(request), "apply request")
    _require_ref(apply["plan_ref"], _artifact_ref(plan), "apply plan")
    _require_ref(apply["readiness_ref"], _artifact_ref(readiness), "apply readiness")
    prototype_id = request["prototype"]["id"]
    if {prototype_id, plan["prototype_id"], apply["prototype_id"]} != {prototype_id}:
        raise PacketError("prototype_identity_mismatch", "Landing artifacts bind different Prototype identities")
    if plan["source_plan"] != request["source_plan"]:
        raise PacketError("source_plan_mismatch", "plan source posture differs from the accepted request")
    if set(plan["mutation_set"]) != {item["kind"] for item in plan["expected_outputs"]}:
        raise PacketError("mutation_set_invalid", "plan outputs do not cover the exact mutation set")
    if readiness["outcome"] != "ready" or any(
        check["state"] != "ready" for check in readiness["checks"]
    ):
        raise PacketError("readiness_denied", "Prototype Landing apply requires every readiness check to be ready")
    if any(finding["severity"] == "blocking" for finding in readiness["findings"]):
        raise PacketError("readiness_denied", "Prototype Landing readiness contains a blocking finding")
    check_ids = [check["id"] for check in readiness["checks"]]
    if len(check_ids) != len(set(check_ids)) or len(check_ids) != 11:
        raise PacketError("readiness_invalid", "readiness must contain each authoritative check once")
    rows = request["setup"]["support_rows"]
    dimensions = [row["dimension"] for row in rows]
    if len(dimensions) != len(set(dimensions)) or set(dimensions) != SUPPORT_DIMENSIONS:
        raise PacketError("support_rows_invalid", "support rows must cover each support dimension once")
    if any(row["state"] in {"unknown", "blocked"} for row in rows):
        raise PacketError("support_rows_blocked", "unknown or blocked support rows cannot be applied")
    if request["correlation_id"] != apply["correlation_id"]:
        raise PacketError("correlation_mismatch", "request and apply correlation ids differ")
    if request["idempotency_key"] != apply["idempotency_key"]:
        raise PacketError("idempotency_mismatch", "request and apply idempotency keys differ")
    request_state = request["expected_state"]
    observed_state = readiness["observed_state"]
    apply_state = apply["expected_state"]
    shared_state = {
        "registry_digest": request_state["registry_digest"],
        "record_present": request_state["record_present"],
        "source_revision": request_state["source_revision"],
    }
    if request_state["record_digest"] is not None or shared_state != observed_state or apply_state != observed_state:
        raise PacketError("expected_state_mismatch", "request, readiness, and apply state bindings differ")


def _slug(prototype_id: str) -> str:
    value = prototype_id.removeprefix("prototype:")
    if not SAFE_ID.fullmatch(value) or "/" in value or ".." in value:
        raise PacketError("prototype_identity_invalid", "Prototype identity is not a safe source id")
    return value


def _repo_ref_path(repo_root: Path, source_ref: str) -> Path:
    prefix = "repo://workspace-prototype-studio/"
    if not source_ref.startswith(prefix):
        raise PacketError("source_ref_invalid", f"Studio source ref must start with {prefix}")
    relative = Path(source_ref.removeprefix(prefix))
    if relative.is_absolute() or ".." in relative.parts:
        raise PacketError("source_ref_invalid", "Studio source ref escapes the repository")
    result = (repo_root / relative).resolve()
    try:
        result.relative_to(repo_root.resolve())
    except ValueError as error:
        raise PacketError("source_ref_invalid", "Studio source ref escapes the repository") from error
    return result


def _expected_targets(slug: str) -> dict[str, str]:
    return {
        "registry-record": "prototypes.yaml",
        "prototype-docs": f"docs/prototypes/{slug}",
        "prototype-source": f"prototypes/{slug}",
        "fixtures": f"fixtures/prototypes/{slug}",
        "preview-profile-draft": f"records/prototype-preview-profiles/{slug}.yaml",
        "validation-plan": f"records/prototype-landings/{slug}/validation-plan.yaml",
    }


def _validate_mutation_plan(plan: dict[str, Any], posture: str, slug: str) -> None:
    mutation_set = set(plan["mutation_set"])
    if not {"registry-record", "prototype-docs"}.issubset(mutation_set):
        raise PacketError("mutation_set_invalid", "Landing requires registry-record and prototype-docs outputs")
    if posture in {"create-studio-source", "import-to-studio"} and "prototype-source" not in mutation_set:
        raise PacketError("mutation_set_invalid", f"{posture} requires a prototype-source output")
    if posture in REFERENCE_ONLY_POSTURES and mutation_set & {"prototype-source", "fixtures"}:
        raise PacketError("reference_only_mutation", "reference-only Landing cannot copy source or fixtures")
    if posture == "use-existing-studio-source" and "prototype-source" in mutation_set:
        raise PacketError("mutation_set_invalid", "existing Studio source is referenced without rewriting it")
    targets = _expected_targets(slug)
    for output in plan["expected_outputs"]:
        if output["target_ref"] != targets[output["kind"]]:
            raise PacketError(
                "mutation_target_invalid",
                f"{output['kind']} target must be {targets[output['kind']]}",
            )


def _source_files(source_root: Path) -> list[tuple[Path, bytes]]:
    if not source_root.is_dir():
        raise PacketError("import_source_invalid", "import source must be a directory")
    files: list[tuple[Path, bytes]] = []
    total = 0
    for path in sorted(source_root.rglob("*")):
        relative = path.relative_to(source_root)
        if ".git" in relative.parts:
            continue
        if path.is_symlink():
            raise PacketError("import_unsafe_link", f"import contains a symbolic link: {relative}")
        if path.is_dir():
            continue
        if not path.is_file():
            raise PacketError("import_unsupported_content", f"import contains a special file: {relative}")
        if len(relative.as_posix()) > 240:
            raise PacketError("import_path_too_long", f"import path is too long: {relative}")
        if path.name.lower() in SECRET_NAMES or path.suffix.lower() in SECRET_SUFFIXES:
            raise PacketError("import_secret_finding", f"import contains a secret-bearing filename: {relative}")
        size = path.stat().st_size
        if size > MAX_IMPORT_FILE_BYTES:
            raise PacketError("import_content_too_large", f"import file exceeds the size limit: {relative}")
        total += size
        if total > MAX_IMPORT_TOTAL_BYTES or len(files) >= MAX_IMPORT_FILES:
            raise PacketError("import_content_too_large", "import exceeds bounded content limits")
        content = path.read_bytes()
        if any(marker in content for marker in SECRET_MARKERS):
            raise PacketError("import_secret_finding", f"import contains private key material: {relative}")
        files.append((relative, content))
    if not files:
        raise PacketError("import_source_invalid", "import source contains no files")
    return files


def imported_content_digest(source_root: Path) -> str:
    manifest = [
        {"path": path.as_posix(), "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}
        for path, content in _source_files(source_root.resolve())
    ]
    return content_digest(manifest)


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _yaml_bytes(payload: dict[str, Any]) -> bytes:
    return yaml.safe_dump(payload, sort_keys=False, allow_unicode=False).encode("utf-8")


def _brief(name: str, objective: str, setup: dict[str, Any]) -> bytes:
    return (
        f"# {name}\n\n## Purpose\n\n{objective}\n\n"
        "## Current Lifecycle\n\n`exploring`\n\n"
        "## Visibility And Data\n\n"
        f"- Visibility: `{setup['visibility']}`\n"
        f"- Data mode: `{setup['data_mode']}`\n"
        f"- Mutation boundary: `{setup['mutation_boundary']}`\n\n"
        "## Success Signal\n\nDefine the smallest evidence that justifies Candidate Promotion.\n"
    ).encode("utf-8")


def _record_validator(repo_root: Path) -> Draft202012Validator:
    schema = load_json(repo_root / CONTRACT_DIR / "prototype-landing-readback.schema.json")
    record_schema = copy.deepcopy(schema["properties"]["record"])
    record_schema["$defs"] = copy.deepcopy(schema["$defs"])
    Draft202012Validator.check_schema(record_schema)
    return Draft202012Validator(record_schema, format_checker=FormatChecker())


def _build_record(
    entry: dict[str, Any], request: dict[str, Any], base_head: str
) -> dict[str, Any]:
    source_plan = request["source_plan"]
    source_revision = source_plan["source_revision"]
    if source_revision is None:
        source_revision = (
            source_plan["imported_content_digest"]
            if source_plan["posture"] == "import-to-studio"
            else f"created-from:{base_head}"
        )
    return {
        "id": request["prototype"]["id"],
        "entry_ref": _artifact_ref(entry),
        "name": request["prototype"]["name"],
        "objective": request["prototype"]["objective"],
        "ingress_class": entry["ingress_class"],
        "lifecycle": "exploring",
        "project_phase": "incubating",
        "setup": copy.deepcopy(request["setup"]),
        "source": {
            "posture": source_plan["posture"],
            "custody": CUSTODY_BY_POSTURE[source_plan["posture"]],
            "ref": source_plan["source_ref"],
            "revision": source_revision,
        },
        "next_action": "candidate-promotion",
    }


def _build_registry_item(record: dict[str, Any], slug: str) -> dict[str, Any]:
    record_ref = f"record://prototype-landings/{slug}"
    return {
        "id": slug,
        "name": record["name"],
        "objective": record["objective"],
        "lifecycle": "exploring",
        "project_phase": "incubating",
        "owner": "Workspace Prototype Studio",
        "linked_records": [
            {
                "role": "landing-record",
                "ref": record_ref,
                "system": "prototype-studio",
                "level": "record",
                "label": "Prototype Landing source record",
            }
        ],
        "visibility_tier": VISIBILITY_MAP[record["setup"]["visibility"]],
        "data_mode": record["setup"]["data_mode"],
        "mutation_boundary": MUTATION_MAP[record["setup"]["mutation_boundary"]],
        "landing_record_ref": record_ref,
        "paths": {
            "brief": f"docs/prototypes/{slug}/brief.md",
            "backlog": f"docs/prototypes/{slug}/backlog.md",
            "design_profile": f"docs/prototypes/{slug}/design-profile.md",
            "change_log": f"docs/prototypes/{slug}/change-log.md",
            "decision_log": f"docs/prototypes/{slug}/decision-log.md",
        },
    }


def _prepare_writes(
    repo_root: Path,
    entry: dict[str, Any],
    request: dict[str, Any],
    plan: dict[str, Any],
    apply: dict[str, Any],
    import_root: Path | None,
) -> tuple[dict[Path, bytes], dict[str, Any], dict[str, Any]]:
    slug = _slug(request["prototype"]["id"])
    posture = request["source_plan"]["posture"]
    _validate_mutation_plan(plan, posture, slug)
    registry = load_yaml(repo_root / "prototypes.yaml")
    record_path = repo_root / LANDING_RECORD_DIR / slug / "record.json"
    history_path = repo_root / LANDING_RECORD_DIR / slug / "history" / f"{apply['apply_id'].replace(':', '-')}.json"
    same_id = [item for item in registry.get("prototypes", []) if item.get("id") == slug]
    if same_id or record_path.exists():
        raise PacketError("prototype_identity_conflict", f"Prototype identity {request['prototype']['id']} already exists")

    base_head = current_head(repo_root)
    record = _build_record(entry, request, base_head)
    validate_schema(
        _record_validator(repo_root),
        record,
        code="source_record_invalid",
        label="Prototype Landing source record",
    )
    updated_registry = copy.deepcopy(registry)
    updated_registry.setdefault("prototypes", []).append(_build_registry_item(record, slug))
    validate_schema(
        Draft202012Validator(load_json(repo_root / "schemas/prototype-registry.schema.json")),
        updated_registry,
        code="source_record_invalid",
        label="updated Prototype registry",
    )

    writes: dict[Path, bytes] = {
        repo_root / "prototypes.yaml": _yaml_bytes(updated_registry),
        record_path: _json_bytes(record),
        history_path: _json_bytes(apply),
    }
    mutation_set = set(plan["mutation_set"])
    docs_dir = repo_root / "docs" / "prototypes" / slug
    writes[docs_dir / "brief.md"] = _brief(record["name"], record["objective"], record["setup"])
    template_dir = repo_root / "docs" / "prototypes" / "_template"
    for name in ("backlog.md", "change-log.md", "decision-log.md", "design-profile.md"):
        writes[docs_dir / name] = (template_dir / name).read_bytes()

    source_target = repo_root / "prototypes" / slug
    if posture == "create-studio-source":
        if import_root is not None:
            raise PacketError("import_source_unexpected", "create-studio-source does not accept imported content")
        expected_ref = f"repo://workspace-prototype-studio/prototypes/{slug}"
        if request["source_plan"]["source_ref"] != expected_ref:
            raise PacketError("source_ref_invalid", f"new Studio source ref must be {expected_ref}")
        writes[source_target / "README.md"] = (
            f"# {record['name']}\n\n{record['objective']}\n\n"
            "This incubation source was prepared by Prototype Landing.\n"
        ).encode("utf-8")
    elif posture == "import-to-studio":
        if import_root is None:
            raise PacketError("import_source_required", "import-to-studio requires --import-root")
        actual_digest = imported_content_digest(import_root)
        if actual_digest != request["source_plan"]["imported_content_digest"]:
            raise PacketError("import_digest_mismatch", "imported content digest differs from the request")
        for relative, content in _source_files(import_root.resolve()):
            writes[source_target / relative] = content
    elif posture == "use-existing-studio-source":
        if import_root is not None:
            raise PacketError("import_source_unexpected", "existing Studio source does not accept imported content")
        source_path = _repo_ref_path(repo_root, request["source_plan"]["source_ref"])
        if not source_path.exists():
            raise PacketError("source_ref_missing", "existing Studio source ref does not resolve")
        relative_source = source_path.relative_to(repo_root).as_posix()
        revision = str(request["source_plan"]["source_revision"])
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}:{relative_source}"],
            cwd=repo_root,
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode:
            raise PacketError("source_revision_invalid", "existing Studio source is absent at the bound revision")
    elif import_root is not None:
        raise PacketError("reference_only_mutation", "reference-only Landing does not accept source content")

    if "fixtures" in mutation_set:
        writes[repo_root / "fixtures" / "prototypes" / slug / ".gitkeep"] = b""
    if "preview-profile-draft" in mutation_set:
        writes[repo_root / "records" / "prototype-preview-profiles" / f"{slug}.yaml"] = _yaml_bytes(
            {
                "schema_version": 1,
                "prototype_id": record["id"],
                "status": "draft",
                "support_profile": record["setup"]["support_profile"],
                "preview_mode": record["setup"]["preview_mode"],
                "runtime_activation": False,
            }
        )
    if "validation-plan" in mutation_set:
        writes[repo_root / LANDING_RECORD_DIR / slug / "validation-plan.yaml"] = _yaml_bytes(
            {
                "schema_version": 1,
                "prototype_id": record["id"],
                "support_rows": copy.deepcopy(record["setup"]["support_rows"]),
                "runtime_validation": "not-authorized",
                "next_action": "candidate-promotion",
            }
        )
    collisions = [
        path.relative_to(repo_root)
        for path in writes
        if path != repo_root / "prototypes.yaml" and path.exists()
    ]
    if collisions:
        raise PacketError(
            "source_target_conflict",
            "Landing would overwrite existing source: " + ", ".join(str(path) for path in collisions),
        )
    return writes, updated_registry, record


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


def _write_evidence(transaction: _Transaction, path: Path, payload: dict[str, Any]) -> None:
    content = _json_bytes(payload)
    if path.exists():
        if path.read_bytes() == content:
            return
        raise PacketError("evidence_conflict", f"Landing evidence already exists at {path}")
    transaction.write(path, content)


@contextmanager
def _authority_lock(repo_root: Path) -> Iterator[None]:
    common_dir = Path(_run_git(repo_root, "rev-parse", "--git-common-dir"))
    if not common_dir.is_absolute():
        common_dir = (repo_root / common_dir).resolve()
    lock_path = common_dir / "prototype-landing.lock"
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _existing_apply(repo_root: Path, idempotency_key: str) -> dict[str, Any] | None:
    for path in sorted((repo_root / LANDING_RECORD_DIR).glob("*/history/*.json")):
        artifact = load_json(path)
        if artifact.get("artifact_type") == "prototype-landing-apply" and artifact.get("idempotency_key") == idempotency_key:
            validate_artifact(repo_root, artifact)
            return artifact
    return None


def _timestamp(now: str) -> int:
    parsed = datetime.fromisoformat(now.replace("Z", "+00:00"))
    return int(parsed.timestamp() * 1_000_000)


def _build_outputs(
    *,
    entry: dict[str, Any],
    request: dict[str, Any],
    plan: dict[str, Any],
    readiness: dict[str, Any],
    apply: dict[str, Any],
    record: dict[str, Any],
    registry: dict[str, Any],
    branch: str,
    source_revision: str,
    phase: str,
    now: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    sequence = _timestamp(now)
    slug = _slug(record["id"])
    readback = _with_digest(
        {
            "schema_version": 1,
            "artifact_type": "prototype-landing-readback",
            "readback_id": f"prototype-landing-readback:{slug}:{sequence}",
            "apply_ref": _artifact_ref(apply),
            "prototype_id": record["id"],
            "authority_state": "review-branch",
            "source_branch": branch,
            "source_revision": source_revision,
            "registry_digest": content_digest(registry),
            "record_digest": content_digest(record),
            "record": copy.deepcopy(record),
            "observed_at": now,
        }
    )
    receipt = _with_digest(
        {
            "schema_version": 1,
            "artifact_type": "prototype-landing-receipt",
            "receipt_id": f"prototype-landing-receipt:{slug}:{sequence}",
            "completed_at": now,
            "entry_packet_ref": _artifact_ref(entry),
            "request_ref": _artifact_ref(request),
            "plan_ref": _artifact_ref(plan),
            "readiness_ref": _artifact_ref(readiness),
            "apply_ref": _artifact_ref(apply),
            "readback_ref": _artifact_ref(readback),
            "prototype_id": record["id"],
            "phase": phase,
            "outcome": "prepared" if phase == "source-preparation" else "replayed",
            "source_result": {
                "repo": "workspace-prototype-studio",
                "branch": branch,
                "revision": source_revision,
                "registry_digest": content_digest(registry),
                "record_digest": content_digest(record),
            },
            "next_action": {"code": "review-source", "owner_ref": "operator-orchestration-service"},
            "correlation_id": request["correlation_id"],
            "idempotency_key": request["idempotency_key"],
        }
    )
    return readback, receipt


def _ensure_output_outside_repo(repo_root: Path, output_dir: Path) -> None:
    try:
        output_dir.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return
    raise PacketError("output_boundary_invalid", "Landing evidence output must be outside Prototype Studio source")


def apply_landing(
    *,
    repo_root: Path,
    entry: dict[str, Any],
    request: dict[str, Any],
    plan: dict[str, Any],
    readiness: dict[str, Any],
    apply: dict[str, Any],
    output_dir: Path,
    import_root: Path | None = None,
    completed_at: str | None = None,
) -> LandingResult:
    repo_root = repo_root.resolve()
    output_dir = output_dir.resolve()
    _ensure_output_outside_repo(repo_root, output_dir)
    validate_contract_bundle(repo_root)
    for artifact in (entry, request, plan, readiness, apply):
        validate_artifact(repo_root, artifact)
    _validate_chain(entry, request, plan, readiness, apply)
    branch = current_branch(repo_root)
    if branch in {"main", "master"} or branch != apply["source_branch"]:
        raise PacketError("source_branch_invalid", "apply must bind the current non-default review branch")
    now = completed_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    with _authority_lock(repo_root):
        existing = _existing_apply(repo_root, request["idempotency_key"])
        if existing is not None:
            if existing != apply:
                raise PacketError("idempotency_conflict", "idempotency key is bound to another Landing apply")
            slug = _slug(request["prototype"]["id"])
            record = load_json(repo_root / LANDING_RECORD_DIR / slug / "record.json")
            registry = load_yaml(repo_root / "prototypes.yaml")
            revision = _worktree_revision(repo_root)
            readback, receipt = _build_outputs(
                entry=entry,
                request=request,
                plan=plan,
                readiness=readiness,
                apply=apply,
                record=record,
                registry=registry,
                branch=branch,
                source_revision=revision,
                phase="source-replay",
                now=now,
            )
            for artifact in (readback, receipt):
                validate_artifact(repo_root, artifact)
            transaction = _Transaction()
            try:
                _write_evidence(transaction, output_dir / "readback.json", readback)
                _write_evidence(transaction, output_dir / "receipt.json", receipt)
            except BaseException:
                transaction.rollback()
                raise
            return LandingResult("replayed", record["id"], revision, output_dir / "readback.json", output_dir / "receipt.json")

        _require_clean_worktree(repo_root)
        registry = load_yaml(repo_root / "prototypes.yaml")
        registry_digest = content_digest(registry)
        expected = apply["expected_state"]
        if expected["registry_digest"] != registry_digest:
            raise PacketError("source_state_stale", "Prototype registry digest differs from apply")
        if expected["record_present"] or expected.get("record_digest") is not None:
            raise PacketError("source_state_invalid", "Landing create requires an absent Prototype record")
        if expected.get("source_revision") is not None and expected["source_revision"] != current_head(repo_root):
            raise PacketError("source_state_stale", "Prototype Studio source revision differs from apply")

        writes, updated_registry, record = _prepare_writes(
            repo_root, entry, request, plan, apply, import_root
        )
        transaction = _Transaction()
        try:
            for path, content in sorted(writes.items(), key=lambda item: str(item[0])):
                transaction.write(path, content)
            revision = _worktree_revision(repo_root)
            readback, receipt = _build_outputs(
                entry=entry,
                request=request,
                plan=plan,
                readiness=readiness,
                apply=apply,
                record=record,
                registry=updated_registry,
                branch=branch,
                source_revision=revision,
                phase="source-preparation",
                now=now,
            )
            for artifact in (readback, receipt):
                validate_artifact(repo_root, artifact)
            _write_evidence(transaction, output_dir / "readback.json", readback)
            _write_evidence(transaction, output_dir / "receipt.json", receipt)
        except BaseException:
            transaction.rollback()
            raise
    return LandingResult("prepared", record["id"], revision, output_dir / "readback.json", output_dir / "receipt.json")


def current_state(repo_root: Path, prototype_id: str) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    slug = _slug(prototype_id)
    registry = load_yaml(repo_root / "prototypes.yaml")
    matches = [item for item in registry.get("prototypes", []) if item.get("id") == slug]
    record_path = repo_root / LANDING_RECORD_DIR / slug / "record.json"
    record = load_json(record_path) if record_path.exists() else None
    return {
        "prototype_id": prototype_id,
        "expected_state": {
            "registry_digest": content_digest(registry),
            "record_present": bool(matches or record is not None),
            "record_digest": content_digest(record) if record is not None else None,
            "source_revision": current_head(repo_root),
        },
    }


def validate_landing_records(repo_root: Path) -> list[Path]:
    repo_root = repo_root.resolve()
    validate_contract_bundle(repo_root)
    registry = load_yaml(repo_root / "prototypes.yaml")
    registry_by_id = {item["id"]: item for item in registry.get("prototypes", [])}
    validated: list[Path] = []
    used_keys: dict[str, str] = {}
    for record_path in sorted((repo_root / LANDING_RECORD_DIR).glob("*/record.json")):
        record = load_json(record_path)
        validate_schema(
            _record_validator(repo_root),
            record,
            code="source_record_invalid",
            label=str(record_path.relative_to(repo_root)),
        )
        slug = _slug(record["id"])
        if record_path != repo_root / LANDING_RECORD_DIR / slug / "record.json":
            raise PacketError("source_record_path_invalid", f"Landing record path differs for {slug}")
        registry_item = registry_by_id.get(slug)
        if registry_item is None or registry_item.get("landing_record_ref") != f"record://prototype-landings/{slug}":
            raise PacketError("source_record_unlinked", f"Landing record {slug} is not linked from the registry")
        linked = [
            item
            for item in registry_item.get("linked_records", [])
            if item.get("role") == "landing-record"
            and item.get("ref") == f"record://prototype-landings/{slug}"
        ]
        if len(linked) != 1:
            raise PacketError("source_record_unlinked", f"registry {slug} must link its Landing record exactly once")
        apply_paths = sorted((record_path.parent / "history").glob("*.json"))
        if not apply_paths:
            raise PacketError("source_history_missing", f"Landing record {slug} has no immutable apply history")
        for apply_path in apply_paths:
            apply = load_json(apply_path)
            validate_artifact(repo_root, apply)
            if apply["prototype_id"] != record["id"]:
                raise PacketError("history_identity_mismatch", f"{apply_path} belongs to another Prototype")
            previous = used_keys.setdefault(apply["idempotency_key"], apply["apply_digest"])
            if previous != apply["apply_digest"]:
                raise PacketError("idempotency_conflict", f"conflicting Landing history for {apply['idempotency_key']}")
        validated.append(record_path)
    for slug, registry_item in registry_by_id.items():
        landing_ref = registry_item.get("landing_record_ref")
        expected_path = repo_root / LANDING_RECORD_DIR / slug / "record.json"
        if landing_ref and expected_path not in validated:
            raise PacketError("source_record_missing", f"registry {slug} points to a missing Landing record")
    return validated
