#!/usr/bin/env python3
"""Read-only Prototype candidate adapter for Workspace Intake."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from packages.prototype_delivery_packet.contract import PacketError, load_json
from packages.prototype_intake_candidate.candidate import build_candidate, validate_candidate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    actions = parser.add_subparsers(dest="action", required=True)
    emit = actions.add_parser("emit", help="emit one candidate as JSON; no source mutation")
    emit.add_argument("--request", type=Path, required=True)
    validate = actions.add_parser("validate", help="validate JSON against committed source")
    validate.add_argument("--candidate", type=Path, required=True)
    validate.add_argument("--historical", action="store_true", help="verify retained evidence, not current submission readiness")
    args = parser.parse_args()
    try:
        if args.action == "emit":
            result = build_candidate(args.repo_root, load_json(args.request))
        else:
            result = validate_candidate(args.repo_root, load_json(args.candidate), historical=args.historical)
    except PacketError as error:
        # Do not echo submitted content, local paths or Git diagnostics into callers' logs.
        print(json.dumps({"error": error.code, "canonical_mutation": False}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
