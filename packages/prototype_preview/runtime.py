from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import mimetypes
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator

import yaml
from jsonschema import Draft202012Validator, FormatChecker


PROFILE_DIR = Path("records/prototype-preview-profiles")
PROFILE_SCHEMA = Path("schemas/prototype-preview-profile.schema.json")
PROJECTION_SCHEMA = Path("schemas/prototype-preview-projection.schema.json")
RECEIPT_SCHEMA = Path("schemas/prototype-preview-receipt.schema.json")
REQUEST_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._:-")
DIGEST_PREFIX = "sha256:"
HEX_CHARS = frozenset("0123456789abcdef")
MAX_SOURCE_FILES = 500
MAX_SOURCE_BYTES = 5 * 1024 * 1024
_SPAWNED_PROCESSES: dict[int, subprocess.Popen[bytes]] = {}


class PreviewError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical(value)).hexdigest()


def _is_hex(value: Any, length: int) -> bool:
    return (
        isinstance(value, str)
        and len(value) == length
        and all(char in HEX_CHARS for char in value)
    )


def _is_digest(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(DIGEST_PREFIX) and _is_hex(value[7:], 64)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PreviewError("record_unreadable", f"cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise PreviewError("record_invalid", f"{path} must contain an object")
    return value


def _validator(repo_root: Path, schema_path: Path) -> Draft202012Validator:
    schema = _load_json(repo_root / schema_path)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _validate(validator: Draft202012Validator, value: Any, label: str) -> None:
    errors = sorted(validator.iter_errors(value), key=lambda item: list(item.absolute_path))
    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "$"
        raise PreviewError("record_invalid", f"{label} {location}: {error.message}")


def _git(repo_root: Path, args: list[str], code: str, message: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        raise PreviewError(code, message)
    return result


def _git_revision(repo_root: Path) -> str:
    result = _git(
        repo_root,
        ["rev-parse", "HEAD"],
        "source_revision_unavailable",
        "preview source must be a Git revision",
    )
    revision = result.stdout.strip()
    if len(revision) != 40:
        raise PreviewError("source_revision_unavailable", "preview source must be a Git revision")
    return revision


def _assert_reviewed_checkout(repo_root: Path, source_root: Path) -> None:
    status = _git(
        repo_root,
        ["status", "--porcelain=v1", "--untracked-files=all"],
        "source_state_unavailable",
        "preview source state is unavailable",
    )
    if status.stdout:
        raise PreviewError(
            "source_checkout_dirty",
            "preview runtime requires a clean reviewed checkout",
        )
    source_relative = source_root.relative_to(repo_root).as_posix()
    tracked = _git(
        repo_root,
        ["ls-files", "-z", "--", source_relative],
        "source_custody_unavailable",
        "preview source custody is unavailable",
    )
    tracked_paths = {
        Path(item).relative_to(source_relative).as_posix()
        for item in tracked.stdout.split("\0")
        if item
    }
    disk_paths = {
        path.relative_to(source_root).as_posix()
        for path in source_root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if not tracked_paths or tracked_paths != disk_paths:
        raise PreviewError(
            "source_custody_invalid",
            "preview source must contain only reviewed tracked files",
        )
    for relative_path in tracked_paths:
        path = source_root / relative_path
        if path.is_symlink() or not path.is_file():
            raise PreviewError(
                "source_custody_invalid",
                "preview source must contain only reviewed regular files",
            )


def _source_digest(source_root: Path) -> str:
    files = [path for path in sorted(source_root.rglob("*")) if path.is_file() and not path.is_symlink()]
    if len(files) > MAX_SOURCE_FILES:
        raise PreviewError("source_bounds_exceeded", "preview source contains too many files")
    total = sum(path.stat().st_size for path in files)
    if total > MAX_SOURCE_BYTES:
        raise PreviewError("source_bounds_exceeded", "preview source exceeds the byte limit")
    digest = hashlib.sha256()
    for path in files:
        relative = path.relative_to(source_root).as_posix().encode()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        content = path.read_bytes()
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return "sha256:" + digest.hexdigest()


def _default_state_root() -> Path:
    runtime_root = os.environ.get("XDG_RUNTIME_DIR")
    if runtime_root:
        return Path(runtime_root) / "workspace-prototype-studio" / "preview-runtime"
    return Path(tempfile.gettempdir()) / f"workspace-prototype-studio-{os.getuid()}" / "preview-runtime"


class PreviewRuntime:
    def __init__(self, repo_root: Path, profile_path: Path, state_root: Path | None = None):
        self.repo_root = repo_root.resolve()
        self.profile_path = profile_path.resolve()
        expected_parent = (self.repo_root / PROFILE_DIR).resolve()
        if self.profile_path.parent != expected_parent:
            raise PreviewError("profile_path_denied", f"profile must be directly under {PROFILE_DIR}")
        try:
            profile = yaml.safe_load(self.profile_path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as error:
            raise PreviewError("profile_unreadable", f"cannot read {self.profile_path}: {error}") from error
        if not isinstance(profile, dict):
            raise PreviewError("profile_invalid", "preview profile must contain an object")
        _validate(_validator(self.repo_root, PROFILE_SCHEMA), profile, "preview profile")
        self.profile = profile
        self.profile_digest = _digest(profile)
        self.source_root = (self.repo_root / profile["runtime"]["source_root"]).resolve()
        try:
            self.source_root.relative_to((self.repo_root / "prototypes").resolve())
        except ValueError as error:
            raise PreviewError("source_path_denied", "preview source must stay under prototypes/") from error
        if not self.source_root.is_dir() or self.source_root.is_symlink():
            raise PreviewError("source_unavailable", "preview source root must be a real directory")
        self.source_revision = _git_revision(self.repo_root)
        _assert_reviewed_checkout(self.repo_root, self.source_root)
        self.source_digest = _source_digest(self.source_root)
        self.state_root = (state_root or _default_state_root()).resolve() / profile["profile_id"]
        try:
            self.state_root.relative_to(self.repo_root)
        except ValueError:
            pass
        else:
            raise PreviewError("state_path_denied", "runtime state must remain outside the source repository")
        self.state_path = self.state_root / "state.json"
        self.lock_path = self.state_root / "runtime.lock"
        self.request_dir = self.state_root / "requests"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self.state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_root, 0o700)
        with self.lock_path.open("a+", encoding="utf-8") as handle:
            os.chmod(self.lock_path, 0o600)
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            yield

    def _state(self) -> dict[str, Any] | None:
        return _load_json(self.state_path) if self.state_path.is_file() else None

    def _health(self, timeout: float = 0.5) -> dict[str, Any] | None:
        url = f"http://127.0.0.1:{self.profile['runtime']['port']}{self.profile['runtime']['health_path']}"
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = json.loads(response.read().decode())
        except (OSError, urllib.error.URLError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _runtime_state(self, state: dict[str, Any] | None = None) -> str:
        state = self._state() if state is None else state
        if state is None:
            return "stopped"
        try:
            os.kill(int(state["pid"]), 0)
        except (KeyError, TypeError, ValueError, ProcessLookupError):
            return "stale"
        except PermissionError:
            return "stale"
        health = self._health()
        if health and all(
            health.get(field) == expected
            for field, expected in {
                "instance_id": state.get("instance_id"),
                "profile_id": self.profile["profile_id"],
                "prototype_id": self.profile["prototype_id"],
                "profile_digest": self.profile_digest,
                "source_digest": self.source_digest,
                "source_revision": self.source_revision,
                "maturity_claim": "prototype-preview-only",
                "public_ingress": False,
            }.items()
        ):
            return "running"
        return "stale"

    def _receipt_ref(self, receipt: dict[str, Any]) -> dict[str, str]:
        return {
            "ref": f"preview-runtime://receipts/{receipt['receipt_id']}",
            "digest": receipt["receipt_digest"],
        }

    def _latest_receipt(self, state: dict[str, Any] | None) -> dict[str, str] | None:
        value = state.get("latest_receipt") if state else None
        return copy.deepcopy(value) if isinstance(value, dict) else None

    def projection(self) -> dict[str, Any]:
        state = self._state()
        runtime_state = self._runtime_state(state)
        projection = {
            "schema_version": 1,
            "profile_id": self.profile["profile_id"],
            "prototype_id": self.profile["prototype_id"],
            "runtime_state": runtime_state,
            "maturity_claim": "prototype-preview-only",
            "profile_digest": self.profile_digest,
            "source_digest": self.source_digest,
            "source_revision": self.source_revision,
            "boundary": copy.deepcopy(self.profile["boundary"]),
            "endpoint": (
                f"http://127.0.0.1:{self.profile['runtime']['port']}" if runtime_state == "running" else None
            ),
            "instance_id": state.get("instance_id") if state and runtime_state == "running" else None,
            "latest_receipt": self._latest_receipt(state),
            "operator_actions": ["start", "status", "restart", "stop", "proof"],
        }
        _validate(_validator(self.repo_root, PROJECTION_SCHEMA), projection, "preview projection")
        return projection

    @staticmethod
    def _check_request_id(request_id: str) -> None:
        if not 3 <= len(request_id) <= 128 or any(char not in REQUEST_ID_CHARS for char in request_id):
            raise PreviewError("request_id_invalid", "request id must be 3-128 safe characters")

    def _request_path(self, request_id: str) -> Path:
        return self.request_dir / (hashlib.sha256(request_id.encode()).hexdigest() + ".json")

    def _replay(
        self,
        request_id: str,
        action: str,
        expected: dict[str, Any],
    ) -> dict[str, Any] | None:
        path = self._request_path(request_id)
        if not path.is_file():
            return None
        receipt = _load_json(path)
        if (
            receipt.get("request_id") != request_id
            or receipt.get("action") != action
            or receipt.get("expected") != expected
        ):
            raise PreviewError("request_replay_conflict", "request id is already bound to another command")
        self._validate_receipt(receipt)
        if any(
            receipt.get(field) != expected
            for field, expected in {
                "profile_digest": self.profile_digest,
                "source_digest": self.source_digest,
                "source_revision": self.source_revision,
            }.items()
        ):
            raise PreviewError("request_replay_stale", "request id is bound to an older profile or source revision")
        return receipt

    def _validate_receipt(self, receipt: dict[str, Any]) -> None:
        _validate(_validator(self.repo_root, RECEIPT_SCHEMA), receipt, "preview receipt")
        body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
        if receipt["receipt_digest"] != _digest(body):
            raise PreviewError("receipt_digest_mismatch", "preview receipt digest is invalid")

    def _store_receipt(
        self,
        request_id: str,
        action: str,
        expected: dict[str, Any],
        before: str,
        after: str,
    ) -> dict[str, Any]:
        body = {
            "schema_version": 1,
            "receipt_id": "prototype-preview-receipt:" + hashlib.sha256(
                f"{self.profile['profile_id']}:{request_id}:{action}".encode()
            ).hexdigest()[:24],
            "request_id": request_id,
            "action": action,
            "expected": copy.deepcopy(expected),
            "profile_id": self.profile["profile_id"],
            "prototype_id": self.profile["prototype_id"],
            "profile_digest": self.profile_digest,
            "source_digest": self.source_digest,
            "source_revision": self.source_revision,
            "before_state": before,
            "after_state": after,
            "outcome": "applied",
            "completed_at": _utc_now(),
        }
        receipt = {**body, "receipt_digest": _digest(body)}
        self._validate_receipt(receipt)
        _atomic_json(self._request_path(request_id), receipt)
        return receipt

    def _spawn(self) -> dict[str, Any]:
        if self.profile["status"] != "active" or self.profile["runtime_activation"] is not True:
            raise PreviewError("runtime_not_active", "profile is not admitted for local runtime activation")
        instance_id = hashlib.sha256(os.urandom(32)).hexdigest()[:24]
        log_path = self.state_root / "runtime.log"
        with log_path.open("ab") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    str(self.repo_root / "scripts/prototype_preview.py"),
                    "--repo-root",
                    str(self.repo_root),
                    "--state-root",
                    str(self.state_root.parent),
                    "serve",
                    "--profile",
                    str(self.profile_path),
                    "--instance-id",
                    instance_id,
                ],
                cwd=self.repo_root,
                stdin=subprocess.DEVNULL,
                stdout=log,
                stderr=log,
                start_new_session=True,
            )
        state = {
            "schema_version": 1,
            "profile_id": self.profile["profile_id"],
            "prototype_id": self.profile["prototype_id"],
            "profile_digest": self.profile_digest,
            "source_digest": self.source_digest,
            "source_revision": self.source_revision,
            "instance_id": instance_id,
            "pid": process.pid,
            "started_at": _utc_now(),
            "latest_receipt": None,
        }
        _SPAWNED_PROCESSES[process.pid] = process
        _atomic_json(self.state_path, state)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if self._runtime_state(state) == "running":
                return state
            if process.poll() is not None:
                break
            time.sleep(0.05)
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)
        _SPAWNED_PROCESSES.pop(process.pid, None)
        self.state_path.unlink(missing_ok=True)
        raise PreviewError("runtime_start_failed", f"preview runtime did not become healthy; inspect {log_path}")

    def _stop(self, state: dict[str, Any]) -> None:
        if self._runtime_state(state) != "running":
            raise PreviewError("runtime_identity_unverified", "refusing to stop an unverified or stale process")
        pid = int(state["pid"])
        os.kill(pid, signal.SIGTERM)
        spawned = _SPAWNED_PROCESSES.pop(pid, None)
        if spawned is not None:
            try:
                spawned.wait(timeout=5)
            except subprocess.TimeoutExpired as error:
                raise PreviewError("runtime_stop_failed", "preview runtime did not stop within five seconds") from error
            self.state_path.unlink(missing_ok=True)
            return
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                self.state_path.unlink(missing_ok=True)
                return
            time.sleep(0.05)
        raise PreviewError("runtime_stop_failed", "preview runtime did not stop within five seconds")

    def command(self, action: str, request_id: str, expected: Any) -> dict[str, Any]:
        if action not in {"start", "restart", "stop"}:
            raise PreviewError("command_invalid", f"unsupported mutating command {action}")
        self._check_request_id(request_id)
        expected = self._expected_state(expected)
        with self._locked():
            replay = self._replay(request_id, action, expected)
            if replay:
                return {"schema_version": 1, "status": "replayed", "receipt": replay}
            state = self._state()
            before = self._runtime_state(state)
            actual = {
                "instance_id": state.get("instance_id") if state and before == "running" else None,
                "profile_digest": self.profile_digest,
                "runtime_state": before,
                "source_digest": self.source_digest,
                "source_revision": self.source_revision,
            }
            if actual != expected:
                raise PreviewError(
                    "expected_state_stale",
                    "preview runtime changed after review; refresh before retrying",
                )
            if action == "start":
                if before == "running":
                    raise PreviewError("runtime_already_running", "preview runtime is already running")
                if before == "stale":
                    raise PreviewError("stale_runtime_state", "stale runtime state requires operator inspection")
                state = self._spawn()
            elif action == "restart":
                if state and before == "running":
                    self._stop(state)
                elif before == "stale":
                    raise PreviewError("stale_runtime_state", "stale runtime state requires operator inspection")
                state = self._spawn()
            else:
                if before == "stopped":
                    raise PreviewError("runtime_not_running", "preview runtime is not running")
                if before == "stale" or state is None:
                    raise PreviewError("stale_runtime_state", "stale runtime state requires operator inspection")
                self._stop(state)
                state = None
            after = self._runtime_state(state)
            receipt = self._store_receipt(request_id, action, expected, before, after)
            if state:
                state["latest_receipt"] = self._receipt_ref(receipt)
                _atomic_json(self.state_path, state)
            return {"schema_version": 1, "status": "applied", "receipt": receipt}

    def _expected_state(self, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise PreviewError("expected_state_invalid", "expected state must be an object")
        expected = {
            "instance_id": value.get("instance_id"),
            "profile_digest": value.get("profile_digest"),
            "runtime_state": value.get("runtime_state"),
            "source_digest": value.get("source_digest"),
            "source_revision": value.get("source_revision"),
        }
        if (
            expected["runtime_state"] not in {"running", "stale", "stopped"}
            or not _is_digest(expected["profile_digest"])
            or not _is_digest(expected["source_digest"])
            or not _is_hex(expected["source_revision"], 40)
            or (
                expected["instance_id"] is not None
                and (
                    not _is_hex(expected["instance_id"], 24)
                )
            )
        ):
            raise PreviewError("expected_state_invalid", "expected state binding is invalid")
        return expected

    def proof(self) -> dict[str, Any]:
        projection = self.projection()
        if projection["runtime_state"] != "running":
            raise PreviewError("runtime_not_running", "operating proof requires a running preview runtime")
        health = self._health(timeout=2)
        if not health:
            raise PreviewError("runtime_health_unavailable", "preview health readback is unavailable")
        expected = {
            "schema_version": 1,
            "profile_id": self.profile["profile_id"],
            "prototype_id": self.profile["prototype_id"],
            "instance_id": projection["instance_id"],
            "profile_digest": self.profile_digest,
            "source_digest": self.source_digest,
            "source_revision": self.source_revision,
            "maturity_claim": "prototype-preview-only",
            "public_ingress": False,
        }
        if health != expected:
            raise PreviewError("runtime_readback_mismatch", "health readback does not bind the exact profile and source")
        latest = projection["latest_receipt"]
        if latest is None:
            raise PreviewError("receipt_missing", "running preview has no bound command receipt")
        matching = []
        for path in self.request_dir.glob("*.json"):
            receipt = _load_json(path)
            if receipt.get("receipt_digest") == latest["digest"]:
                matching.append(receipt)
        if len(matching) != 1:
            raise PreviewError("receipt_readback_invalid", "latest receipt is absent or ambiguous")
        self._validate_receipt(matching[0])
        negative_checks = {
            "non_loopback_bind_denied": self.profile["runtime"]["bind_host"] == "127.0.0.1",
            "public_ingress_denied": self.profile["boundary"]["public_ingress"] is False,
            "external_network_denied": self.profile["boundary"]["external_network"] is False,
            "mutation_denied": self.profile["boundary"]["mutation_boundary"] == "none",
            "real_data_denied": self.profile["boundary"]["data_mode"] in {"mock", "synthetic"},
            "maturity_overclaim_denied": projection["maturity_claim"] == "prototype-preview-only",
            "stale_source_denied": health["source_digest"] == projection["source_digest"],
            "false_receipt_denied": matching[0]["receipt_digest"] == latest["digest"],
        }
        if not all(negative_checks.values()):
            raise PreviewError("negative_proof_failed", "one or more fail-closed checks did not hold")
        return {
            "schema_version": 1,
            "status": "proven",
            "profile_id": self.profile["profile_id"],
            "prototype_id": self.profile["prototype_id"],
            "projection_digest": _digest(projection),
            "health_digest": _digest(health),
            "receipt": latest,
            "positive_checks": [
                "exact-profile-readback",
                "exact-source-readback",
                "current-instance-readback",
                "receipt-custody-readback",
            ],
            "negative_checks": negative_checks,
            "security_gate": "gate:preview-runtime-operating-acceptance",
            "security_decision": "evaluated-by-oos-before-operating-ready",
        }


def validate_profiles(repo_root: Path) -> list[str]:
    profile_validator = _validator(repo_root, PROFILE_SCHEMA)
    registry = yaml.safe_load((repo_root / "prototypes.yaml").read_text(encoding="utf-8"))
    prototypes = {f"prototype:{item['id']}": item for item in registry.get("prototypes", [])}
    validated: list[str] = []
    for path in sorted((repo_root / PROFILE_DIR).glob("*.yaml")):
        profile = yaml.safe_load(path.read_text(encoding="utf-8"))
        _validate(profile_validator, profile, f"preview profile {path.name}")
        prototype = prototypes.get(profile["prototype_id"])
        if prototype is None:
            raise PreviewError("prototype_unknown", f"{path.name} references an unknown Prototype")
        source_root = (repo_root / profile["runtime"]["source_root"]).resolve()
        if not source_root.is_dir() or source_root.is_symlink():
            raise PreviewError("source_unavailable", f"{path.name} source root is unavailable")
        if profile["boundary"]["data_mode"] != prototype["data_mode"]:
            raise PreviewError("boundary_mismatch", f"{path.name} data mode differs from the Prototype registry")
        if profile["runtime"]["source_root"].split("/")[:2] != [
            "prototypes",
            profile["prototype_id"].removeprefix("prototype:"),
        ]:
            raise PreviewError("source_identity_mismatch", f"{path.name} source root differs from its Prototype")
        if profile["boundary"]["visibility_tier"] != prototype["visibility_tier"]:
            raise PreviewError("boundary_mismatch", f"{path.name} visibility differs from the Prototype registry")
        if profile["boundary"]["mutation_boundary"] != prototype["mutation_boundary"]:
            raise PreviewError("boundary_mismatch", f"{path.name} mutation boundary differs from the Prototype registry")
        validated.append(path.relative_to(repo_root).as_posix())
    return validated


def serve(runtime: PreviewRuntime, instance_id: str) -> None:
    health = {
        "schema_version": 1,
        "profile_id": runtime.profile["profile_id"],
        "prototype_id": runtime.profile["prototype_id"],
        "instance_id": instance_id,
        "profile_digest": runtime.profile_digest,
        "source_digest": runtime.source_digest,
        "source_revision": runtime.source_revision,
        "maturity_claim": "prototype-preview-only",
        "public_ingress": False,
    }

    class Handler(BaseHTTPRequestHandler):
        server_version = "PrototypePreview/1"

        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy", "default-src 'self'; object-src 'none'; frame-ancestors 'none'")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            if self.path == runtime.profile["runtime"]["health_path"]:
                body = _canonical(health)
                self._headers(200, "application/json", len(body))
                self.wfile.write(body)
                return
            relative = self.path.split("?", 1)[0].lstrip("/") or "index.html"
            candidate = (runtime.source_root / relative).resolve()
            try:
                candidate.relative_to(runtime.source_root)
            except ValueError:
                self.send_error(404)
                return
            if any(part.startswith(".") for part in Path(relative).parts) or not candidate.is_file() or candidate.is_symlink():
                self.send_error(404)
                return
            body = candidate.read_bytes()
            content_type = mimetypes.guess_type(candidate.name)[0] or "application/octet-stream"
            self._headers(200, content_type, len(body))
            self.wfile.write(body)

        def do_HEAD(self) -> None:  # noqa: N802
            self.send_error(405)

        def do_POST(self) -> None:  # noqa: N802
            self.send_error(405)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(
        (runtime.profile["runtime"]["bind_host"], runtime.profile["runtime"]["port"]),
        Handler,
    )
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(SystemExit(0)))
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()
