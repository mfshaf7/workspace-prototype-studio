import {
  readWorkspaceFile,
  workspacePathExists,
} from "../guard-lib.mjs";

const operationWorkbenchContract =
  "docs/prototypes/governance-operations-console/operation-workbench-contract.md";

const requiredTerms = [
  "### Pre-Baseline Authority And Artifact Model",
  "authorize live wiring",
  "Do not implement a generic mutable `local overlay` record",
  "### Multi-Source Projection And Preconditions Rule",
  "### Domain State Machine Rule",
  "current state + command + preconditions -> accepted transition or rejection",
  "### Capability And Action Semantics Rule",
  "prototype-local simulation",
  "### Cross-Domain Packet And Custody Rule",
  "The producer prepares and dispatches a packet; it does not mutate the consumer's",
  "### Post-Baseline Live Runtime Authority Rule",
  "### Schema, Identity, Ordering, And Local Retention Rule",
  "a receipt is immutable action evidence",
  "rollback returns the domain to prototype-local or read-only mode",
];

export const guard = {
  id: "shared/operation-authority-contract",
  run() {
    if (!workspacePathExists(operationWorkbenchContract)) {
      return [`${operationWorkbenchContract}: missing operation contract`];
    }

    const source = readWorkspaceFile(operationWorkbenchContract);

    return requiredTerms.flatMap((term) =>
      source.includes(term)
        ? []
        : [`${operationWorkbenchContract}: missing authority contract token "${term}"`],
    );
  },
};

export default guard;
