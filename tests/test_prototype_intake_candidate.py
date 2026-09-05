from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from packages.prototype_delivery_packet.contract import PacketError, content_digest
from packages.prototype_intake_candidate.candidate import build_candidate, validate_candidate


SOURCE_ROOT = Path(__file__).resolve().parents[1]


class PrototypeIntakeCandidateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "studio"
        self.root.mkdir()
        shutil.copytree(SOURCE_ROOT / "schemas", self.root / "schemas")
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Candidate Test")
        self.git("config", "user.email", "candidate@example.invalid")
        self.baseline = {
            "schema_version": 1, "prototype_id": "sample-app", "baseline_id": "sample-approved",
            "approved_on": "2026-09-05", "approved_by": "operator:reviewer", "decision": "approved",
            "source_refs": ["repo://workspace-prototype-studio"],
            "evidence_refs": ["record://evidence/sample-review"],
        }
        self.prototype = {
            "id": "sample-app", "name": "Sample App", "portfolio": "experiment",
            "lifecycle": "baseline-approved", "owner": "Prototype Studio",
            "visibility_tier": "private-internal", "data_mode": "synthetic",
            "mutation_boundary": "prototype-local", "paths": {},
            "design_baseline_ref": "record://design-baselines/sample-approved",
            "linked_records": [{"role": "baseline-record", "ref": "record://design-baselines/sample-approved",
                                "system": "prototype-studio", "level": "record", "label": "Baseline"}],
        }
        self.registry = {"schema_version": 1, "studio": {"owner_repo": "workspace-prototype-studio"},
                         "prototypes": [self.prototype]}
        self.commit_source()
        self.request = {
            "schema_version": 1, "prototype_id": "sample-app",
            "source_revision": {"repository": "workspace-prototype-studio", "ref": "refs/heads/main",
                                "base_commit": self.git("rev-parse", "HEAD"), "head_commit": self.git("rev-parse", "HEAD")},
            "suggested_target": {"kind": "product", "name": "sample-product"},
            "rationale": "Classify the approved prototype as a workspace entrant.",
        }

    def git(self, *args: str) -> str:
        return subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True).stdout.strip()

    def commit_source(self) -> None:
        (self.root / "prototypes.yaml").write_text(yaml.safe_dump(self.registry), encoding="utf-8")
        baseline = self.root / "records/design-baselines/sample-approved.yaml"
        baseline.parent.mkdir(parents=True, exist_ok=True)
        baseline.write_text(yaml.safe_dump(self.baseline), encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "--allow-empty", "-m", "Source baseline")

    def cli(self, action: str, payload: dict, *extra: str) -> subprocess.CompletedProcess:
        path = Path(self.temporary.name) / "input.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        return subprocess.run([
            sys.executable, str(SOURCE_ROOT / "scripts/prototype_intake_candidate.py"),
            "--repo-root", str(self.root), action,
            "--request" if action == "emit" else "--candidate", str(path), *extra,
        ], capture_output=True, text=True)

    def assert_code(self, code: str, operation, *args, **kwargs) -> None:
        with self.assertRaises(PacketError) as caught:
            operation(*args, **kwargs)
        self.assertEqual(code, caught.exception.code)

    def test_cli_emit_validate_replay_and_cancel_before_submission_do_not_mutate(self) -> None:
        before = self.git("rev-parse", "HEAD"), (self.root / "prototypes.yaml").read_bytes()
        first = self.cli("emit", self.request)
        self.assertEqual(0, first.returncode, first.stderr)
        candidate = json.loads(first.stdout)
        result = self.cli("validate", candidate)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("prototype", json.loads(result.stdout)["source"]["class"])
        # Dropping an unsubmitted candidate is cancellation here: no lifecycle to unwind.
        second = self.cli("emit", self.request)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual("source-candidate-only", candidate["content"]["authority"])
        self.assertEqual(before, (self.git("rev-parse", "HEAD"), (self.root / "prototypes.yaml").read_bytes()))
        self.assertEqual("", self.git("status", "--porcelain"))

    def test_all_entrant_kinds_and_renaming_preserve_source_identity(self) -> None:
        original = build_candidate(self.root, self.request)
        for kind in ("repo", "product", "component"):
            request = copy.deepcopy(self.request)
            request["suggested_target"] = {"kind": kind, "name": "different-name"}
            candidate = build_candidate(self.root, request)
            self.assertEqual(original["content"]["source"], candidate["content"]["source"])
            self.assertNotEqual(original["candidate_digest"], candidate["candidate_digest"])
        self.prototype["name"] = "Renamed Prototype"
        self.commit_source()
        self.request["source_revision"]["head_commit"] = self.git("rev-parse", "HEAD")
        renamed = build_candidate(self.root, self.request)
        self.assertEqual(original["content"]["source"]["record_ref"], renamed["content"]["source"]["record_ref"])
        self.assertEqual(original["content"]["baseline"], renamed["content"]["baseline"])
        self.assertEqual("Renamed Prototype", renamed["content"]["source"]["name"])

    def test_stale_source_rejected_but_historical_evidence_remains_verifiable(self) -> None:
        candidate = build_candidate(self.root, self.request)
        self.commit_source()
        self.assert_code("source_revision_stale", validate_candidate, self.root, candidate)
        result = self.cli("validate", candidate, "--historical")
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual("historical", json.loads(result.stdout)["mode"])

    def test_recomputed_tampering_and_authority_claims_are_rejected(self) -> None:
        original = build_candidate(self.root, self.request)
        for field, value in (("name", "Forged"), ("owner", "Forged"), ("record_version", "a" * 40)):
            candidate = copy.deepcopy(original)
            candidate["content"]["source"][field] = value
            digest = content_digest(candidate["content"])
            candidate["candidate_digest"] = digest
            candidate["candidate_ref"] = "record://intake-candidates/" + digest[7:]
            self.assert_code("candidate_source_mismatch", validate_candidate, self.root, candidate)
        for extra in ("classification", "owner_route", "active_inventory", "governance_console"):
            candidate = copy.deepcopy(original)
            candidate["content"][extra] = "admitted"
            self.assert_code("candidate_invalid", validate_candidate, self.root, candidate)

    def test_incomplete_or_injected_input_is_rejected_by_real_cli(self) -> None:
        for mutate in (
            lambda r: r.pop("rationale"),
            lambda r: r.update(rationale="   "),
            lambda r: r.update(classification="admitted"),
            lambda r: r["source_revision"].update(ref="--output=secret"),
            lambda r: r["source_revision"].update(repository="another-repo"),
        ):
            request = copy.deepcopy(self.request)
            mutate(request)
            result = self.cli("emit", request)
            self.assertEqual(1, result.returncode)
            self.assertEqual("", result.stdout)
            self.assertEqual("candidate_input_invalid", json.loads(result.stderr)["error"])
            self.assertNotIn("secret", result.stderr)

    def test_lifecycle_matrix_and_approval_binding(self) -> None:
        for lifecycle in ("exploring", "candidate", "graduated", "retired", "graduating"):
            self.prototype["lifecycle"] = lifecycle
            self.commit_source()
            self.request["source_revision"]["head_commit"] = self.git("rev-parse", "HEAD")
            self.assert_code("source_record_invalid" if lifecycle == "graduating" else "lifecycle_not_eligible",
                             build_candidate, self.root, self.request)
        self.prototype["delivery_packet_ref"] = "record://delivery-packets/sample-packet"
        self.commit_source()
        self.request["source_revision"]["head_commit"] = self.git("rev-parse", "HEAD")
        self.assertEqual("graduating", build_candidate(self.root, self.request)["content"]["source"]["lifecycle"])
        for decision in ("rejected", "superseded"):
            self.baseline["decision"] = decision
            self.commit_source()
            self.request["source_revision"]["head_commit"] = self.git("rev-parse", "HEAD")
            self.assert_code("baseline_not_approved", build_candidate, self.root, self.request)

    def test_fixture_only_changes_and_duplicate_source_ids_cannot_supply_truth(self) -> None:
        original = build_candidate(self.root, self.request)
        self.prototype["name"] = "Uncommitted fixture"
        (self.root / "prototypes.yaml").write_text(yaml.safe_dump(self.registry), encoding="utf-8")
        self.assertEqual(original, build_candidate(self.root, self.request))
        request = copy.deepcopy(self.request)
        request["prototype_id"] = "not-committed"
        self.assert_code("prototype_identity_invalid", build_candidate, self.root, request)
        self.registry["prototypes"].append(copy.deepcopy(self.prototype))
        self.commit_source()
        self.request["source_revision"]["head_commit"] = self.git("rev-parse", "HEAD")
        self.assert_code("prototype_identity_invalid", build_candidate, self.root, self.request)

    def test_unrelated_git_ancestry_is_rejected(self) -> None:
        self.git("checkout", "--orphan", "unrelated")
        self.git("commit", "-m", "Unrelated root")
        self.request["source_revision"]["base_commit"] = self.git("rev-parse", "HEAD")
        self.assert_code("source_ancestry_invalid", build_candidate, self.root, self.request)

    def test_baseline_identity_and_path_cannot_be_substituted(self) -> None:
        self.baseline["prototype_id"] = "another-prototype"
        self.commit_source()
        self.request["source_revision"]["head_commit"] = self.git("rev-parse", "HEAD")
        self.assert_code("baseline_binding_invalid", build_candidate, self.root, self.request)
        self.prototype["design_baseline_ref"] = "record://design-baselines/../../private"
        self.commit_source()
        self.request["source_revision"]["head_commit"] = self.git("rev-parse", "HEAD")
        self.assert_code("baseline_binding_invalid", build_candidate, self.root, self.request)

    def test_foreign_registry_owner_does_not_gain_source_authority(self) -> None:
        self.registry["studio"]["owner_repo"] = "another-repo"
        self.commit_source()
        self.request["source_revision"]["head_commit"] = self.git("rev-parse", "HEAD")
        self.assert_code("source_repository_mismatch", build_candidate, self.root, self.request)


if __name__ == "__main__":
    unittest.main()
