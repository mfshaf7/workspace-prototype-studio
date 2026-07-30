import {
  assertAppPathAbsent,
  assertIncludes,
  assertOmits,
  assertWorkspaceFile,
  assertWorkspaceIncludes,
  readWorkspaceFile,
  workspacePathExists,
} from "../guard-lib.mjs";

const modelPath =
  "docs/prototypes/governance-operations-console/architecture/system-model.yaml";
const lifecycleView =
  "docs/prototypes/governance-operations-console/architecture/views/04-lifecycle.md";
const handoffView =
  "docs/prototypes/governance-operations-console/architecture/views/05-handoffs.md";
const classificationDefinition =
  "docs/prototypes/governance-operations-console/orchestration-definitions/workspace-entrant-classification.md";
const promotionDefinition =
  "docs/prototypes/governance-operations-console/orchestration-definitions/workspace-entrant-promotion.md";

const staleTerms = [
  "workspace-product-intake",
  "Workspace Product Intake",
  "workspace-product-admission",
  "delivery-to-product-intake",
  "product-intake-to-portfolio",
];

const activeDocs = [
  "docs/prototypes/governance-operations-console/architecture/system-model.yaml",
  "docs/prototypes/governance-operations-console/architecture/views/01-system-context.md",
  "docs/prototypes/governance-operations-console/architecture/views/02-operator-surfaces.md",
  "docs/prototypes/governance-operations-console/architecture/views/03-authority-map.md",
  lifecycleView,
  handoffView,
  "docs/prototypes/governance-operations-console/architecture/views/07-capability-maturity.md",
  "docs/prototypes/governance-operations-console/operation-workbench-contract.md",
  "docs/prototypes/governance-operations-console/orchestration-boundary-contract.md",
  "docs/prototypes/governance-operations-console/orchestration-use-case-matrix.md",
  "docs/prototypes/governance-operations-console/domain-contracts/portfolio.md",
  "docs/prototypes/governance-operations-console/surface-contracts/lifecycle-transitions.md",
  classificationDefinition,
  promotionDefinition,
];

export const guard = {
  id: "shared/workspace-intake-boundary",
  run() {
    const failures = [];

    assertAppPathAbsent(
      failures,
      "src/domain-workspaces/workspace-product-intake",
      "Workspace Intake is an embedded authority workflow, not a Workbench domain",
    );
    if (
      workspacePathExists(
        "docs/prototypes/governance-operations-console/domain-contracts/workspace-product-intake.md",
      )
    ) {
      failures.push(
        "domain-contracts/workspace-product-intake.md: obsolete standalone domain contract must remain absent",
      );
    }

    for (const path of [
      "src/operation-workbench/operation-workbench-domain-registry.ts",
      "src/operation-workbench/operation-workbench-host.tsx",
      "src/operation-workbench/operation-workbench-selector-model.ts",
    ]) {
      assertOmits(failures, path, staleTerms);
    }

    assertIncludes(
      failures,
      "src/operation-workbench/operation-workbench-selector.tsx",
      ["xl:grid-cols-7"],
    );
    assertIncludes(
      failures,
      "src/domain-workspaces/portfolio/work-model/publication/product-publication-requirements.ts",
      [
        '"active-product-inventory"',
        "workspace-governance://products/",
      ],
    );
    assertOmits(
      failures,
      "src/domain-workspaces/portfolio/work-model/publication/product-publication-requirements.ts",
      staleTerms,
    );

    for (const path of [classificationDefinition, promotionDefinition]) {
      assertWorkspaceFile(failures, path);
    }
    assertWorkspaceIncludes(failures, classificationDefinition, [
      "Definition id: `workspace.entrant.classify`",
      "Classification: `synchronous`",
      "workspace-governance/contracts/intake-register.yaml",
      "Classification is not active registration.",
      "no standalone Product Intake operation",
    ]);
    assertWorkspaceIncludes(failures, promotionDefinition, [
      "Definition id: `workspace.entrant.promote`",
      "Classification: `durable-candidate`",
      "workspace-governance/contracts/repos.yaml",
      "workspace-governance/contracts/products.yaml",
      "workspace-governance/contracts/components.yaml",
      "must never overlap",
    ]);

    assertWorkspaceIncludes(failures, modelPath, [
      "workspace-intake:",
      "kind: authority-workflow",
      "workspace-active-inventory:",
      "workspace-governance/contracts/intake-register.yaml",
      "workspace-governance/contracts/repos.yaml",
      "workspace-governance/contracts/products.yaml",
      "workspace-governance/contracts/components.yaml",
      "repository-to-workspace-intake:",
      "prototype-to-workspace-intake:",
      "delivery-to-workspace-intake:",
      "workspace-intake-to-active-inventory:",
      "active-product-to-portfolio:",
    ]);
    assertWorkspaceIncludes(
      failures,
      "docs/prototypes/governance-operations-console/architecture/views/01-system-context.md",
      ["Operation Workbench<br/>7 operation domains"],
    );
    assertWorkspaceIncludes(failures, lifecycleView, [
      "Workspace Intake classification",
      "Active inventory promotion",
      "active real product",
    ]);
    assertWorkspaceIncludes(failures, handoffView, [
      "Classification and promotion are separate workflows and receipts.",
      "Workspace Intake classification",
      "Active inventory promotion",
    ]);

    for (const path of activeDocs) {
      const source = readWorkspaceFile(path);
      for (const term of staleTerms) {
        if (source.includes(term)) {
          failures.push(`${path}: must not retain stale token "${term}"`);
        }
      }
    }

    return failures;
  },
};

export default guard;
