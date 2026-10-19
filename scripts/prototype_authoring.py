#!/usr/bin/env python3
"""Read-only owner planning adapter, not a source writer or model executor."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from packages.prototype_authoring import inspect_source, plan_preview  # noqa: E402
from packages.prototype_delivery_packet.contract import PacketError  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare bounded Prototype owner source plans without mutation")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect")
    inspect.add_argument("--prototype-id", required=True)
    inspect.add_argument("--source-revision", required=True)
    preview = commands.add_parser("plan-preview")
    preview.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "inspect":
            result = inspect_source(args.repo_root, args.prototype_id, args.source_revision)
        else:
            if args.request.stat().st_size > 16_384:
                raise PacketError("request_oversized", "Owner preparation request exceeds the source bound")
            result = plan_preview(args.repo_root, json.loads(args.request.read_text()))
        print(json.dumps(result, sort_keys=True))
    except (OSError, ValueError, PacketError) as error:
        print(json.dumps({"status": "rejected", "code": getattr(error, "code", "request_invalid"),
                          "message": "Prototype owner preparation was rejected"}))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
