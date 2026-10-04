from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from packages.proposal_target_application.application import (
    apply_application,
    current_state,
    validate_capture_records,
)
from packages.prototype_delivery_packet.contract import PacketError, content_digest


SOURCE_ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-10-04T10:30:00Z"
PACKET_DIGEST = "sha256:" + "a" * 64


def bind_request(payload: dict) -> dict:
    result = copy.deepcopy(payload)
    result["request_digest"] = content_digest(result)
    return result


class ProposalTargetApplicationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        shutil.copytree(
            SOURCE_ROOT / "contracts" / "proposal-target-application",
            self.root / "contracts" / "proposal-target-application",
        )
        (self.root / "contracts" / "prototype-landing").mkdir(parents=True)
        shutil.copy2(
            SOURCE_ROOT / "contracts" / "prototype-landing" / "prototype-landing-entry-packet.schema.json",
            self.root / "contracts" / "prototype-landing" / "prototype-landing-entry-packet.schema.json",
        )
        (self.root / "prototypes.yaml").write_text(
            yaml.safe_dump({
                "schema_version": 1,
                "studio": {"owner_repo": "workspace-prototype-studio"},
                "prototypes": [],
            }, sort_keys=False),
            encoding="utf-8",
        )
        self.git("init", "-b", "main")
        self.git("config", "user.email", "proposal-target-test@example.invalid")
        self.git("config", "user.name", "Proposal Target Test")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("switch", "-c", "feature/test-proposal-target")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args], cwd=self.root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def request(self, **changes) -> dict:
        state = current_state(self.root, "prototype:sample-tool")["expected_state"]
        payload = {
            "schema_version": 1,
            "artifact_type": "proposal-prototype-application",
            "application_id": "proposal-prototype-application:sample-tool:1",
            "requested_at": NOW,
            "operator_ref": "operator:workspace-owner",
            "source": {
                "authority": "workspace-proposals",
                "proposal_id": "idea-851",
                "record_ref": "openproject://work_packages/851",
                "record_version": "version-19",
                "projection_state": "current",
                "status": "accepted",
                "handoff_packet_ref": "proposal-packet:851",
                "handoff_packet_digest": PACKET_DIGEST,
                "suggested_name": "Sample Tool",
                "suggested_objective": "Explore a bounded operator tool.",
                "route": {
                    "target": "prototype",
                    "rationale": "The idea needs incubation before Delivery.",
                    "source_custody": {
                        "classification": "platform-internal",
                        "repository_mode": "not-required",
                        "repository_gate_state": "resolved",
                        "owner": None,
                        "source_ref": None,
                        "rationale": "No source exists before Prototype Landing.",
                    },
                },
            },
            "authorization": {
                "authority": "operator-orchestration-service",
                "decision": "approved",
                "receipt_ref": "oos://proposal-applications/851",
            },
            "target": {"prototype_id": "prototype:sample-tool", "expected_state": state},
            "source_branch": "feature/test-proposal-target",
            "correlation_id": "correlation:proposal-851:prototype",
            "idempotency_key": "proposal-851:prototype:1",
        }
        for key, value in changes.items():
            payload[key] = value
        return bind_request(payload)

    def apply(self, request: dict, name: str = "result.json"):
        return apply_application(
            repo_root=self.root,
            request=request,
            output_path=self.base / "evidence" / name,
        )

    def test_apply_creates_only_one_captured_exploring_record_and_receipt(self) -> None:
        request = self.request()
        applied = self.apply(request)
        self.assertEqual(applied.status, "prepared")
        record_path = self.root / "records/prototype-captures/sample-tool/record.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        result = json.loads(applied.result_path.read_text(encoding="utf-8"))
        registry = yaml.safe_load((self.root / "prototypes.yaml").read_text(encoding="utf-8"))

        self.assertEqual(record["lifecycle"], "exploring")
        self.assertEqual(record["landing_state"], "captured")
        self.assertEqual(record["next_action"], "prototype-landing")
        self.assertEqual(record["proposal"]["handoff_packet_ref"], "proposal-packet:851")
        self.assertEqual(record["entry_packet"]["ingress_class"], "proposal-routed")
        self.assertEqual(registry["prototypes"], [])
        self.assertFalse((self.root / "records/prototype-landings/sample-tool").exists())
        self.assertFalse((self.root / "docs/prototypes/sample-tool").exists())
        self.assertEqual(result["receipt"]["owner"], "workspace-prototype-studio")
        self.assertEqual(result["receipt"]["outcome"], "prepared")
        self.assertEqual(result["receipt"]["next_action"]["code"], "prototype-landing")
        self.assertEqual(result["readback"]["record"], record)
        self.assertEqual(validate_capture_records(self.root), [record_path])

    def test_exact_replay_is_idempotent_and_keeps_receipt_identity(self) -> None:
        request = self.request()
        first = self.apply(request, "first.json")
        first_result = json.loads(first.result_path.read_text(encoding="utf-8"))
        before = self.git("status", "--porcelain")
        second = self.apply(request, "second.json")
        second_result = json.loads(second.result_path.read_text(encoding="utf-8"))

        self.assertEqual(second.status, "replayed")
        self.assertEqual(first_result["receipt"]["receipt_ref"], second_result["receipt"]["receipt_ref"])
        self.assertEqual(first_result["readback"]["record_digest"], second_result["readback"]["record_digest"])
        self.assertTrue(second_result["replayed"])
        self.assertEqual(second_result["receipt"]["outcome"], "replayed")
        self.assertEqual(self.git("status", "--porcelain"), before)

    def test_conflicting_replay_fails_without_second_record(self) -> None:
        request = self.request()
        self.apply(request)
        conflict = copy.deepcopy(request)
        conflict["source"]["suggested_name"] = "Different Tool"
        conflict = bind_request({key: value for key, value in conflict.items() if key != "request_digest"})
        with self.assertRaisesRegex(PacketError, "bound to different content") as caught:
            self.apply(conflict, "conflict.json")
        self.assertEqual(caught.exception.code, "idempotency_conflict")
        self.assertEqual(len(list((self.root / "records/prototype-captures").glob("*/record.json"))), 1)

    def test_stale_state_fails_closed_without_source_mutation(self) -> None:
        request = self.request()
        request["target"]["expected_state"]["registry_digest"] = "sha256:" + "b" * 64
        request = bind_request({key: value for key, value in request.items() if key != "request_digest"})
        with self.assertRaises(PacketError) as caught:
            self.apply(request)
        self.assertEqual(caught.exception.code, "source_state_stale")
        self.assertFalse((self.root / "records").exists())

    def test_wrong_branch_and_dirty_source_are_rejected(self) -> None:
        request = self.request(source_branch="feature/another")
        with self.assertRaises(PacketError) as branch_error:
            self.apply(request)
        self.assertEqual(branch_error.exception.code, "source_branch_invalid")

        (self.root / "dirty.txt").write_text("dirty", encoding="utf-8")
        with self.assertRaises(PacketError) as dirty_error:
            self.apply(self.request())
        self.assertEqual(dirty_error.exception.code, "dirty_worktree")

    def test_malformed_authorization_route_and_proposal_identity_fail_closed(self) -> None:
        cases = []
        unauthorized = self.request()
        unauthorized["authorization"]["decision"] = "denied"
        cases.append((unauthorized, "artifact_invalid"))
        wrong_route = self.request()
        wrong_route["source"]["route"]["target"] = "delivery"
        cases.append((wrong_route, "artifact_invalid"))
        wrong_record = self.request()
        wrong_record["source"]["record_ref"] = "openproject://work_packages/852"
        cases.append((wrong_record, "proposal_identity_mismatch"))
        wrong_custody = self.request()
        wrong_custody["source"]["route"]["source_custody"] = {
            "classification": "existing-repo",
            "repository_mode": "new",
            "repository_gate_state": "resolved",
            "owner": "workspace-prototype-studio",
            "source_ref": "repo:workspace-prototype-studio",
            "rationale": "Mismatched classification.",
        }
        cases.append((wrong_custody, "source_custody_invalid"))

        for index, (payload, code) in enumerate(cases):
            with self.subTest(code=code, index=index):
                payload = bind_request({key: value for key, value in payload.items() if key != "request_digest"})
                with self.assertRaises(PacketError) as caught:
                    self.apply(payload, f"invalid-{index}.json")
                self.assertEqual(caught.exception.code, code)
        self.assertFalse((self.root / "records").exists())

    def test_existing_registry_identity_is_not_overwritten(self) -> None:
        registry = yaml.safe_load((self.root / "prototypes.yaml").read_text(encoding="utf-8"))
        registry["prototypes"].append({"id": "sample-tool"})
        (self.root / "prototypes.yaml").write_text(yaml.safe_dump(registry), encoding="utf-8")
        self.git("add", "prototypes.yaml")
        self.git("commit", "-m", "existing identity")
        request = self.request()
        self.assertTrue(request["target"]["expected_state"]["record_present"])
        request["target"]["expected_state"]["record_present"] = False
        request = bind_request({key: value for key, value in request.items() if key != "request_digest"})
        with self.assertRaises(PacketError) as caught:
            self.apply(request)
        self.assertEqual(caught.exception.code, "source_state_stale")

    def test_failure_rolls_back_record_history_and_result(self) -> None:
        request = self.request()
        output = self.base / "evidence/result.json"
        with mock.patch(
            "packages.proposal_target_application.application._build_result",
            side_effect=PacketError("result_failed", "forced result failure"),
        ):
            with self.assertRaises(PacketError):
                apply_application(repo_root=self.root, request=request, output_path=output)
        self.assertFalse((self.root / "records/prototype-captures/sample-tool/record.json").exists())
        self.assertFalse(any((self.root / "records/prototype-captures").glob("*/history/*.json")))
        self.assertFalse(output.exists())

    def test_validator_rejects_tampered_record(self) -> None:
        self.apply(self.request())
        path = self.root / "records/prototype-captures/sample-tool/record.json"
        record = json.loads(path.read_text(encoding="utf-8"))
        record["entry_packet"]["suggestions"]["name"] = "Forged"
        path.write_text(json.dumps(record), encoding="utf-8")
        with self.assertRaises(PacketError) as caught:
            validate_capture_records(self.root)
        self.assertEqual(caught.exception.code, "entry_packet_digest_mismatch")

    def test_cli_runs_against_a_real_git_review_branch(self) -> None:
        request = self.request()
        request_path = self.base / "request.json"
        output_path = self.base / "cli-result.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        completed = subprocess.run(
            [
                "python3", str(SOURCE_ROOT / "scripts/proposal_target_application.py"),
                "--repo-root", str(self.root), "apply",
                "--request", str(request_path), "--output", str(output_path),
            ],
            cwd=SOURCE_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertEqual(json.loads(completed.stdout)["status"], "prepared")
        self.assertTrue(output_path.is_file())


if __name__ == "__main__":
    unittest.main()
