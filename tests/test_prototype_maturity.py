from __future__ import annotations

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from packages.prototype_delivery_packet.contract import PacketError, content_digest
from packages.prototype_maturity.maturity import (
    apply_maturity,
    current_state,
    readback_maturity,
    validate_contract_bundle,
    validate_maturity_records,
)


SOURCE_ROOT = Path(__file__).resolve().parents[1]
NOW = "2026-09-09T12:00:00Z"
CHECKS = (
    "request-integrity",
    "lifecycle-source-state",
    "source-version-freshness",
    "packet-integrity",
    "required-evidence",
    "boundary-coherence",
    "security-trigger-disposition",
    "open-issue-disposition",
)
SECTIONS = {
    "candidate-promotion": (
        "candidate-brief",
        "scope-and-non-goals",
        "boundaries-and-risks",
    ),
    "baseline-promotion": (
        "definition",
        "design-and-workflow",
        "evidence",
        "boundaries",
        "issues-and-risk-disposition",
    ),
}


def bind(payload: dict, field: str) -> dict:
    result = copy.deepcopy(payload)
    result[field] = content_digest(result)
    return result


def ref(artifact: dict, id_field: str, digest_field: str) -> dict:
    return {"id": artifact[id_field], "digest": artifact[digest_field]}


class PrototypeMaturityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "studio"
        self.output = Path(self.temp.name) / "evidence"
        self.root.mkdir()
        shutil.copytree(SOURCE_ROOT / "contracts", self.root / "contracts")
        shutil.copytree(SOURCE_ROOT / "schemas", self.root / "schemas")
        landing_dir = self.root / "records" / "prototype-landings" / "sample"
        landing_dir.mkdir(parents=True)
        self.write_json(
            landing_dir / "record.json",
            {
                "id": "prototype:sample",
                "name": "Sample Prototype",
                "objective": "Prove a bounded workflow.",
                "lifecycle": "exploring",
            },
        )
        self.write_yaml(
            self.root / "prototypes.yaml",
            {
                "schema_version": 1,
                "studio": {"owner_repo": "workspace-prototype-studio"},
                "prototypes": [
                    {
                        "id": "sample",
                        "name": "Sample Prototype",
                        "objective": "Prove a bounded workflow.",
                        "portfolio": "experiment",
                        "lifecycle": "exploring",
                        "project_phase": "incubating",
                        "owner": "Workspace Prototype Studio",
                        "linked_records": [
                            {
                                "role": "landing-record",
                                "ref": "record://prototype-landings/sample",
                                "system": "prototype-studio",
                                "level": "record",
                                "label": "Prototype Landing source record",
                            }
                        ],
                        "visibility_tier": "private-internal",
                        "data_mode": "synthetic",
                        "mutation_boundary": "none",
                        "landing_record_ref": "record://prototype-landings/sample",
                        "paths": {
                            "brief": "docs/prototypes/sample/brief.md",
                            "backlog": "docs/prototypes/sample/backlog.md",
                            "design_profile": "docs/prototypes/sample/design-profile.md",
                            "change_log": "docs/prototypes/sample/change-log.md",
                            "decision_log": "docs/prototypes/sample/decision-log.md",
                        },
                    }
                ],
            },
        )
        docs = self.root / "docs" / "prototypes" / "sample"
        docs.mkdir(parents=True)
        for name in ("brief.md", "backlog.md", "design-profile.md", "change-log.md", "decision-log.md"):
            (docs / name).write_text(f"# {name}\n", encoding="utf-8")
        (self.root / "records" / "design-baselines").mkdir(parents=True)
        self.git("init", "-b", "main")
        self.git("config", "user.email", "prototype-test@example.invalid")
        self.git("config", "user.name", "Prototype Test")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("switch", "-c", "feature/sample-maturity")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def git(self, *args: str) -> str:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    @staticmethod
    def write_json(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @staticmethod
    def write_yaml(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def artifacts(
        self,
        transition: str = "candidate-promotion",
        *,
        decision_value: str | None = None,
        expected_state: dict | None = None,
        sequence: int | None = None,
    ) -> tuple[dict, dict, dict, dict]:
        baseline = transition == "baseline-promotion"
        sequence = sequence or (2 if baseline else 1)
        source = "candidate" if baseline else "exploring"
        target = "baseline-approved" if baseline else "candidate"
        decision_value = decision_value or ("approve-baseline" if baseline else "promote-candidate")
        state = expected_state or current_state(self.root, "prototype:sample")["expected_state"]
        values = (
            {
                "baseline-title": "Sample accepted baseline",
                "baseline-statement": "The local design and workflow are accepted.",
                "accepted-summary": "The reviewed operator workflow and local proof.",
                "excluded-summary": "Live runtime and cross-domain authority remain excluded.",
                "selected-evidence-refs": ["evidence://sample/design-review"],
                "missing-evidence-disposition": "No required local evidence is missing.",
                "issue-and-risk-disposition": "No open issue blocks local baseline approval.",
            }
            if baseline
            else {
                "prototype-objective": "Prove a bounded workflow.",
                "target-user": "Workspace operator",
                "expected-proof": "A deterministic local transition with review evidence.",
                "accepted-scope": ["Local Prototype workflow", "Synthetic validation evidence"],
                "excluded-scope": ["Live backend authority", "Public exposure"],
                "boundary-clarifications": "Source remains in Workspace Prototype Studio.",
                "open-issue-disposition": "No open issue blocks candidate shaping.",
            }
        )
        request = bind(
            {
                "schema_version": 1,
                "artifact_type": "prototype-maturity-request",
                "request_id": f"prototype-maturity-request:sample:{sequence}",
                "requested_at": NOW,
                "operator_ref": "operator:workspace-owner",
                "prototype_id": "prototype:sample",
                "transition": transition,
                "source_lifecycle": source,
                "target_lifecycle": target,
                "expected_state": copy.deepcopy(state),
                "inputs": {
                    "source_refs": ["record://prototype-landings/sample"],
                    "editable_values": values,
                },
                "correlation_id": f"prototype-maturity:sample:{sequence}",
                "idempotency_key": f"prototype-maturity:sample:{sequence}",
            },
            "request_digest",
        )
        packet = bind(
            {
                "schema_version": 1,
                "artifact_type": "prototype-maturity-packet",
                "packet_id": f"prototype-maturity-packet:sample:{sequence}",
                "assembled_at": NOW,
                "request_ref": ref(request, "request_id", "request_digest"),
                "prototype_id": "prototype:sample",
                "transition": transition,
                "packet_kind": "baseline-packet" if baseline else "candidate-evidence-packet",
                "sections": [
                    {
                        "id": section,
                        "state": "ready",
                        "evidence_refs": [f"evidence://sample/{section}"],
                    }
                    for section in SECTIONS[transition]
                ],
            },
            "packet_digest",
        )
        readiness = bind(
            {
                "schema_version": 1,
                "artifact_type": "prototype-maturity-readiness",
                "readiness_id": f"prototype-maturity-readiness:sample:{sequence}",
                "evaluated_at": NOW,
                "request_ref": ref(request, "request_id", "request_digest"),
                "packet_ref": ref(packet, "packet_id", "packet_digest"),
                "prototype_id": "prototype:sample",
                "transition": transition,
                "observed_state": copy.deepcopy(state),
                "outcome": "ready",
                "checks": [
                    {"id": check, "state": "ready", "evidence_refs": [f"evidence://sample/{check}"]}
                    for check in CHECKS
                ],
                "findings": [],
            },
            "readiness_digest",
        )
        blocker = (
            {
                "issue_ref": "openproject://work_packages/999",
                "owner_ref": "workspace-prototype-studio",
                "required_fix": "Resolve the visible evidence gap.",
            }
            if decision_value in {"block-promotion", "block-baseline"}
            else None
        )
        decision = bind(
            {
                "schema_version": 1,
                "artifact_type": "prototype-maturity-decision",
                "decision_id": f"prototype-maturity-decision:sample:{sequence}",
                "decided_at": NOW,
                "request_ref": ref(request, "request_id", "request_digest"),
                "packet_ref": ref(packet, "packet_id", "packet_digest"),
                "readiness_ref": ref(readiness, "readiness_id", "readiness_digest"),
                "prototype_id": "prototype:sample",
                "transition": transition,
                "decision": decision_value,
                "operator_ref": "operator:workspace-owner",
                "expected_state": copy.deepcopy(state),
                "source_branch": "feature/sample-maturity",
                "blocker": blocker,
                "correlation_id": request["correlation_id"],
                "idempotency_key": request["idempotency_key"],
            },
            "decision_digest",
        )
        return request, packet, readiness, decision

    def apply(self, artifacts: tuple[dict, dict, dict, dict], name: str = "result.json"):
        request, packet, readiness, decision = artifacts
        return apply_maturity(
            repo_root=self.root,
            request=request,
            packet=packet,
            readiness=readiness,
            decision=decision,
            output_path=self.output / name,
            prepared_at=NOW,
        )

    def test_contract_bundle_is_exact_and_valid(self) -> None:
        validate_contract_bundle(self.root)

    def test_candidate_promotion_prepares_only_allowed_source(self) -> None:
        artifacts = self.artifacts()
        result = self.apply(artifacts)
        registry = yaml.safe_load((self.root / "prototypes.yaml").read_text())
        item = registry["prototypes"][0]
        self.assertEqual(result.status, "prepared")
        self.assertEqual(item["lifecycle"], "candidate")
        self.assertEqual(item["project_phase"], "incubating")
        self.assertEqual(item["mutation_boundary"], "none")
        self.assertTrue((self.root / "records/prototype-maturity/sample/candidate.json").is_file())
        self.assertEqual(
            set(json.loads((self.output / "result.json").read_text())["changed_paths"]),
            {
                "prototypes.yaml",
                "records/prototype-maturity/sample/candidate.json",
                "records/prototype-maturity/sample/history/prototype-maturity-decision-sample-1.json",
            },
        )

    def test_baseline_promotion_prepares_approved_baseline_without_cross_domain_mutation(self) -> None:
        self.apply(self.artifacts(), "candidate.json")
        self.git("add", ".")
        self.git("commit", "-m", "promote candidate")
        result = self.apply(self.artifacts("baseline-promotion"), "baseline.json")
        registry = yaml.safe_load((self.root / "prototypes.yaml").read_text())
        item = registry["prototypes"][0]
        self.assertEqual(result.status, "prepared")
        self.assertEqual(item["lifecycle"], "baseline-approved")
        self.assertEqual(item["project_phase"], "incubating")
        self.assertNotIn("delivery_packet_ref", item)
        self.assertNotIn("graduation_ref", item)
        baseline = yaml.safe_load(
            (self.root / "records/design-baselines/sample-baseline-2.yaml").read_text()
        )
        self.assertEqual(baseline["decision"], "approved")
        self.assertEqual(baseline["title"], "Sample accepted baseline")
        self.assertEqual(baseline["statement"], "The local design and workflow are accepted.")
        self.assertEqual(baseline["accepted_summary"], "The reviewed operator workflow and local proof.")
        self.assertIn("evidence://sample/design-review", baseline["evidence_refs"])
        self.assertEqual(len(validate_maturity_records(self.root)), 3)

    def test_exact_replay_does_not_mutate_source_again(self) -> None:
        artifacts = self.artifacts()
        self.apply(artifacts, "first.json")
        before = self.git("diff")
        result = self.apply(artifacts, "replay.json")
        self.assertEqual(result.status, "replayed")
        self.assertEqual(self.git("diff"), before)
        self.assertEqual(json.loads((self.output / "replay.json").read_text())["changed_paths"], [])

    def test_conflicting_idempotency_key_fails_closed(self) -> None:
        artifacts = self.artifacts()
        self.apply(artifacts, "first.json")
        request, packet, readiness, decision = copy.deepcopy(artifacts)
        decision["operator_ref"] = "operator:another"
        decision = bind(
            {key: value for key, value in decision.items() if key != "decision_digest"},
            "decision_digest",
        )
        with self.assertRaisesRegex(PacketError, "idempotency key is bound"):
            self.apply((request, packet, readiness, decision), "conflict.json")

    def test_stale_source_fails_without_mutation(self) -> None:
        state = current_state(self.root, "prototype:sample")["expected_state"]
        state["source_revision"] = "0" * 40
        artifacts = self.artifacts(expected_state=state)
        with self.assertRaisesRegex(PacketError, "source state differs"):
            self.apply(artifacts)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_block_and_closeout_decisions_leave_source_unchanged(self) -> None:
        for sequence, decision_value in ((3, "block-promotion"), (4, "route-closeout")):
            artifacts = self.artifacts(decision_value=decision_value, sequence=sequence)
            result = self.apply(artifacts, f"{decision_value}.json")
            self.assertEqual(result.status, "unchanged")
            self.assertEqual(self.git("status", "--porcelain"), "")
            self.assertEqual(json.loads((self.output / f"{decision_value}.json").read_text())["changed_paths"], [])

    def test_promotion_rejects_default_branch(self) -> None:
        self.git("switch", "main")
        artifacts = self.artifacts()
        with self.assertRaisesRegex(PacketError, "non-default review branch"):
            self.apply(artifacts)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_replay_remains_bound_to_the_review_branch(self) -> None:
        artifacts = self.artifacts()
        self.apply(artifacts)
        self.git("add", ".")
        self.git("commit", "-m", "promote candidate")
        self.git("switch", "main")
        with self.assertRaisesRegex(PacketError, "non-default review branch"):
            self.apply(artifacts, "replay.json")

    def test_baseline_rejects_a_manually_edited_candidate_lifecycle(self) -> None:
        registry = yaml.safe_load((self.root / "prototypes.yaml").read_text())
        registry["prototypes"][0]["lifecycle"] = "candidate"
        self.write_yaml(self.root / "prototypes.yaml", registry)
        self.git("add", "prototypes.yaml")
        self.git("commit", "-m", "simulate invalid candidate state")
        with self.assertRaisesRegex(PacketError, "requires a candidate record"):
            self.apply(self.artifacts("baseline-promotion"))

    def test_unbounded_or_unknown_editable_values_are_rejected(self) -> None:
        request, _, _, _ = self.artifacts()
        request["inputs"]["editable_values"]["invented-field"] = "not allowed"
        request = bind(
            {key: value for key, value in request.items() if key != "request_digest"},
            "request_digest",
        )
        _, packet, readiness, decision = self.artifacts()
        packet["request_ref"] = ref(request, "request_id", "request_digest")
        packet = bind({key: value for key, value in packet.items() if key != "packet_digest"}, "packet_digest")
        readiness["request_ref"] = ref(request, "request_id", "request_digest")
        readiness["packet_ref"] = ref(packet, "packet_id", "packet_digest")
        readiness = bind(
            {key: value for key, value in readiness.items() if key != "readiness_digest"},
            "readiness_digest",
        )
        decision["request_ref"] = ref(request, "request_id", "request_digest")
        decision["packet_ref"] = ref(packet, "packet_id", "packet_digest")
        decision["readiness_ref"] = ref(readiness, "readiness_id", "readiness_digest")
        decision = bind(
            {key: value for key, value in decision.items() if key != "decision_digest"},
            "decision_digest",
        )
        with self.assertRaisesRegex(PacketError, "exact transition fields"):
            self.apply((request, packet, readiness, decision))

    def test_output_failure_rolls_back_all_source_writes(self) -> None:
        self.output.mkdir()
        (self.output / "result.json").write_text("conflict\n", encoding="utf-8")
        with self.assertRaisesRegex(PacketError, "evidence already exists"):
            self.apply(self.artifacts())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_merged_readback_requires_and_proves_default_branch_authority(self) -> None:
        artifacts = self.artifacts()
        decision = artifacts[-1]
        self.apply(artifacts)
        with self.assertRaisesRegex(PacketError, "default branch"):
            readback_maturity(
                repo_root=self.root,
                decision=decision,
                output_path=self.output / "early-readback.json",
                observed_at=NOW,
            )
        self.git("add", ".")
        self.git("commit", "-m", "promote candidate")
        self.git("switch", "main")
        self.git("merge", "--ff-only", "feature/sample-maturity")
        readback = readback_maturity(
            repo_root=self.root,
            decision=decision,
            output_path=self.output / "merged-readback.json",
            observed_at=NOW,
        )
        self.assertEqual(readback["authority_state"], "merged-authority")
        self.assertEqual(readback["observed_lifecycle"], "candidate")
        self.assertEqual(readback["source_revision"], self.git("rev-parse", "HEAD"))

    def test_committed_maturity_records_validate(self) -> None:
        self.apply(self.artifacts())
        paths = validate_maturity_records(self.root)
        self.assertEqual(len(paths), 2)


if __name__ == "__main__":
    unittest.main()
