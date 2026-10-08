from __future__ import annotations

import copy
import json
import socket
import subprocess
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
    _assert_reviewed_checkout,
    _validate,
    _validator,
    validate_profiles,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = REPO_ROOT / "records/prototype-preview-profiles/client-review-portal.yaml"


def expected_state(runtime: PreviewRuntime) -> dict[str, object]:
    projection = runtime.projection()
    return {
        "instance_id": projection["instance_id"],
        "profile_digest": projection["profile_digest"],
        "runtime_state": projection["runtime_state"],
        "source_digest": projection["source_digest"],
        "source_revision": projection["source_revision"],
    }


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
                self.runtime.command(
                    "stop",
                    "test-cleanup-stop",
                    expected_state(self.runtime),
                )
        finally:
            self.temporary.cleanup()

    def test_lifecycle_is_receipt_bound_replay_safe_and_read_only_provable(self) -> None:
        stopped = expected_state(self.runtime)
        start = self.runtime.command("start", "test-start-001", stopped)
        self.assertEqual(start["status"], "applied")
        self.assertEqual(start["receipt"]["after_state"], "running")

        replay = self.runtime.command("start", "test-start-001", stopped)
        self.assertEqual(replay["status"], "replayed")
        self.assertEqual(replay["receipt"], start["receipt"])
        with self.assertRaisesRegex(PreviewError, "another command"):
            self.runtime.command("stop", "test-start-001", stopped)

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

        running = expected_state(self.runtime)
        stop = self.runtime.command("stop", "test-stop-001", running)
        self.assertEqual(stop["receipt"]["after_state"], "stopped")
        stop_replay = self.runtime.command("stop", "test-stop-001", running)
        self.assertEqual(stop_replay["status"], "replayed")
        self.assertEqual(stop_replay["receipt"], stop["receipt"])
        self.assertEqual(self.runtime.projection()["runtime_state"], "stopped")

    def test_tampered_receipt_is_rejected(self) -> None:
        expected = expected_state(self.runtime)
        self.runtime.command("start", "test-start-tamper", expected)
        request_path = self.runtime._request_path("test-start-tamper")
        receipt = json.loads(request_path.read_text(encoding="utf-8"))
        receipt["source_revision"] = "0" * 40
        request_path.write_text(json.dumps(receipt), encoding="utf-8")
        with self.assertRaisesRegex(PreviewError, "digest"):
            self.runtime.command("start", "test-start-tamper", expected)

    def test_invalid_request_id_is_rejected_before_mutation(self) -> None:
        with self.assertRaisesRegex(PreviewError, "request id"):
            self.runtime.command("start", "../unsafe", expected_state(self.runtime))
        self.assertEqual(self.runtime.projection()["runtime_state"], "stopped")

    def test_expected_state_is_checked_inside_the_owner_lock(self) -> None:
        stale = expected_state(self.runtime)
        self.runtime.command("start", "test-atomic-start", stale)
        with self.assertRaisesRegex(PreviewError, "changed after review"):
            self.runtime.command("stop", "test-atomic-stale-stop", stale)
        self.assertEqual(self.runtime.projection()["runtime_state"], "running")
        with self.assertRaisesRegex(PreviewError, "another command"):
            self.runtime.command(
                "start",
                "test-atomic-start",
                expected_state(self.runtime),
            )


class PrototypePreviewSourceCustodyTests(unittest.TestCase):
    def test_dirty_and_untracked_served_source_are_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo_root = Path(directory)
            source_root = repo_root / "prototypes/example"
            source_root.mkdir(parents=True)
            (source_root / "index.html").write_text("reviewed", encoding="utf-8")
            (repo_root / ".gitignore").write_text("*.ignored\n", encoding="utf-8")
            for args in (
                ["init", "-q"],
                ["config", "user.name", "Preview Test"],
                ["config", "user.email", "preview@example.invalid"],
                ["add", "."],
                ["commit", "-qm", "baseline"],
            ):
                subprocess.run(["git", *args], cwd=repo_root, check=True)
            _assert_reviewed_checkout(repo_root, source_root)

            (source_root / "index.html").write_text("dirty", encoding="utf-8")
            with self.assertRaisesRegex(PreviewError, "clean reviewed checkout"):
                _assert_reviewed_checkout(repo_root, source_root)
            subprocess.run(
                ["git", "restore", "prototypes/example/index.html"],
                cwd=repo_root,
                check=True,
            )

            (source_root / "hidden.ignored").write_text("not reviewed", encoding="utf-8")
            with self.assertRaisesRegex(PreviewError, "reviewed tracked files"):
                _assert_reviewed_checkout(repo_root, source_root)


if __name__ == "__main__":
    unittest.main()
