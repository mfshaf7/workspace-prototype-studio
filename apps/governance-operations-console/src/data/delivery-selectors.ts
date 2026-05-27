import {
  deliveryReadModel,
  type DeliveryActionType,
  type DeliveryApplyIntent,
  type DeliveryArtNode,
  type DeliveryAuditEvent,
  type DeliveryAvailableAction,
  type DeliveryBoardSummary,
  type DeliveryPackagePosture,
  type DeliveryPackageSummary,
  type DeliveryReadModel,
  type DeliverySelectedPackage,
  type DeliveryTone,
} from "./delivery-read-model";

export type DeliveryActionDefinition = {
  action_type: DeliveryActionType;
  default_label: string;
  description: string;
  mutable: boolean;
  tone: DeliveryTone;
};

export const deliveryActionDefinitions: Record<
  DeliveryActionType,
  DeliveryActionDefinition
> = {
  "ask-advisor": {
    action_type: "ask-advisor",
    default_label: "Ask Advisor",
    description: "Request a bounded recommendation without mutating ART.",
    mutable: false,
    tone: "info",
  },
  "block": {
    action_type: "block",
    default_label: "Block",
    description: "Record a bounded blocker through the blocker workflow.",
    mutable: true,
    tone: "danger",
  },
  "clear-blocker": {
    action_type: "clear-blocker",
    default_label: "Clear Blocker",
    description: "Resolve a blocker through the bounded blocker workflow.",
    mutable: true,
    tone: "ok",
  },
  "continue-remaining-work": {
    action_type: "continue-remaining-work",
    default_label: "Continue Remaining Work",
    description: "Return to remaining executable scope after closeout review.",
    mutable: false,
    tone: "info",
  },
  "defer": {
    action_type: "defer",
    default_label: "Defer",
    description: "Park open work outside active focus with review metadata.",
    mutable: true,
    tone: "warn",
  },
  "open-audit-trail": {
    action_type: "open-audit-trail",
    default_label: "Audit Trail",
    description: "Inspect package-scoped events, receipts, and decisions.",
    mutable: false,
    tone: "muted",
  },
  "open-closeout": {
    action_type: "open-closeout",
    default_label: "Open Closeout",
    description: "Review completion evidence before final closeout mutation.",
    mutable: false,
    tone: "warn",
  },
  "open-details": {
    action_type: "open-details",
    default_label: "Open Details",
    description: "Inspect package metadata, evidence, and tree context.",
    mutable: false,
    tone: "info",
  },
  "resume": {
    action_type: "resume",
    default_label: "Resume",
    description: "Return parked work to a nonterminal execution posture.",
    mutable: true,
    tone: "info",
  },
  "retire": {
    action_type: "retire",
    default_label: "Retire",
    description: "Move invalid or superseded work to terminal inactive posture.",
    mutable: true,
    tone: "danger",
  },
  "start-work": {
    action_type: "start-work",
    default_label: "Start Work",
    description: "Move the selected executable child front toward execution.",
    mutable: true,
    tone: "ok",
  },
  "view-art-tree": {
    action_type: "view-art-tree",
    default_label: "View ART Tree",
    description: "Inspect package hierarchy without mutating ART.",
    mutable: false,
    tone: "info",
  },
};

export const deliveryPostureOrder: DeliveryPackagePosture[] = [
  "Blocked",
  "Closeout Pending",
  "In Progress",
  "Ready",
  "Deferred",
  "Done",
  "Retired",
];

export function getDeliveryReadModel(): DeliveryReadModel {
  return deliveryReadModel;
}

export function getDeliveryBoardSummary(
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryBoardSummary {
  return model.board_summary;
}

export function getDeliveryPackages(
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryPackageSummary[] {
  return [...model.packages].sort(
    (a, b) =>
      deliveryPostureOrder.indexOf(a.package_posture) -
        deliveryPostureOrder.indexOf(b.package_posture) ||
      a.legacy_epic_id - b.legacy_epic_id,
  );
}

export function getPackageById(
  deliveryPackageId: string,
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryPackageSummary | null {
  return (
    model.packages.find(
      (deliveryPackage) =>
        deliveryPackage.delivery_package_id === deliveryPackageId,
    ) ?? null
  );
}

export function getSelectedPackage(
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryPackageSummary | null {
  return getPackageById(model.selected_delivery_package_id, model);
}

export function getSelectedPackageDetails(
  model: DeliveryReadModel = deliveryReadModel,
): DeliverySelectedPackage | null {
  return (
    model.selected_packages.find(
      (deliveryPackage) =>
        deliveryPackage.delivery_package_id ===
        model.selected_delivery_package_id,
    ) ?? null
  );
}

export function getPackagePosture(
  deliveryPackageId: string,
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryPackagePosture | null {
  return getPackageById(deliveryPackageId, model)?.package_posture ?? null;
}

export function getAvailableActions(
  deliveryPackageId: string,
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryAvailableAction[] {
  return getPackageById(deliveryPackageId, model)?.available_actions ?? [];
}

export function getEnabledActions(
  deliveryPackageId: string,
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryAvailableAction[] {
  return getAvailableActions(deliveryPackageId, model).filter(
    (action) => action.enabled,
  );
}

export function getPackageAuditEvents(
  deliveryPackageId: string,
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryAuditEvent[] {
  return model.audit_events.filter(
    (event) => event.delivery_package_id === deliveryPackageId,
  );
}

export function getApplyIntent(
  intentId: string,
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryApplyIntent | null {
  return model.apply_intents.find((intent) => intent.intent_id === intentId) ?? null;
}

export function getPackageTree(
  deliveryPackageId: string,
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryArtNode | null {
  const rootId = getPackageById(deliveryPackageId, model)?.tree_root_id;

  if (!rootId) {
    return null;
  }

  return findTreeNode(rootId, model.art_tree.roots);
}

export function getSelectedPackageTree(
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryArtNode | null {
  return getPackageTree(model.selected_delivery_package_id, model);
}

export function getArtNodeById(
  nodeId: string,
  model: DeliveryReadModel = deliveryReadModel,
): DeliveryArtNode | null {
  return findTreeNode(nodeId, model.art_tree.roots);
}

export function getChildCounts(node: DeliveryArtNode): {
  blocked_child_count: number;
  open_child_count: number;
  terminal_child_count: number;
  total_child_count: number;
} {
  const descendants = flattenTree(node.children);

  return {
    blocked_child_count: descendants.filter(
      (child) => child.backend_status === "blocked",
    ).length,
    open_child_count: descendants.filter(
      (child) =>
        child.backend_status !== "done" && child.backend_status !== "retired",
    ).length,
    terminal_child_count: descendants.filter(
      (child) =>
        child.backend_status === "done" || child.backend_status === "retired",
    ).length,
    total_child_count: descendants.length,
  };
}

export function getActionDefinition(
  actionType: DeliveryActionType,
): DeliveryActionDefinition {
  return deliveryActionDefinitions[actionType];
}

function findTreeNode(
  nodeId: string,
  nodes: DeliveryArtNode[],
): DeliveryArtNode | null {
  for (const node of nodes) {
    if (node.id === nodeId) {
      return node;
    }

    const childMatch = findTreeNode(nodeId, node.children);

    if (childMatch) {
      return childMatch;
    }
  }

  return null;
}

function flattenTree(nodes: DeliveryArtNode[]): DeliveryArtNode[] {
  return nodes.flatMap((node) => [node, ...flattenTree(node.children)]);
}
