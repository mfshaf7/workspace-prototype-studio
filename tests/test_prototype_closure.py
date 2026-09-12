from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from packages.prototype_closure.closure import (
    prepare_transition,
    readback_transition,
    validate_closure_records,
    validate_contract_bundle,
)
from packages.prototype_delivery_packet.contract import PacketError, content_digest, load_yaml


SOURCE_ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-12T12:00:00Z"


class PrototypeClosureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "studio"
        self.root.mkdir()
        shutil.copytree(SOURCE_ROOT / "contracts" / "prototype-closure", self.root / "contracts" / "prototype-closure")
        shutil.copytree(SOURCE_ROOT / "schemas", self.root / "schemas")
        self._write_registry({
            "schema_version": 1,
            "studio": {"owner_repo": "workspace-prototype-studio"},
            "prototypes": [{
                "id": "sample",
                "name": "Sample",
                "lifecycle": "baseline-approved",
                "project_phase": "incubating",
                "owner": "Workspace Prototype Studio",
                "visibility_tier": "private-internal",
                "data_mode": "synthetic",
                "mutation_boundary": "none",
                "design_baseline_ref": "record://design-baselines/sample",
                "delivery_packet_ref": "record://delivery-packets/sample",
                "paths": {},
            }],
        })
        self.git("init", "-b", "main")
        self.git("config", "user.email", "closure-test@example.invalid")
        self.git("config", "user.name", "Closure Test")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("switch", "-c", "feature/closure")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True, text=True)
        return result.stdout.strip()

    def _write_registry(self, payload: dict) -> None:
        (self.root / "prototypes.yaml").write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def item(self) -> dict:
        return load_yaml(self.root / "prototypes.yaml")["prototypes"][0]

    def request(self, action: str, **extra: str) -> dict:
        request = {
            "schema_version": 2,
            "artifact_type": "prototype-closure-request",
            "request_id": f"closure-request-{action}-{self.git('rev-parse', '--short', 'HEAD')}",
            "prototype_id": "sample",
            "action": action,
            "expected_lifecycle": self.item()["lifecycle"],
            "expected_source_revision": self.git("rev-parse", "HEAD"),
            "operator_id": "operator:test",
            "correlation_id": "test-closure",
            "idempotency_key": f"closure-{action}-{self.git('rev-parse', '--short', 'HEAD')}",
        }
        request.update(extra)
        return request

    def resolved(self, request: dict, **extra: str) -> dict:
        result = {
            "artifact_type": "prototype-closure-resolved-authority",
            "issuer": "operator-orchestration-service",
            "request_digest": content_digest(request),
        }
        result.update(extra)
        return result

    def apply_delivery(self) -> tuple[Path, dict]:
        request = self.request(
            "apply-delivery",
            accepted_baseline_receipt_ref="receipt://baseline/sample",
            target_kind="new-delivery-epic",
        )
        return prepare_transition(
            self.root,
            request,
            self.resolved(
                request,
                accepted_delivery_target_receipt_ref="receipt://delivery/sample",
                target_delivery_ref="openproject://work_packages/1200",
            ),
            recorded_at=NOW,
        )

    def test_delivery_acceptance_changes_phase_but_not_custody(self) -> None:
        validate_contract_bundle(self.root)
        path, event = self.apply_delivery()
        self.assertEqual("graduating", self.item()["lifecycle"])
        self.assertEqual("delivery-governed", self.item()["project_phase"])
        self.assertEqual("incubation-repo", self.item()["source_custody"])
        self.assertEqual("receipt://delivery/sample", event["accepted_delivery_target_receipt_ref"])
        self.assertIsNone(event["prior_event_digest"])
        self.assertEqual([path], validate_closure_records(self.root))
        with self.assertRaisesRegex(PacketError, "merged default-branch"):
            readback_transition(self.root, path)
        self.git("add", ".")
        self.git("commit", "-m", "accept Delivery target")
        self.git("switch", "main")
        self.git("merge", "--ff-only", "feature/closure")
        readback = readback_transition(self.root, path, observed_at="2026-09-12T13:00:00Z")
        self.assertEqual(content_digest(event), readback["source_event_digest"])
        self.assertEqual("graduating", readback["observed_lifecycle"])

    def test_graduation_requires_accepted_owner_and_exact_source_proof(self) -> None:
        self.apply_delivery()
        self.git("add", ".")
        self.git("commit", "-m", "accept Delivery target")
        request = self.request(
            "graduate-source",
            accepted_delivery_target_receipt_ref="receipt://delivery/sample",
            durable_owner_ref="repo://owner",
            durable_repo_ref="repo://owner/source",
            durable_owner_acceptance_ref="receipt://owner/sample",
            transfer_strategy="already-owned",
            already_owned_source_proof_ref="proof://owner/sample",
        )
        resolved = self.resolved(
            request,
            durable_owner_ref="repo://owner",
            durable_repo_ref="repo://owner/source",
            durable_owner_acceptance_ref="receipt://owner/sample",
            observed_source_custody="shared-owner-repo",
            already_owned_source_proof_ref="proof://owner/sample",
        )
        invalid = copy.deepcopy(resolved)
        invalid["durable_repo_ref"] = "repo://wrong"
        with self.assertRaisesRegex(PacketError, "accepted durable_repo_ref"):
            prepare_transition(self.root, request, invalid)
        self.assertEqual("graduating", self.item()["lifecycle"])
        path, event = prepare_transition(self.root, request, resolved, recorded_at=NOW)
        self.assertEqual("graduated", self.item()["lifecycle"])
        self.assertEqual("shared-owner-repo", self.item()["source_custody"])
        self.assertEqual(content_digest(self.apply_event()), event["prior_event_digest"])
        self.assertEqual(
            [self.root / "records/prototype-closure/sample/history/0001.json", path],
            validate_closure_records(self.root),
        )

    def apply_event(self) -> dict:
        from packages.prototype_delivery_packet.contract import load_json
        return load_json(self.root / "records/prototype-closure/sample/history/0001.json")

    def test_retire_and_reopen_append_history_without_runtime_revival(self) -> None:
        registry = load_yaml(self.root / "prototypes.yaml")
        registry["prototypes"][0]["lifecycle"] = "exploring"
        registry["prototypes"][0].pop("design_baseline_ref")
        registry["prototypes"][0].pop("delivery_packet_ref")
        self._write_registry(registry)
        self.git("add", ".")
        self.git("commit", "-m", "exploring fixture")
        request = self.request(
            "retire-incubation",
            retirement_reason="No longer needed",
            retention_plan_ref="plan://retention/sample",
            runtime_disposition_plan_ref="plan://runtime/sample",
        )
        resolved = self.resolved(
            request,
            retention_plan_ref="plan://retention/sample",
            runtime_disposition_plan_ref="plan://runtime/sample",
            runtime_disposition_proof_ref="proof://runtime/absent",
        )
        _, retired = prepare_transition(self.root, request, resolved, recorded_at=NOW)
        self.assertEqual("retired", self.item()["lifecycle"])
        self.git("add", ".")
        self.git("commit", "-m", "retire incubation")
        request = self.request(
            "reopen-incubation",
            prior_retirement_receipt_ref="receipt://closure/retired-sample",
        )
        resolved = self.resolved(
            request,
            prior_retirement_receipt_ref="receipt://closure/retired-sample",
            prior_retirement_event_ref=self.item()["retirement_ref"],
            retained_source_readback_ref="readback://source/sample",
        )
        _, reopened = prepare_transition(self.root, request, resolved, recorded_at="2026-09-12T14:00:00Z")
        self.assertEqual(content_digest(retired), reopened["prior_event_digest"])
        self.assertEqual("exploring", self.item()["lifecycle"])
        self.assertEqual("incubation-repo", self.item()["source_custody"])
        self.assertEqual(2, len(validate_closure_records(self.root)))

    def test_stale_revision_and_unreconciled_target_leave_source_unchanged(self) -> None:
        request = self.request(
            "apply-delivery",
            accepted_baseline_receipt_ref="receipt://baseline/sample",
            target_kind="new-delivery-epic",
        )
        resolved = self.resolved(request, target_delivery_ref="openproject://work_packages/1200")
        with self.assertRaisesRegex(PacketError, "accepted_delivery_target_receipt_ref"):
            prepare_transition(self.root, request, resolved)
        self.assertEqual("baseline-approved", self.item()["lifecycle"])
        self.assertEqual([], validate_closure_records(self.root))
        stale = copy.deepcopy(request)
        stale["expected_source_revision"] = "0" * 40
        with self.assertRaisesRegex(PacketError, "current source HEAD"):
            prepare_transition(
                self.root,
                stale,
                self.resolved(
                    stale,
                    accepted_delivery_target_receipt_ref="receipt://delivery/sample",
                    target_delivery_ref="openproject://work_packages/1200",
                ),
            )

    def test_replay_returns_exact_event_and_changed_authority_is_denied(self) -> None:
        request = self.request(
            "apply-delivery",
            accepted_baseline_receipt_ref="receipt://baseline/sample",
            target_kind="new-delivery-epic",
        )
        resolved = self.resolved(
            request,
            accepted_delivery_target_receipt_ref="receipt://delivery/sample",
            target_delivery_ref="openproject://work_packages/1200",
        )
        path, event = prepare_transition(self.root, request, resolved, recorded_at=NOW)
        replay_path, replay_event = prepare_transition(self.root, request, resolved, recorded_at=NOW)
        self.assertEqual((path, event), (replay_path, replay_event))
        changed = copy.deepcopy(resolved)
        changed["accepted_delivery_target_receipt_ref"] = "receipt://delivery/other"
        with self.assertRaises(PacketError) as context:
            prepare_transition(self.root, request, changed)
        self.assertEqual("idempotency_conflict", context.exception.code)

    def test_default_branch_and_tampered_history_are_denied(self) -> None:
        request = self.request(
            "apply-delivery",
            accepted_baseline_receipt_ref="receipt://baseline/sample",
            target_kind="new-delivery-epic",
        )
        resolved = self.resolved(
            request,
            accepted_delivery_target_receipt_ref="receipt://delivery/sample",
            target_delivery_ref="openproject://work_packages/1200",
        )
        self.git("switch", "main")
        with self.assertRaisesRegex(PacketError, "non-default review branch"):
            prepare_transition(self.root, request, resolved)
        self.git("switch", "feature/closure")
        path, _ = prepare_transition(self.root, request, resolved, recorded_at=NOW)
        from packages.prototype_delivery_packet.contract import load_json
        tampered = load_json(path)
        tampered["previous_lifecycle"] = "candidate"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaisesRegex(PacketError, "prior state differs"):
            validate_closure_records(self.root)


if __name__ == "__main__":
    unittest.main()
