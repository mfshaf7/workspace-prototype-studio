#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from packages.prototype_closure.closure import (  # noqa: E402
    prepare_transition,
    readback_transition,
    validate_closure_records,
)
from packages.prototype_delivery_packet.contract import PacketError, content_digest, load_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Prototype Closure Studio source authority")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="prepare a reviewable Studio source transition")
    prepare.add_argument("--request", type=Path, required=True)
    prepare.add_argument("--resolved-authority", type=Path, required=True)
    readback = commands.add_parser("readback", help="inspect a merged Studio transition")
    readback.add_argument("--event", type=Path, required=True)
    commands.add_parser("validate-all", help="validate Studio Closure source history")
    args = parser.parse_args()

    try:
        repo_root = args.repo_root.resolve()
        if args.command == "prepare":
            path, event = prepare_transition(
                repo_root,
                load_json(args.request),
                load_json(args.resolved_authority),
            )
            result = {
                "event_path": str(path),
                "event_id": event["event_id"],
                "event_digest": content_digest(event),
                "status": "source-prepared",
            }
        elif args.command == "readback":
            result = readback_transition(repo_root, args.event)
        else:
            paths = validate_closure_records(repo_root)
            result = {"status": "valid", "event_count": len(paths)}
    except PacketError as error:
        print(json.dumps({"status": "error", "code": error.code, "detail": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
