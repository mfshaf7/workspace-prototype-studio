from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

from packages.prototype_delivery_packet.contract import PacketError, content_digest
from packages.prototype_landing.landing import (
    apply_landing,
    current_state,
    imported_content_digest,
    validate_contract_bundle,
    validate_landing_records,
)


SOURCE_ROOT = Path(__file__).resolve().parents[1]
DIGEST = "sha256:" + "1" * 64
NOW = "2026-09-07T06:30:00Z"
CHECKS = (
    "entry-integrity",
    "identity-availability",
    "required-metadata",
    "support-profile-integrity",
    "support-row-readiness",
    "source-custody-coherence",
    "source-version-freshness",
    "data-and-mutation-boundary",
    "visibility-and-exposure",
    "security-trigger-disposition",
    "expected-mutation-set",
)
DIMENSIONS = (
    "source",
    "studio-home",
    "interface",
    "runtime",
    "data",
    "integration",
    "tooling",
    "evidence",
    "visibility",
    "recovery",
)


def bind_digest(payload: dict) -> dict:
    result = copy.deepcopy(payload)
    digest_fields = {
        "prototype-entry-packet": "packet_digest",
        "prototype-landing-request": "request_digest",
        "prototype-landing-plan": "plan_digest",
        "prototype-landing-readiness": "readiness_digest",
        "prototype-landing-apply": "apply_digest",
    }
    result[digest_fields[result["artifact_type"]]] = content_digest(result)
    return result


def ref(artifact: dict) -> dict:
    id_fields = {
        "prototype-entry-packet": "entry_id",
        "prototype-landing-request": "request_id",
        "prototype-landing-plan": "plan_id",
        "prototype-landing-readiness": "readiness_id",
        "prototype-landing-apply": "apply_id",
    }
    digest_fields = {
        "prototype-entry-packet": "packet_digest",
        "prototype-landing-request": "request_digest",
        "prototype-landing-plan": "plan_digest",
        "prototype-landing-readiness": "readiness_digest",
        "prototype-landing-apply": "apply_digest",
    }
    return {
        "id": artifact[id_fields[artifact["artifact_type"]]],
        "digest": artifact[digest_fields[artifact["artifact_type"]]],
    }


class PrototypeLandingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "studio"
        self.output = Path(self.temp.name) / "evidence"
        self.root.mkdir()
        shutil.copytree(SOURCE_ROOT / "contracts", self.root / "contracts")
        shutil.copytree(SOURCE_ROOT / "schemas", self.root / "schemas")
        shutil.copytree(SOURCE_ROOT / "docs" / "prototypes" / "_template", self.root / "docs" / "prototypes" / "_template")
        self._write_yaml(
            self.root / "prototypes.yaml",
            {
                "schema_version": 1,
                "studio": {"owner_repo": "workspace-prototype-studio"},
                "prototypes": [],
            },
        )
        self.git("init", "-b", "main")
        self.git("config", "user.email", "prototype-test@example.invalid")
        self.git("config", "user.name", "Prototype Test")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.git("switch", "-c", "feature/test-landing")

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
    def _write_yaml(path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")

    def artifacts(
        self,
        *,
        posture: str = "create-studio-source",
        mutation_set: tuple[str, ...] | None = None,
        source_ref: str = "repo://workspace-prototype-studio/prototypes/sample-tool",
        source_revision: str | None = None,
        origin_digest: str | None = None,
        imported_digest: str | None = None,
        readiness_outcome: str = "ready",
    ) -> tuple[dict, dict, dict, dict, dict]:
        state = current_state(self.root, "prototype:sample-tool")["expected_state"]
        observed_state = {
            "registry_digest": state["registry_digest"],
            "record_present": state["record_present"],
            "source_revision": state["source_revision"],
        }
        entry = bind_digest(
            {
                "schema_version": 1,
                "artifact_type": "prototype-entry-packet",
                "entry_id": "prototype-entry:direct:sample-tool",
                "captured_at": NOW,
                "ingress_class": "direct",
                "source": {
                    "authority": "operator",
                    "ref": "operator-request:sample-tool",
                    "digest": DIGEST,
                    "revision": None,
                },
                "suggestions": {
                    "name": "Suggested Name",
                    "objective": "Suggested objective",
                    "support_profile": "simple",
                },
                "constraints": [],
                "requested_by": "operator:mfshaf7",
            }
        )
        request = bind_digest(
            {
                "schema_version": 1,
                "artifact_type": "prototype-landing-request",
                "request_id": "prototype-landing-request:sample-tool:1",
                "requested_at": NOW,
                "operator_ref": "operator:mfshaf7",
                "entry_packet_ref": ref(entry),
                "prototype": {
                    "id": "prototype:sample-tool",
                    "name": "Operator Chosen Tool",
                    "objective": "Prove a deterministic local workflow.",
                },
                "setup": {
                    "support_profile": "simple",
                    "support_rows": [
                        {
                            "dimension": dimension,
                            "state": "ready" if dimension in {"source", "studio-home", "evidence", "recovery"} else "not-needed",
                            "generated": True,
                            "detail": f"{dimension} resolved by the simple profile",
                        }
                        for dimension in DIMENSIONS
                    ],
                    "scaffold_profile": "python-library",
                    "preview_mode": "none",
                    "data_mode": "synthetic",
                    "mutation_boundary": "none",
                    "visibility": "private",
                },
                "source_plan": {
                    "posture": posture,
                    "source_ref": source_ref,
                    "source_revision": source_revision,
                    "origin_digest": origin_digest,
                    "imported_content_digest": imported_digest,
                },
                "starting_lifecycle": "exploring",
                "expected_state": state,
                "operator_accepted": True,
                "correlation_id": "correlation:sample-tool:1",
                "idempotency_key": "landing:sample-tool:1",
            }
        )
        if mutation_set is None:
            mutation_set = ("registry-record", "prototype-docs", "prototype-source", "validation-plan")
        targets = {
            "registry-record": "prototypes.yaml",
            "prototype-docs": "docs/prototypes/sample-tool",
            "prototype-source": "prototypes/sample-tool",
            "fixtures": "fixtures/prototypes/sample-tool",
            "preview-profile-draft": "records/prototype-preview-profiles/sample-tool.yaml",
            "validation-plan": "records/prototype-landings/sample-tool/validation-plan.yaml",
        }
        plan = bind_digest(
            {
                "schema_version": 1,
                "artifact_type": "prototype-landing-plan",
                "plan_id": "prototype-landing-plan:sample-tool:1",
                "planned_at": NOW,
                "request_ref": ref(request),
                "prototype_id": "prototype:sample-tool",
                "source_plan": copy.deepcopy(request["source_plan"]),
                "mutation_set": list(mutation_set),
                "expected_outputs": [
                    {"kind": kind, "target_ref": targets[kind], "required": True}
                    for kind in mutation_set
                ],
                "next_action": "candidate-promotion",
            }
        )
        states = ["ready"] * len(CHECKS)
        if readiness_outcome == "blocked":
            states[0] = "blocked"
        readiness = bind_digest(
            {
                "schema_version": 1,
                "artifact_type": "prototype-landing-readiness",
                "readiness_id": "prototype-landing-readiness:sample-tool:1",
                "evaluated_at": NOW,
                "request_ref": ref(request),
                "plan_ref": ref(plan),
                "observed_state": copy.deepcopy(observed_state),
                "outcome": readiness_outcome,
                "checks": [
                    {"id": check, "state": check_state, "evidence_refs": [f"evidence:{check}"]}
                    for check, check_state in zip(CHECKS, states, strict=True)
                ],
                "findings": [],
                "security_trigger_refs": [],
            }
        )
        apply = bind_digest(
            {
                "schema_version": 1,
                "artifact_type": "prototype-landing-apply",
                "apply_id": "prototype-landing-apply:sample-tool:1",
                "requested_at": NOW,
                "request_ref": ref(request),
                "plan_ref": ref(plan),
                "readiness_ref": ref(readiness),
                "prototype_id": "prototype:sample-tool",
                "expected_state": copy.deepcopy(observed_state),
                "operator_approval_ref": "approval:sample-tool:1",
                "source_branch": "feature/test-landing",
                "correlation_id": request["correlation_id"],
                "idempotency_key": request["idempotency_key"],
            }
        )
        return entry, request, plan, readiness, apply

    def apply(self, artifacts: tuple[dict, dict, dict, dict, dict], **kwargs):
        entry, request, plan, readiness, apply = artifacts
        return apply_landing(
            repo_root=self.root,
            entry=entry,
            request=request,
            plan=plan,
            readiness=readiness,
            apply=apply,
            output_dir=kwargs.pop("output_dir", self.output),
            completed_at=NOW,
            **kwargs,
        )

    def test_create_prepares_registry_source_docs_and_receipt(self) -> None:
        result = self.apply(self.artifacts())
        self.assertEqual(result.status, "prepared")
        self.assertTrue(result.source_revision.startswith("git-tree:"))
        registry = yaml.safe_load((self.root / "prototypes.yaml").read_text())
        landed = registry["prototypes"][0]
        self.assertEqual(landed["id"], "sample-tool")
        self.assertNotIn("portfolio", landed)
        self.assertEqual(landed["lifecycle"], "exploring")
        record = json.loads((self.root / "records/prototype-landings/sample-tool/record.json").read_text())
        self.assertEqual(record["id"], "prototype:sample-tool")
        self.assertEqual(record["name"], "Operator Chosen Tool")
        self.assertNotEqual(record["name"], "Suggested Name")
        self.assertTrue((self.root / "prototypes/sample-tool/README.md").is_file())
        receipt = json.loads(result.receipt_path.read_text())
        self.assertEqual(receipt["outcome"], "prepared")
        self.assertEqual(receipt["source_result"]["revision"], result.source_revision)
        self.assertEqual(validate_landing_records(self.root), [self.root / "records/prototype-landings/sample-tool/record.json"])

    def test_exact_replay_does_not_mutate_source(self) -> None:
        artifacts = self.artifacts()
        self.apply(artifacts)
        before = self.git("diff")
        replay = self.apply(artifacts, output_dir=Path(self.temp.name) / "replay")
        self.assertEqual(replay.status, "replayed")
        self.assertEqual(self.git("diff"), before)
        receipt = json.loads(replay.receipt_path.read_text())
        self.assertEqual(receipt["phase"], "source-replay")

    def test_conflicting_idempotency_key_is_rejected_without_mutation(self) -> None:
        artifacts = self.artifacts()
        self.apply(artifacts)
        before = self.git("diff")
        conflicting = list(copy.deepcopy(artifacts))
        conflicting_apply = conflicting[-1]
        conflicting_apply["operator_approval_ref"] = "approval:different"
        conflicting[-1] = bind_digest({key: value for key, value in conflicting_apply.items() if key != "apply_digest"})
        with self.assertRaisesRegex(PacketError, "idempotency key"):
            self.apply(tuple(conflicting), output_dir=Path(self.temp.name) / "conflict")
        self.assertEqual(self.git("diff"), before)

    def test_blocked_readiness_and_stale_state_leave_source_clean(self) -> None:
        blocked = self.artifacts(readiness_outcome="blocked")
        with self.assertRaisesRegex(PacketError, "requires every readiness"):
            self.apply(blocked)
        self.assertEqual(self.git("status", "--porcelain"), "")

        stale = list(self.artifacts())
        stale[-1]["expected_state"]["registry_digest"] = DIGEST
        stale[-1] = bind_digest({key: value for key, value in stale[-1].items() if key != "apply_digest"})
        with self.assertRaisesRegex(PacketError, "state bindings differ"):
            self.apply(tuple(stale))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_default_branch_is_denied(self) -> None:
        artifacts = list(self.artifacts())
        self.git("switch", "main")
        artifacts[-1]["source_branch"] = "main"
        artifacts[-1] = bind_digest({key: value for key, value in artifacts[-1].items() if key != "apply_digest"})
        with self.assertRaises(PacketError) as raised:
            self.apply(tuple(artifacts))
        self.assertEqual(raised.exception.code, "artifact_invalid")
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_reference_only_records_custody_without_copying_source(self) -> None:
        artifacts = self.artifacts(
            posture="reference-dedicated-owner-source",
            mutation_set=("registry-record", "prototype-docs", "validation-plan"),
            source_ref="repo://dedicated-product/source",
            source_revision="abc123",
        )
        self.apply(artifacts)
        record = json.loads((self.root / "records/prototype-landings/sample-tool/record.json").read_text())
        self.assertEqual(record["source"]["custody"], "dedicated-owner-repo")
        self.assertFalse((self.root / "prototypes/sample-tool").exists())

    def test_import_is_bounded_digest_checked_and_never_executes_content(self) -> None:
        import_root = Path(self.temp.name) / "import"
        import_root.mkdir()
        (import_root / "app.py").write_text("print('not executed')\n", encoding="utf-8")
        digest = imported_content_digest(import_root)
        artifacts = self.artifacts(
            posture="import-to-studio",
            source_ref="import://operator/sample-tool",
            origin_digest=DIGEST,
            imported_digest=digest,
        )
        self.apply(artifacts, import_root=import_root)
        self.assertEqual((self.root / "prototypes/sample-tool/app.py").read_text(), "print('not executed')\n")

    def test_import_secret_and_digest_mismatch_are_rejected_without_mutation(self) -> None:
        import_root = Path(self.temp.name) / "import"
        import_root.mkdir()
        (import_root / ".env").write_text("TOKEN=secret\n", encoding="utf-8")
        artifacts = self.artifacts(
            posture="import-to-studio",
            source_ref="import://operator/sample-tool",
            origin_digest=DIGEST,
            imported_digest=DIGEST,
        )
        with self.assertRaisesRegex(PacketError, "secret-bearing"):
            self.apply(artifacts, import_root=import_root)
        self.assertEqual(self.git("status", "--porcelain"), "")

        (import_root / ".env").unlink()
        (import_root / "app.txt").write_text("content\n", encoding="utf-8")
        with self.assertRaisesRegex(PacketError, "digest differs"):
            self.apply(artifacts, import_root=import_root)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_atomic_write_failure_restores_source_and_output(self) -> None:
        real_replace = os.replace
        calls = 0

        def fail_once(source, target):
            nonlocal calls
            calls += 1
            if calls == 4:
                raise OSError("simulated write failure")
            return real_replace(source, target)

        with mock.patch("packages.prototype_landing.landing.os.replace", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "simulated"):
                self.apply(self.artifacts())
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.assertFalse(self.output.exists())

    def test_schema_or_digest_tampering_is_rejected(self) -> None:
        artifacts = list(self.artifacts())
        artifacts[0]["requested_by"] = "changed-after-digest"
        with self.assertRaisesRegex(PacketError, "digest does not match"):
            self.apply(tuple(artifacts))
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_contract_bundle_digest_is_enforced(self) -> None:
        contract = self.root / "contracts/prototype-landing/prototype-landing.yaml"
        contract.write_text(contract.read_text() + "\n", encoding="utf-8")
        with self.assertRaisesRegex(PacketError, "digest differs"):
            validate_contract_bundle(self.root)


if __name__ == "__main__":
    unittest.main()
