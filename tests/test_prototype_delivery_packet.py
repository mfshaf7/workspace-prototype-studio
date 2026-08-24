from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from packages.prototype_delivery_packet.packet import (
    PacketError,
    _reject_self_referential_provenance,
    emit_packet,
    validate_packet_file,
    validate_packet_records,
)


SOURCE_ROOT = Path(__file__).resolve().parents[1]


class PrototypeDeliveryPacketTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "workspace-prototype-studio"
        self.root.mkdir()
        (self.root / "schemas").mkdir()
        (self.root / "records/design-baselines").mkdir(parents=True)
        (self.root / "records/delivery-packets").mkdir(parents=True)
        for schema_name in (
            "design-baseline.schema.json",
            "prototype-registry.schema.json",
            "prototype-delivery-request.schema.json",
            "prototype-delivery-packet.schema.json",
        ):
            shutil.copy2(SOURCE_ROOT / "schemas" / schema_name, self.root / "schemas")

        self._git("init", "--initial-branch=main")
        self._git("config", "user.name", "Prototype Packet Test")
        self._git("config", "user.email", "prototype-packet@example.invalid")
        (self.root / "README.md").write_text("# Fixture\n", encoding="utf-8")
        self._commit("fixture base")
        self.base_commit = self._git("rev-parse", "HEAD")

        self.baseline_id = "sample-prototype-2026-08-25"
        self.baseline_ref = f"record://design-baselines/{self.baseline_id}"
        self.baseline = {
            "schema_version": 1,
            "prototype_id": "sample-prototype",
            "baseline_id": self.baseline_id,
            "approved_on": "2026-08-25",
            "approved_by": "operator:workspace-owner",
            "decision": "approved",
            "source_refs": ["repo://workspace-prototype-studio@fixture"],
            "evidence_refs": ["record://evidence/baseline-review"],
        }
        self.registry = {
            "schema_version": 1,
            "studio": {"owner_repo": "workspace-prototype-studio"},
            "prototypes": [
                {
                    "id": "sample-prototype",
                    "name": "Sample Prototype",
                    "portfolio": "experiment",
                    "lifecycle": "baseline-approved",
                    "owner": "Workspace Prototype Studio",
                    "visibility_tier": "private-internal",
                    "data_mode": "synthetic",
                    "mutation_boundary": "prototype-local",
                    "design_baseline_ref": self.baseline_ref,
                    "linked_records": [
                        {
                            "role": "baseline-record",
                            "ref": self.baseline_ref,
                            "system": "prototype-studio",
                            "level": "record",
                            "label": "Approved design baseline",
                        }
                    ],
                    "paths": {},
                }
            ],
        }
        self._write_yaml(self.root / "prototypes.yaml", self.registry)
        self._write_yaml(
            self.root / "records/design-baselines" / f"{self.baseline_id}.yaml",
            self.baseline,
        )
        self._commit("approved baseline")
        self.head_commit = self._git("rev-parse", "HEAD")
        self.request_path = Path(self.temporary_directory.name) / "request.yaml"
        self.request = self._request()
        self._write_yaml(self.request_path, self.request)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        )
        return result.stdout.strip()

    def _commit(self, message: str) -> None:
        self._git("add", ".")
        self._git("commit", "-m", message)

    @staticmethod
    def _write_yaml(path: Path, payload: dict) -> None:
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def _request(self) -> dict:
        return {
            "schema_version": 1,
            "prototype_id": "sample-prototype",
            "title": "Sample governed continuation",
            "objective": "Continue the approved prototype through governed Delivery.",
            "included_scope": ["Preserve the approved operator workflow."],
            "excluded_scope": ["Do not authorize production deployment."],
            "remaining_work": ["Wire the durable backend adapter."],
            "evidence_refs": ["record://evidence/preview-proof"],
            "custody": {
                "classification": "existing-repo",
                "repository_mode": "existing",
                "repository_gate_state": "resolved",
                "owner": "workspace-prototype-studio",
                "source_ref": "repo://workspace-prototype-studio@main",
                "rationale": "The governed source already has a durable repository.",
            },
            "authorization": {
                "decision": "approved",
                "operator_id": "operator:workspace-owner",
                "decision_ref": "record://prototype-decisions/sample-delivery-handoff",
            },
            "source_revision": {
                "repository": "workspace-prototype-studio",
                "ref": "refs/heads/main",
                "base_commit": self.base_commit,
                "head_commit": self.head_commit,
            },
            "rationale": "The baseline is approved and the remaining work needs governed delivery.",
        }

    def _emit(self):
        return emit_packet(self.root, self.request_path)

    def test_positive_emit_is_deterministic_and_replay_safe(self) -> None:
        first = self._emit()
        first_bytes = first.packet_path.read_bytes()
        second = self._emit()

        self.assertEqual("emitted", first.status)
        self.assertEqual("replayed", second.status)
        self.assertEqual(first.packet_ref, second.packet_ref)
        self.assertEqual(first.packet_digest, second.packet_digest)
        self.assertEqual(first_bytes, second.packet_path.read_bytes())
        self.assertEqual([first.packet_path], validate_packet_records(self.root))

        registry = yaml.safe_load((self.root / "prototypes.yaml").read_text())
        prototype = registry["prototypes"][0]
        self.assertEqual("graduating", prototype["lifecycle"])
        self.assertEqual(first.packet_ref, prototype["delivery_packet_ref"])
        self.assertEqual(
            [first.packet_ref],
            [
                record["ref"]
                for record in prototype["linked_records"]
                if record["role"] == "delivery-packet"
            ],
        )

    def test_packet_contains_complete_delivery_evidence_without_target_owned_fields(self) -> None:
        result = self._emit()
        packet = validate_packet_file(self.root, result.packet_path)
        content = packet["content"]

        self.assertEqual("workspace-delivery-art", content["target"])
        self.assertEqual(self.head_commit, content["source"]["record_version"])
        self.assertEqual(self.baseline_ref, content["baseline"]["record_ref"])
        self.assertEqual(
            {
                "record://evidence/baseline-review",
                "record://evidence/preview-proof",
            },
            set(content["evidence_refs"]),
        )
        serialized = json.dumps(packet)
        for target_owned_field in ("target_pi", "iteration", "delivery_team", "art_tree"):
            self.assertNotIn(target_owned_field, serialized)

    def test_malformed_or_custody_incomplete_request_fails_without_projection(self) -> None:
        malformed = copy.deepcopy(self.request)
        malformed["custody"]["repository_gate_state"] = "pending"
        self._write_yaml(self.request_path, malformed)

        with self.assertRaises(PacketError) as raised:
            self._emit()

        self.assertEqual("malformed_request", raised.exception.code)
        self.assertEqual([], list((self.root / "records/delivery-packets").glob("*.json")))
        registry = yaml.safe_load((self.root / "prototypes.yaml").read_text())
        self.assertEqual("baseline-approved", registry["prototypes"][0]["lifecycle"])

    def test_unapproved_request_fails_without_projection(self) -> None:
        unapproved = copy.deepcopy(self.request)
        unapproved["authorization"]["decision"] = "pending"
        self._write_yaml(self.request_path, unapproved)

        with self.assertRaises(PacketError) as raised:
            self._emit()

        self.assertEqual("malformed_request", raised.exception.code)
        self.assertEqual([], list((self.root / "records/delivery-packets").glob("*.json")))

    def test_projection_conflict_is_rejected_before_packet_write(self) -> None:
        registry = copy.deepcopy(self.registry)
        registry["prototypes"][0]["lifecycle"] = "candidate"
        self._write_yaml(self.root / "prototypes.yaml", registry)

        with self.assertRaises(PacketError) as raised:
            self._emit()

        self.assertEqual("source_projection_conflict", raised.exception.code)
        self.assertEqual([], list((self.root / "records/delivery-packets").glob("*.json")))

    def test_conflicting_packet_for_same_source_version_is_rejected(self) -> None:
        first = self._emit()
        changed = copy.deepcopy(self.request)
        changed["objective"] = "A conflicting objective against the same source revision."
        self._write_yaml(self.request_path, changed)

        with self.assertRaises(PacketError) as raised:
            self._emit()

        self.assertEqual("packet_conflict", raised.exception.code)
        self.assertEqual(1, len(list((self.root / "records/delivery-packets").glob("*.json"))))
        self.assertTrue(first.packet_path.exists())

    def test_stale_source_revision_is_rejected_before_output(self) -> None:
        (self.root / "README.md").write_text("# Fixture\n\nadvanced\n", encoding="utf-8")
        self._commit("advance source")

        with self.assertRaises(PacketError) as raised:
            self._emit()

        self.assertEqual("source_revision_stale", raised.exception.code)
        self.assertEqual([], list((self.root / "records/delivery-packets").glob("*.json")))

    def test_unrelated_base_commit_is_rejected(self) -> None:
        tree = self._git("rev-parse", f"{self.head_commit}^{{tree}}")
        orphan_commit = self._git("commit-tree", tree, "-m", "unrelated root")
        invalid = copy.deepcopy(self.request)
        invalid["source_revision"]["base_commit"] = orphan_commit
        self._write_yaml(self.request_path, invalid)

        with self.assertRaises(PacketError) as raised:
            self._emit()

        self.assertEqual("source_ancestry_invalid", raised.exception.code)

    def test_baseline_tamper_is_detected_after_emission(self) -> None:
        result = self._emit()
        baseline_path = self.root / "records/design-baselines" / f"{self.baseline_id}.yaml"
        tampered = copy.deepcopy(self.baseline)
        tampered["evidence_refs"].append("record://evidence/unbound-change")
        self._write_yaml(baseline_path, tampered)

        with self.assertRaises(PacketError) as raised:
            validate_packet_file(self.root, result.packet_path)

        self.assertEqual("baseline_binding_invalid", raised.exception.code)

    def test_self_referential_provenance_guard_rejects_packet_in_bound_commit(self) -> None:
        result = self._emit()
        self._commit("store packet")
        packet = json.loads(result.packet_path.read_text(encoding="utf-8"))
        packet["content"]["source"]["revision"]["head_commit"] = self._git("rev-parse", "HEAD")

        with self.assertRaises(PacketError) as raised:
            _reject_self_referential_provenance(self.root, packet)

        self.assertEqual("source_provenance_self_referential", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
