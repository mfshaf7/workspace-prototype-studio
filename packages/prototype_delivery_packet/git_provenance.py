from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

from packages.prototype_delivery_packet.contract import PacketError


def run_git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise PacketError("source_provenance_invalid", detail)
    return result.stdout.strip()


def load_yaml_at_revision(
    repo_root: Path,
    commit: str,
    relative_path: Path,
) -> dict[str, Any]:
    raw = run_git(repo_root, "show", f"{commit}:{relative_path.as_posix()}")
    try:
        payload = yaml.safe_load(raw) or {}
    except yaml.YAMLError as error:
        raise PacketError(
            "source_record_invalid",
            f"{relative_path} at {commit} is not valid YAML: {error}",
        ) from error
    if not isinstance(payload, dict):
        raise PacketError(
            "source_record_invalid",
            f"{relative_path} at {commit} must contain an object",
        )
    return payload


def validate_source_revision(
    repo_root: Path,
    source_revision: dict[str, Any],
    *,
    require_ref_match: bool,
) -> str:
    base_commit = str(source_revision["base_commit"])
    head_commit = str(source_revision["head_commit"])
    source_ref = str(source_revision["ref"])

    for commit_name, commit in (("base_commit", base_commit), ("head_commit", head_commit)):
        resolved = run_git(repo_root, "rev-parse", "--verify", f"{commit}^{{commit}}")
        if resolved != commit:
            raise PacketError(
                "source_provenance_invalid",
                f"{commit_name} does not resolve to the declared commit",
            )

    ancestry = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base_commit, head_commit],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
    )
    if ancestry.returncode != 0:
        raise PacketError(
            "source_ancestry_invalid",
            f"base commit {base_commit} is not an ancestor of {head_commit}",
        )

    if require_ref_match:
        resolved_ref = run_git(
            repo_root,
            "rev-parse",
            "--verify",
            f"{source_ref}^{{commit}}",
        )
        if resolved_ref != head_commit:
            raise PacketError(
                "source_revision_stale",
                f"{source_ref} resolves to {resolved_ref}, not declared head {head_commit}",
            )

    return run_git(repo_root, "rev-parse", f"{head_commit}^{{tree}}")
