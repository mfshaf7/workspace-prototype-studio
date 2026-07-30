import {
  assertAppPathAbsent,
  assertIncludes,
  assertOmits,
  assertWorkspaceFile,
  readWorkspaceFile,
} from "../guard-lib.mjs";

const authorityContract =
  "docs/prototypes/governance-operations-console/authority-decision-contract.md";

const activeDocs = [
  "docs/operating-model.md",
  "docs/prototypes/governance-operations-console/README.md",
  "docs/prototypes/governance-operations-console/architecture/README.md",
  "docs/prototypes/governance-operations-console/architecture/system-model.yaml",
  "docs/prototypes/governance-operations-console/architecture/views/01-system-context.md",
  "docs/prototypes/governance-operations-console/architecture/views/02-operator-surfaces.md",
  "docs/prototypes/governance-operations-console/architecture/views/03-authority-map.md",
  "docs/prototypes/governance-operations-console/architecture/views/04-lifecycle.md",
  "docs/prototypes/governance-operations-console/architecture/views/05-handoffs.md",
  "docs/prototypes/governance-operations-console/architecture/views/06-runtime-release.md",
  "docs/prototypes/governance-operations-console/architecture/views/07-capability-maturity.md",
  "docs/prototypes/governance-operations-console/backlog.md",
  "docs/prototypes/governance-operations-console/brief.md",
  "docs/prototypes/governance-operations-console/design-profile.md",
  "docs/prototypes/governance-operations-console/implementation-audit.md",
  "docs/prototypes/governance-operations-console/operation-workbench-contract.md",
  "docs/prototypes/governance-operations-console/orchestration-boundary-contract.md",
  "docs/prototypes/governance-operations-console/orchestration-use-case-matrix.md",
  "docs/prototypes/governance-operations-console/system-design.md",
  "docs/prototypes/governance-operations-console/domain-contracts/README.md",
  "docs/prototypes/governance-operations-console/domain-contracts/model-operations.md",
  "docs/prototypes/governance-operations-console/domain-contracts/orchestration.md",
  "docs/prototypes/governance-operations-console/domain-contracts/portfolio.md",
  "docs/prototypes/governance-operations-console/domain-contracts/prototype.md",
  "docs/prototypes/governance-operations-console/surface-contracts/lifecycle-transitions.md",
];

const staleDomainTerms = [
  "Risk / Exception",
  "Risk/Exception",
  "risk-exception",
];

export const guard = {
  id: "shared/authority-decision-boundary",
  run() {
    const failures = [];

    assertWorkspaceFile(failures, authorityContract);
    assertAppPathAbsent(
      failures,
      "src/domain-workspaces/risk-exception",
      "authority decisions are not an Operation Workbench domain",
    );
    assertAppPathAbsent(
      failures,
      "src/movement-control",
      "Lifecycle Transitions replaced the historical Movement Control surface",
    );

    assertIncludes(
      failures,
      "src/operation-workbench/operation-workbench-selector.tsx",
      ["xl:grid-cols-7"],
    );
    assertOmits(failures, "src/app/page.tsx", staleDomainTerms);
    assertOmits(
      failures,
      "src/operation-workbench/operation-workbench-selector-model.ts",
      staleDomainTerms,
    );
    assertOmits(failures, "src/domain-workspaces/index.ts", ["risk-exception"]);
    assertOmits(
      failures,
      "src/lifecycle-transitions/presentation/workspace/lifecycle-transitions-workspace.tsx",
      staleDomainTerms,
    );

    if (failures.length === 0) {
      const contract = readWorkspaceFile(authorityContract);
      for (const term of [
        "Authority Decision Request",
        "Authority Decision Receipt",
        "The request is not approval.",
        "The originating domain must validate authority",
        "Do not add a generic Risk / Exception register",
      ]) {
        if (!contract.includes(term)) {
          failures.push(`${authorityContract}: missing required token "${term}"`);
        }
      }
    }

    for (const path of activeDocs) {
      const source = readWorkspaceFile(path);
      for (const term of staleDomainTerms) {
        if (source.includes(term)) {
          failures.push(`${path}: must not retain generic domain token "${term}"`);
        }
      }
    }

    return failures;
  },
};

export default guard;
