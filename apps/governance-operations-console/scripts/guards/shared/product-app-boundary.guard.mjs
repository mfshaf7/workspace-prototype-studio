import {
  assertWorkspaceIncludes,
  importSpecifiers,
  readAppFile,
  relativeAppPath,
  walkFiles,
} from "../guard-lib.mjs";

export const guard = {
  id: "shared/product-app-boundary",
  run() {
    const failures = [];

    assertWorkspaceIncludes(
      failures,
      "docs/prototypes/governance-operations-console/product-app-boundaries.md",
      [
        "product-apps/context-board",
        "product-apps/build-tree",
        "delivery/product-adapters",
        "Product app core code must not import Delivery",
      ],
    );

    for (const file of walkFiles("src/product-apps", [".ts", ".tsx"])) {
      const relativePath = relativeAppPath(file);
      const source = readAppFile(relativePath);

      for (const specifier of importSpecifiers(source)) {
        if (
          specifier.includes("domain-workspaces/") ||
          specifier.includes("operation-workbench/")
        ) {
          failures.push(
            `${relativePath}: product apps must not import operation domain or workbench internals via "${specifier}"`,
          );
        }
      }
    }

    return failures;
  },
};

export default guard;
