#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from packages.proposal_target_application.application import (  # noqa: E402
    apply_application,
    current_state,
    validate_capture_records,
)
from packages.prototype_delivery_packet.contract import PacketError, load_json  # noqa: E402


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Apply an accepted Proposal to Prototype Studio capture")
    result.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    commands = result.add_subparsers(dest="command", required=True)
    state = commands.add_parser("state", help="print current optimistic-concurrency bindings")
    state.add_argument("--prototype-id", required=True)
    apply = commands.add_parser("apply", help="create or replay one captured exploring Prototype")
    apply.add_argument("--request", type=Path, required=True)
    apply.add_argument("--output", type=Path, required=True)
    commands.add_parser("validate-all", help="validate target contracts and committed capture records")
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        if args.command == "state":
            output = current_state(args.repo_root, args.prototype_id)
        elif args.command == "validate-all":
            paths = validate_capture_records(args.repo_root)
            output = {"status": "valid", "record_count": len(paths)}
        else:
            applied = apply_application(
                repo_root=args.repo_root,
                request=load_json(args.request),
                output_path=args.output,
            )
            output = {
                "status": applied.status,
                "prototype_id": applied.prototype_id,
                "target_record_ref": applied.target_record_ref,
                "source_revision": applied.source_revision,
                "result_path": str(applied.result_path),
            }
    except (OSError, PacketError) as error:
        code = error.code if isinstance(error, PacketError) else "io_error"
        print(json.dumps({"status": "rejected", "code": code, "message": str(error)}))
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
