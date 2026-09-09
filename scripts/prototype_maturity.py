#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from packages.prototype_delivery_packet.contract import PacketError, load_json  # noqa: E402
from packages.prototype_maturity.maturity import (  # noqa: E402
    apply_maturity,
    current_state,
    readback_maturity,
    validate_maturity_records,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or read Prototype maturity source")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)

    state = commands.add_parser("state", help="print current optimistic-concurrency bindings")
    state.add_argument("--prototype-id", required=True)

    apply = commands.add_parser("apply", help="prepare one reviewed maturity decision")
    for name in ("request", "packet", "readiness", "decision"):
        apply.add_argument(f"--{name}", type=Path, required=True)
    apply.add_argument("--output", type=Path, required=True)

    readback = commands.add_parser("readback", help="read merged or unchanged source authority")
    readback.add_argument("--decision", type=Path, required=True)
    readback.add_argument("--output", type=Path, required=True)

    commands.add_parser("validate-all", help="validate the synchronized contract and maturity records")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    try:
        if args.command == "state":
            output = current_state(repo_root, args.prototype_id)
        elif args.command == "validate-all":
            paths = validate_maturity_records(repo_root)
            output = {"status": "valid", "record_count": len(paths)}
        elif args.command == "readback":
            artifact = readback_maturity(
                repo_root=repo_root,
                decision=load_json(args.decision.resolve()),
                output_path=args.output.resolve(),
            )
            output = {
                "status": "observed",
                "prototype_id": artifact["prototype_id"],
                "source_revision": artifact["source_revision"],
                "readback_path": str(args.output.resolve()),
            }
        else:
            result = apply_maturity(
                repo_root=repo_root,
                request=load_json(args.request.resolve()),
                packet=load_json(args.packet.resolve()),
                readiness=load_json(args.readiness.resolve()),
                decision=load_json(args.decision.resolve()),
                output_path=args.output.resolve(),
            )
            output = {
                "status": result.status,
                "prototype_id": result.prototype_id,
                "source_revision": result.source_revision,
                "source_result_path": str(result.source_result_path),
            }
    except (OSError, PacketError) as error:
        code = error.code if isinstance(error, PacketError) else "io_error"
        print(json.dumps({"status": "rejected", "code": code, "message": str(error)}))
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
