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
from packages.prototype_closure.owner_evidence import (  # noqa: E402
    prepare_retention_plan,
    read_retained_source,
    read_retention_plan,
    validate_retention_plan_records,
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
    retention = commands.add_parser("prepare-retention", help="prepare a reviewed source-retention plan")
    retention.add_argument("--prototype-id", required=True)
    retention.add_argument("--operator-id", required=True)
    retention.add_argument("--reason", required=True)
    owner = commands.add_parser("owner-readback", help="read current committed Studio owner evidence")
    owner.add_argument("--field", choices=("retention_plan_ref", "retained_source_readback_ref"), required=True)
    owner.add_argument("--prototype-id", required=True)
    owner.add_argument("--source-revision", required=True)
    owner.add_argument("--ref")
    owner.add_argument("--operator-id")
    owner.add_argument("--reason")
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
        elif args.command == "prepare-retention":
            path, ref, plan = prepare_retention_plan(
                repo_root, args.prototype_id, args.operator_id, args.reason,
            )
            result = {"status": "source-prepared", "path": str(path), "ref": ref, "digest": content_digest(plan)}
        elif args.command == "owner-readback":
            if args.field == "retention_plan_ref":
                if not args.ref or not args.operator_id or not args.reason:
                    raise PacketError("retention_input_missing", "retention ref, operator, and reason are required")
                result = read_retention_plan(
                    repo_root, args.ref, args.source_revision, args.operator_id, args.reason,
                )
                if result["prototype_id"] != args.prototype_id:
                    raise PacketError("retention_ref_invalid", "retention plan binds another prototype")
            else:
                result = read_retained_source(
                    repo_root, args.prototype_id, args.source_revision, args.ref,
                )
        else:
            paths = validate_closure_records(repo_root)
            plans = validate_retention_plan_records(repo_root)
            result = {"status": "valid", "event_count": len(paths), "retention_plan_count": len(plans)}
    except PacketError as error:
        print(json.dumps({"status": "error", "code": error.code, "detail": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
