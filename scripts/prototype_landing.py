#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from packages.prototype_delivery_packet.contract import PacketError, load_json  # noqa: E402
from packages.prototype_landing.landing import (  # noqa: E402
    apply_landing,
    current_state,
    imported_content_digest,
    validate_landing_records,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare or validate Prototype Landing source")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    commands = parser.add_subparsers(dest="command", required=True)

    state = commands.add_parser("state", help="print current optimistic-concurrency bindings")
    state.add_argument("--prototype-id", required=True)

    digest = commands.add_parser("digest-import", help="print the bounded imported-content digest")
    digest.add_argument("--source", type=Path, required=True)

    apply = commands.add_parser("apply", help="prepare one ready Landing on the current review branch")
    for name in ("entry", "request", "plan", "readiness", "apply"):
        apply.add_argument(f"--{name}", type=Path, required=True)
    apply.add_argument("--output-dir", type=Path, required=True)
    apply.add_argument("--import-root", type=Path)

    commands.add_parser("validate-all", help="validate the synchronized contract and Landing records")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    repo_root = args.repo_root.resolve()
    try:
        if args.command == "state":
            output = current_state(repo_root, args.prototype_id)
        elif args.command == "digest-import":
            output = {"imported_content_digest": imported_content_digest(args.source.resolve())}
        elif args.command == "validate-all":
            paths = validate_landing_records(repo_root)
            output = {"status": "valid", "record_count": len(paths)}
        else:
            result = apply_landing(
                repo_root=repo_root,
                entry=load_json(args.entry.resolve()),
                request=load_json(args.request.resolve()),
                plan=load_json(args.plan.resolve()),
                readiness=load_json(args.readiness.resolve()),
                apply=load_json(args.apply.resolve()),
                output_dir=args.output_dir.resolve(),
                import_root=args.import_root.resolve() if args.import_root else None,
            )
            output = {
                "status": result.status,
                "prototype_id": result.prototype_id,
                "source_revision": result.source_revision,
                "readback_path": str(result.readback_path),
                "receipt_path": str(result.receipt_path),
            }
    except (OSError, PacketError) as error:
        code = error.code if isinstance(error, PacketError) else "io_error"
        print(json.dumps({"status": "rejected", "code": code, "message": str(error)}))
        return 1
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
