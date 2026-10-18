from __future__ import annotations

import copy
import hashlib
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
import urllib.error
import urllib.request
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

from packages.prototype_authoring import inspect_source, plan_preview
from packages.prototype_delivery_packet.contract import PacketError
from packages.prototype_preview.runtime import PreviewError, PreviewRuntime


ROOT = Path(__file__).resolve().parents[1]


class PrototypeAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "owner"
        self.root.mkdir()
        shutil.copyfile(ROOT / ".gitignore", self.root / ".gitignore")
        for directory in ("schemas", "packages", "scripts"):
            shutil.copytree(ROOT / directory, self.root / directory,
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        self.entry = {
            "id": "sample-tool", "name": "Synthetic test fixture", "lifecycle": "exploring",
            "project_phase": "incubating", "owner": "Workspace Prototype Studio",
            "source_custody": "incubation-repo", "visibility_tier": "operator-review",
            "data_mode": "synthetic", "mutation_boundary": "prototype-local",
            "paths": {"design_profile": "docs/prototypes/sample-tool/design-profile.md"},
        }
        self.registry = {"schema_version": 1, "studio": {}, "prototypes": [self.entry]}
        self._write_registry(self.registry)
        source = self.root / "prototypes/sample-tool"
        source.mkdir(parents=True)
        (source / "index.html").write_text("<p>Synthetic browser storage fixture, not a product.</p>")
        design = self.root / "docs/prototypes/sample-tool/design-profile.md"
        design.parent.mkdir(parents=True)
        design.write_text("# Synthetic design draft\nNo baseline approval.\n")
        other = self.root / "prototypes/other-tool"
        other.mkdir()
        (other / "unrelated.txt").write_text("must-not-be-captured")
        for args in (("init", "-q", "-b", "main"), ("config", "user.name", "Owner Fixture"),
                     ("config", "user.email", "owner@example.invalid")):
            self._git(*args)
        self._commit()

    def _git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.PIPE).decode().strip()

    def _commit(self):
        self._git("add", ".")
        self._git("commit", "-qm", "reviewed synthetic owner fixture")
        self.revision = self._git("rev-parse", "HEAD")

    def _write_registry(self, value):
        (self.root / "prototypes.yaml").write_text(yaml.safe_dump(value))

    def _request(self, **changes):
        return {"schema_version": 1, "prototype_id": "prototype:sample-tool",
                "source_revision": self.revision,
                "operator": {"id": "operator:fixture", "decision_ref": "record://decisions/synthetic-preview"},
                "port": 18499, "support_profile": "interactive", "runtime_activation": True,
                "ttl_seconds": 600, **changes}

    def _inspect(self):
        return inspect_source(self.root, "prototype:sample-tool", self.revision)

    def test_inspection_is_exact_readonly_and_scoped_to_one_prototype(self):
        result = self._inspect()
        self.assertEqual(result["subject"]["registry_revision"], self.revision)
        self.assertEqual(result["subject"]["source_revision"], self.revision)
        self.assertEqual(result["model_source_scope"]["source_root"], "prototypes/sample-tool")
        self.assertEqual([item["path"] for item in result["source_manifest"]],
                         ["prototypes/sample-tool/index.html"])
        self.assertNotIn("must-not-be-captured", json.dumps(result))
        self.assertTrue(all(value is False for value in result["authority"].values()))
        self.assertFalse(result["delivery_packet_preparation"]["readiness_evaluated"])
        self.assertEqual(result["delivery_packet_preparation"]["owner_command"], "scripts/prototype_delivery_packet.py")
        self.assertEqual(self._git("status", "--porcelain"), "")

    def test_preview_plan_is_deterministic_closed_and_does_not_write(self):
        request = self._request()
        first = plan_preview(self.root, request)
        self.assertEqual(first, plan_preview(self.root, request))
        self.assertEqual(first["status"], "preparation-only")
        self.assertEqual(len(first["changes"]), 1)
        change = first["changes"][0]
        self.assertEqual(change["path"], "records/prototype-preview-profiles/sample-tool.yaml")
        self.assertIsNone(change["expected_content_digest"])
        self.assertFalse((self.root / change["path"]).exists())
        profile = yaml.safe_load(change["content"])
        self.assertEqual(profile["boundary"]["persistence_model"], "browser-local")
        self.assertEqual(profile["runtime"]["source_root"], "prototypes/sample-tool")
        self.assertTrue(all(value is False for value in first["authority"].values()))
        self.assertEqual(self._git("status", "--porcelain"), "")

    def test_existing_inert_draft_digest_is_bound_not_overwritten(self):
        path = self.root / "records/prototype-preview-profiles/sample-tool.yaml"
        path.parent.mkdir(parents=True)
        original = "schema_version: 1\nprototype_id: prototype:sample-tool\nstatus: draft\nsupport_profile: interactive\npreview_mode: static\nruntime_activation: false\n"
        path.write_text(original)
        self._commit()
        plan = plan_preview(self.root, self._request(runtime_activation=False))
        self.assertEqual(plan["changes"][0]["expected_content_digest"],
                         "sha256:" + hashlib.sha256(original.encode()).hexdigest())
        self.assertEqual(path.read_text(), original)
        profile = yaml.safe_load(plan["changes"][0]["content"])
        self.assertFalse(profile["runtime_activation"])
        self.assertEqual(profile["status"], "draft")

    def test_unknown_dirty_stale_and_ambiguous_sources_are_denied(self):
        for prototype, revision in (("prototype:unknown-tool", self.revision),
                                    ("prototype:sample-tool", "0" * 40),
                                    ("prototype:sample-tool", "main")):
            with self.subTest(prototype=prototype, revision=revision), self.assertRaises(PacketError):
                inspect_source(self.root, prototype, revision)
        (self.root / "prototypes/sample-tool/index.html").write_text("not reviewed")
        with self.assertRaises(PacketError) as caught:
            self._inspect()
        self.assertEqual(caught.exception.code, "dirty_worktree")
        self._commit()
        duplicate = copy.deepcopy(self.registry)
        duplicate["prototypes"].append(copy.deepcopy(self.entry))
        self._write_registry(duplicate)
        self._commit()
        with self.assertRaises(PacketError) as caught:
            self._inspect()
        self.assertEqual(caught.exception.code, "prototype_unknown")

    def test_closed_input_cannot_supply_source_paths_policy_or_credentials(self):
        cases = [self._request(source_root="prototypes/other-tool"),
                 self._request(profile={"public_ingress": True}),
                 self._request(port=80), self._request(runtime_activation="true"),
                 self._request(operator={"id": "operator:fixture", "decision_ref": "record://decisions/fixture", "token": "private-test-marker"})]
        for request in cases:
            with self.subTest(request=request), self.assertRaises(PacketError) as caught:
                plan_preview(self.root, request)
            self.assertEqual(caught.exception.code, "authoring_contract_invalid")
            self.assertNotIn("private-test-marker", str(caught.exception))
        self.assertEqual(self._git("status", "--porcelain"), "")

    def test_custody_phase_design_and_data_boundaries_are_not_inferred(self):
        cases = [("source_custody", "dedicated-owner-repo"), ("project_phase", "operational"),
                 ("lifecycle", "graduated"), ("paths", {"design_profile": "docs/prototypes/other-tool/design-profile.md"}),
                 ("paths", []), ("data_mode", "real-readonly"), ("mutation_boundary", "real-system")]
        for key, value in cases:
            registry = copy.deepcopy(self.registry)
            registry["prototypes"][0][key] = value
            self._write_registry(registry)
            self._commit()
            with self.subTest(field=key), self.assertRaises(PacketError):
                plan_preview(self.root, self._request())

    def test_landing_custody_supports_registry_without_legacy_custody_field(self):
        registry = copy.deepcopy(self.registry)
        del registry["prototypes"][0]["source_custody"]
        self._write_registry(registry)
        landing = self.root / "records/prototype-landings/sample-tool/record.json"
        landing.parent.mkdir(parents=True)
        record = {"id": "prototype:sample-tool", "source": {"custody": "incubation-repo",
                  "ref": "repo://workspace-prototype-studio/prototypes/sample-tool"}}
        landing.write_text(json.dumps(record))
        self._commit()
        self.assertEqual(self._inspect()["subject"]["prototype_id"], "prototype:sample-tool")
        record["source"]["ref"] = "repo://different-owner/app"
        landing.write_text(json.dumps(record))
        self._commit()
        with self.assertRaises(PacketError):
            self._inspect()

    def test_symlink_or_secret_source_is_not_projected(self):
        path = self.root / "prototypes/sample-tool/unsafe-link"
        path.symlink_to("../../prototypes/other-tool/unrelated.txt")
        self._commit()
        with self.assertRaises(PacketError) as caught:
            self._inspect()
        self.assertEqual(caught.exception.code, "source_scope_denied")
        path.unlink()
        (path.parent / ".env").write_text("API_TOKEN=private-test-marker")
        self._commit()
        # Ignored local content is not read from disk into committed context.
        self.assertNotIn("private-test-marker", json.dumps(self._inspect()))
        (path.parent / "credentials.json").write_text("private-test-marker")
        self._commit()
        with self.assertRaises(PacketError) as caught:
            self._inspect()
        self.assertNotIn("private-test-marker", str(caught.exception))

    def test_boundary_pairs_and_committed_port_conflicts_are_explicit(self):
        profile = yaml.safe_load(plan_preview(self.root, self._request())["changes"][0]["content"])
        validator = Draft202012Validator(json.loads((self.root / "schemas/prototype-preview-profile.schema.json").read_text()))
        validator.validate(profile)
        for mutation, persistence in (("none", "browser-local"), ("prototype-local", "runtime-metadata-only")):
            value = copy.deepcopy(profile)
            value["boundary"].update(mutation_boundary=mutation, persistence_model=persistence)
            self.assertFalse(validator.is_valid(value))
        other = copy.deepcopy(profile)
        other.update(profile_id="other-tool", prototype_id="prototype:other-tool")
        path = self.root / "records/prototype-preview-profiles/other-tool.yaml"
        path.parent.mkdir(parents=True)
        path.write_text(yaml.safe_dump(other))
        self._commit()
        with self.assertRaises(PacketError) as caught:
            plan_preview(self.root, self._request())
        self.assertEqual(caught.exception.code, "preview_port_conflict")

    def test_actual_loopback_runtime_denies_http_writes_without_claiming_browser_proof(self):
        with socket.socket() as socket_probe:
            socket_probe.bind(("127.0.0.1", 0))
            port = socket_probe.getsockname()[1]
        plan = plan_preview(self.root, self._request(port=port))
        change = plan["changes"][0]
        path = self.root / change["path"]
        path.parent.mkdir(parents=True)
        path.write_text(change["content"])
        self._commit()
        runtime = PreviewRuntime(self.root, path, Path(self.temporary.name) / "state")
        def expected():
            projection = runtime.projection()
            return {key: projection[key] for key in ("instance_id", "profile_digest", "runtime_state", "source_digest", "source_revision")}
        try:
            runtime.command("start", "fixture-start", expected())
            proof = runtime.proof()
            self.assertTrue(proof["negative_checks"]["server_mutation_denied"])
            self.assertFalse(proof["browser_persistence"]["cleared_by_stop"])
            self.assertFalse(proof["browser_persistence"]["browser_operation_proven"])
            self.assertEqual(proof["browser_persistence"]["network_isolation_claim"], "not-a-general-browser-sandbox")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/index.html", timeout=2) as response:
                self.assertIn("connect-src 'none'", response.headers["Content-Security-Policy"])
                self.assertIn(b"Synthetic browser storage fixture", response.read())
            request = urllib.request.Request(f"http://127.0.0.1:{port}/index.html", data=b"not-a-write", method="POST")
            with self.assertRaises(urllib.error.HTTPError) as denied:
                urllib.request.urlopen(request, timeout=2)
            self.assertEqual(denied.exception.code, 405)
            self.assertEqual(self._git("status", "--porcelain"), "")
        finally:
            if runtime.projection()["runtime_state"] == "running":
                runtime.command("stop", "fixture-stop", expected())

    def test_runtime_and_repository_validation_share_registry_and_source_scope(self):
        plan = plan_preview(self.root, self._request())
        profile = yaml.safe_load(plan["changes"][0]["content"])
        path = self.root / plan["changes"][0]["path"]
        path.parent.mkdir(parents=True)
        for source in ("prototypes/other-tool", "prototypes/sample-tool/../other-tool"):
            value = copy.deepcopy(profile)
            value["runtime"]["source_root"] = source
            path.write_text(yaml.safe_dump(value))
            self._commit()
            with self.subTest(source=source), self.assertRaises(PreviewError):
                PreviewRuntime(self.root, path, Path(self.temporary.name) / "state")

    def test_cli_is_thin_readonly_and_errors_do_not_echo_input(self):
        request = Path(self.temporary.name) / "request.json"
        request.write_text(json.dumps(self._request()))
        command = [sys.executable, str(self.root / "scripts/prototype_authoring.py"),
                   "--repo-root", str(self.root), "plan-preview", "--request", str(request)]
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout), plan_preview(self.root, self._request()))
        request.write_text(json.dumps(self._request(token="private-test-marker")))
        denied = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(denied.returncode, 1)
        self.assertNotIn("private-test-marker", denied.stdout + denied.stderr)
        self.assertEqual(self._git("status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()
