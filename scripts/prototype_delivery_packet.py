#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from packages.prototype_delivery_packet.packet import (  # noqa: E402
    PacketError,
    emit_packet,
    validate_packet_file,
    validate_packet_records,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit or validate Prototype Delivery packets")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)

    emit_parser = subparsers.add_parser("emit")
    emit_parser.add_argument("--request", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--packet", type=Path, required=True)

    subparsers.add_parser("validate-all")
    args = parser.parse_args()

    try:
        if args.command == "emit":
            result = emit_packet(args.repo_root, args.request)
            output = {
                "status": result.status,
                "packet_ref": result.packet_ref,
                "packet_digest": result.packet_digest,
                "packet_path": str(result.packet_path),
            }
        elif args.command == "validate":
            packet = validate_packet_file(args.repo_root, args.packet)
            output = {
                "status": "valid",
                "packet_ref": packet["packet_ref"],
                "packet_digest": packet["packet_digest"],
            }
        else:
            paths = validate_packet_records(args.repo_root)
            output = {
                "status": "valid",
                "packet_count": len(paths),
                "packet_paths": [str(path) for path in paths],
            }
    except PacketError as error:
        print(json.dumps({"status": "rejected", "code": error.code, "message": str(error)}))
        return 1

    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
