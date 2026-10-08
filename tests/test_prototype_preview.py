from __future__ import annotations

import copy
import json
import socket
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import yaml

from packages.prototype_preview.runtime import (
    PROFILE_SCHEMA,
    PreviewError,
    PreviewRuntime,
    _validate,
    _validator,
    validate_profiles,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPO_ROOT / "records/prototype-preview-profiles/client-review-portal.yaml"


class PrototypePreviewProfileTests(unittest.TestCase):
    def test_repository_profiles_are_valid_and_registry_bound(self) -> None:
        self.assertEqual(
            validate_profiles(REPO_ROOT),
            ["records/prototype-preview-profiles/client-review-portal.yaml"],
        )

    def test_profile_schema_denies_boundary_expansion(self) -> None:
        profile = yaml.safe_load(PROFILE_PATH.read_text(encoding="utf-8"))
        validator = _validator(REPO_ROOT, PROFILE_SCHEMA)
        denied = {
            "runtime.bind_host": ("runtime", "bind_host", "0.0.0.0"),
            "boundary.public_ingress": ("boundary", "public_ingress", True),
            "boundary.external_network": ("boundary", "external_network", True),
            "boundary.data_mode": ("boundary", "data_mode", "real-readonly"),
            "boundary.mutation_boundary": ("boundary", "mutation_boundary", "prototype-local"),
        }
        for label, (section, field, value) in denied.items():
            with self.subTest(label=label):
                candidate = copy.deepcopy(profile)
                candidate[section][field] = value
                with self.assertRaises(PreviewError):
                    _validate(validator, candidate, label)


class PrototypePreviewRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", 18191)) == 0:
                self.skipTest("the repository Preview Runtime port is already in use")
        self.temporary = tempfile.TemporaryDirectory()
        self.state_root = Path(self.temporary.name)
        self.runtime = PreviewRuntime(REPO_ROOT, PROFILE_PATH, self.state_root)

    def tearDown(self) -> None:
        try:
            projection = self.runtime.projection()
            if projection["runtime_state"] == "running":
                self.runtime.command("stop", "test-cleanup-stop")
        finally:
            self.temporary.cleanup()

    def test_lifecycle_is_receipt_bound_replay_safe_and_read_only_provable(self) -> None:
        start = self.runtime.command("start", "test-start-001")
        self.assertEqual(start["status"], "applied")
        self.assertEqual(start["receipt"]["after_state"], "running")

        replay = self.runtime.command("start", "test-start-001")
        self.assertEqual(replay["status"], "replayed")
        self.assertEqual(replay["receipt"], start["receipt"])
        with self.assertRaisesRegex(PreviewError, "another command"):
            self.runtime.command("stop", "test-start-001")

        projection = self.runtime.projection()
        self.assertEqual(projection["runtime_state"], "running")
        self.assertEqual(projection["maturity_claim"], "prototype-preview-only")
        self.assertEqual(projection["endpoint"], "http://127.0.0.1:18191")
        self.assertFalse(projection["boundary"]["public_ingress"])

        proof = self.runtime.proof()
        self.assertEqual(proof["status"], "proven")
        self.assertTrue(all(proof["negative_checks"].values()))
        self.assertEqual(
            proof["security_gate"],
            "gate:preview-runtime-operating-acceptance",
        )

        with urllib.request.urlopen("http://127.0.0.1:18191/README.md", timeout=2) as response:
            self.assertIn(b"Client Review Portal Concept", response.read())
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        for denied_path in ("/../.git/config", "/.hidden", "/"):
            with self.subTest(path=denied_path):
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(f"http://127.0.0.1:18191{denied_path}", timeout=2)
                self.assertEqual(denied.exception.code, 404)

        stop = self.runtime.command("stop", "test-stop-001")
        self.assertEqual(stop["receipt"]["after_state"], "stopped")
        stop_replay = self.runtime.command("stop", "test-stop-001")
        self.assertEqual(stop_replay["status"], "replayed")
        self.assertEqual(stop_replay["receipt"], stop["receipt"])
        self.assertEqual(self.runtime.projection()["runtime_state"], "stopped")

    def test_tampered_receipt_is_rejected(self) -> None:
        self.runtime.command("start", "test-start-tamper")
        request_path = self.runtime._request_path("test-start-tamper")
        receipt = json.loads(request_path.read_text(encoding="utf-8"))
        receipt["source_revision"] = "0" * 40
        request_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(PreviewError, "digest"):
            self.runtime.command("start", "test-start-tamper")

    def test_invalid_request_id_is_rejected_before_mutation(self) -> None:
        with self.assertRaisesRegex(PreviewError, "request id"):
            self.runtime.command("start", "../unsafe")
        self.assertEqual(self.runtime.projection()["runtime_state"], "stopped")


if __name__ == "__main__":
    unittest.main()
