#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from packages.prototype_preview import PreviewError, PreviewRuntime  # noqa: E402
from packages.prototype_preview.runtime import serve, validate_profiles  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Operate the loopback-only Prototype Preview Runtime")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--state-root", type=Path)
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("validate-all", help="validate all Preview Runtime profiles")
    for name in ("status", "proof"):
        command = commands.add_parser(name, help=f"{name} one Preview Runtime")
        command.add_argument("--profile", type=Path, required=True)
    for name in ("start", "restart", "stop"):
        command = commands.add_parser(name, help=f"{name} one Preview Runtime")
        command.add_argument("--profile", type=Path, required=True)
        command.add_argument("--request-id", required=True)
        command.add_argument(
            "--expected-state",
            required=True,
            help="JSON projection reviewed immediately before this command",
        )
    server = commands.add_parser("serve", help=argparse.SUPPRESS)
    server.add_argument("--profile", type=Path, required=True)
    server.add_argument("--instance-id", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    try:
        if args.command == "validate-all":
            paths = validate_profiles(repo_root)
            output = {"status": "valid", "profile_count": len(paths), "profiles": paths}
        else:
            runtime = PreviewRuntime(repo_root, args.profile, args.state_root)
            if args.command == "serve":
                serve(runtime, args.instance_id)
                return 0
            if args.command == "status":
                output = runtime.projection()
            elif args.command == "proof":
                output = runtime.proof()
            else:
                try:
                    expected_state = json.loads(args.expected_state)
                except json.JSONDecodeError as error:
                    raise PreviewError(
                        "expected_state_invalid",
                        "expected state must be valid JSON",
                    ) from error
                output = runtime.command(args.command, args.request_id, expected_state)
    except (OSError, PreviewError) as error:
        code = error.code if isinstance(error, PreviewError) else "io_error"
        print(json.dumps({"status": "rejected", "code": code, "message": str(error)}, sort_keys=True))
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
