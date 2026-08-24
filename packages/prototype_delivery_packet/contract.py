from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker


class PacketError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def content_digest(payload: Any) -> str:
    return f"sha256:{hashlib.sha256(canonical_json_bytes(payload)).hexdigest()}"


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PacketError("malformed_record", f"cannot read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise PacketError("malformed_record", f"{path} must contain an object")
    return payload


def load_yaml(path: Path) -> dict[str, Any]:
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        raise PacketError("malformed_record", f"cannot read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise PacketError("malformed_record", f"{path} must contain an object")
    return payload


def schema_validator(repo_root: Path, name: str) -> Draft202012Validator:
    schema = load_json(repo_root / "schemas" / name)
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def validate_schema(
    validator: Draft202012Validator,
    payload: dict[str, Any],
    *,
    code: str,
    label: str,
) -> None:
    errors = sorted(validator.iter_errors(payload), key=lambda item: list(item.absolute_path))
    if not errors:
        return
    details = "; ".join(
        f"{'.'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
        for error in errors
    )
    raise PacketError(code, f"{label} is invalid: {details}")
