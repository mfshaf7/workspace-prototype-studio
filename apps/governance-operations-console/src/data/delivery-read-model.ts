export type DeliverySourceTruth =
  | "mock"
  | "OOS"
  | "OpenProject-backed OOS"
  | "Workspace Delivery backend";

export type DeliveryProjectionStatus =
  | "backend_unavailable"
  | "fresh"
  | "permission_denied"
  | "projection_sync_required"
  | "read_error"
  | "stale";

export type DeliveryBackendStatus =
  | "blocked"
  | "done"
  | "in-progress"
  | "new"
  | "parked"
  | "ready"
  | "retired";

export type DeliveryPackagePosture =
  | "Blocked"
  | "Closeout Pending"
  | "Deferred"
  | "Done"
  | "In Progress"
  | "Ready"
  | "Retired";

export type DeliveryWorkflowStage =
  | "audit_only"
  | "execution"
  | "intake"
  | "refinement"
  | "work_design";

export type DeliveryComponentType =
  | "Defect"
  | "Epic"
  | "Feature"
  | "Milestone"
  | "PI Objective"
  | "Risk"
  | "Task"
  | "User story";

export type DeliveryTone =
  | "danger"
  | "info"
  | "muted"
  | "ok"
  | "stale"
  | "warn";

export type DeliveryActionType =
  | "ask-advisor"
  | "block"
  | "clear-blocker"
  | "continue-remaining-work"
  | "defer"
  | "open-audit-trail"
  | "open-closeout"
  | "open-details"
  | "resume"
  | "retire"
  | "start-work"
  | "view-art-tree";

export type DeliveryActionScope =
  | "child_front"
  | "package"
  | "package_with_children"
  | "read_only";

export type DeliveryReceiptCategory =
  | "accepted"
  | "apply_failed"
  | "blocked_by_gate"
  | "projection_sync_required"
  | "rejected";

export type DeliveryMilestoneKind =
  | "external_commitment"
  | "governance_review"
  | "integration_gate"
  | "learning_review"
  | "pi_boundary";

export type DeliveryProjectionState = {
  checked_at: string;
  detail: string;
  source_revision: string;
  status: DeliveryProjectionStatus;
};

export type DeliveryBoardSummary = {
  total_packages: number;
  by_posture: Record<DeliveryPackagePosture, number>;
  stale_count: number;
  blocked_count: number;
  closeout_pending_count: number;
};

export type DeliveryAvailableAction = {
  action_type: DeliveryActionType;
  enabled: boolean;
  expected_backend_route: string | null;
  label: string;
  reason: string;
  scope: DeliveryActionScope;
  tone: DeliveryTone;
};

export type DeliveryPackageSummary = {
  available_actions: DeliveryAvailableAction[];
  backend_status: DeliveryBackendStatus;
  delivery_package_id: string;
  display_name: string;
  legacy_epic_id: number;
  open_child_count: number;
  package_posture: DeliveryPackagePosture;
  source_ref: string;
  summary: string;
  target_pi: string | null;
  tone: DeliveryTone;
  tree_root_id: string;
  workflow_stage: DeliveryWorkflowStage;
};

export type DeliveryArtMapLane = {
  id: string;
  label: string;
  packages: Array<{
    delivery_package_id: string;
    display_name: string;
    legacy_epic_id: number;
    package_posture: DeliveryPackagePosture;
    selected: boolean;
    tone: DeliveryTone;
  }>;
  summary: string;
};

export type DeliveryArtNode = {
  backend_status: DeliveryBackendStatus;
  children: DeliveryArtNode[];
  component_type: DeliveryComponentType;
  description: string;
  id: string;
  legacy_work_package_id: number | null;
  metadata_status: "complete" | "missing" | "not_applicable" | "partial";
  title: string;
  tone: DeliveryTone;
};

export type DeliveryMilestone = {
  checkpoint_kind: DeliveryMilestoneKind;
  evidence_refs?: string[];
  execution_context: string;
  exit_condition: string;
  id: string;
  status: Extract<DeliveryBackendStatus, "done" | "new" | "ready" | "retired">;
  target_pi: string;
  title: string;
};

export type DeliverySelectedPackage = {
  active_front_id: string | null;
  advisor_summary: string;
  delivery_package_id: string;
  lineage_refs: {
    architecture_anchor_ref: string | null;
    required_upstream_ref: string | null;
  };
  milestones: DeliveryMilestone[];
  next_front_id: string | null;
  owner_repo: string;
  source_revision: string;
};

export type DeliveryApplyIntent = {
  action_type: DeliveryActionType;
  advisor_reason: string | null;
  dirty_state: "clean" | "dirty" | "stale";
  expected_backend_route: string | null;
  gate_checks: Array<{
    label: string;
    passed: boolean;
    tone: DeliveryTone;
  }>;
  intent_id: string;
  operator_payload: Record<string, string>;
  receipt_category: DeliveryReceiptCategory | null;
  target_display_name: string;
  target_id: string;
  target_type: DeliveryComponentType;
};

export type DeliveryAuditEvent = {
  actor: string;
  category:
    | "action"
    | "apply"
    | "milestone"
    | "projection"
    | "readiness"
    | "receipt";
  delivery_package_id: string;
  detail: string;
  event_id: string;
  occurred_at: string;
  receipt_id: string | null;
  title: string;
  tone: DeliveryTone;
};

export type DeliveryReadModel = {
  apply_intents: DeliveryApplyIntent[];
  art_map: {
    lanes: DeliveryArtMapLane[];
  };
  art_tree: {
    roots: DeliveryArtNode[];
  };
  audit_events: DeliveryAuditEvent[];
  board_summary: DeliveryBoardSummary;
  generated_at: string;
  packages: DeliveryPackageSummary[];
  projection_state: DeliveryProjectionState;
  schema_version: 1;
  selected_delivery_package_id: string;
  selected_packages: DeliverySelectedPackage[];
  source_truth: DeliverySourceTruth;
};

const readOnlyActions: DeliveryAvailableAction[] = [
  {
    action_type: "open-details",
    enabled: true,
    expected_backend_route: null,
    label: "Open Details",
    reason: "Inspect package evidence, metadata, and tree context.",
    scope: "read_only",
    tone: "info",
  },
  {
    action_type: "open-audit-trail",
    enabled: true,
    expected_backend_route: null,
    label: "Audit Trail",
    reason: "Read package-scoped receipt and decision history.",
    scope: "read_only",
    tone: "muted",
  },
];

function packageActions(
  actions: DeliveryAvailableAction[],
): DeliveryAvailableAction[] {
  return [...actions, ...readOnlyActions];
}

export const deliveryReadModel: DeliveryReadModel = {
  schema_version: 1,
  generated_at: "2026-05-27T06:54:00.000Z",
  source_truth: "mock",
  selected_delivery_package_id: "pkg-698",
  projection_state: {
    checked_at: "2026-05-27T06:54:00.000Z",
    detail:
      "Prototype read model mirrors the locked Delivery architecture discussion. It is not live ART truth.",
    source_revision: "mock-delivery-v1",
    status: "fresh",
  },
  board_summary: {
    total_packages: 8,
    blocked_count: 1,
    closeout_pending_count: 1,
    stale_count: 1,
    by_posture: {
      "Blocked": 1,
      "Closeout Pending": 1,
      "Deferred": 1,
      "Done": 1,
      "In Progress": 1,
      "Ready": 2,
      "Retired": 1,
    },
  },
  packages: [
    {
      available_actions: readOnlyActions,
      backend_status: "new",
      delivery_package_id: "pkg-intake-394",
      display_name: "Client Insight Delivery Shell",
      legacy_epic_id: 394,
      open_child_count: 0,
      package_posture: "Ready",
      source_ref: "Proposal IDEA-394",
      summary:
        "Accepted proposal is ready to become an ART-backed Delivery Package shell.",
      target_pi: null,
      tone: "warn",
      tree_root_id: "node-intake-394",
      workflow_stage: "intake",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "new",
      delivery_package_id: "pkg-intake-402",
      display_name: "Workspace Audit Evidence Shell",
      legacy_epic_id: 402,
      open_child_count: 0,
      package_posture: "Ready",
      source_ref: "Proposal IDEA-402",
      summary:
        "Accepted governance audit proposal is ready for root Epic shell creation.",
      target_pi: null,
      tone: "warn",
      tree_root_id: "node-intake-402",
      workflow_stage: "intake",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "blocked",
      delivery_package_id: "pkg-intake-417",
      display_name: "Security Review Intake Gap",
      legacy_epic_id: 417,
      open_child_count: 0,
      package_posture: "Blocked",
      source_ref: "Proposal IDEA-417",
      summary:
        "Accepted proposal is missing owning repository evidence before Delivery shell creation.",
      target_pi: null,
      tone: "danger",
      tree_root_id: "node-intake-417",
      workflow_stage: "intake",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "new",
      delivery_package_id: "pkg-intake-428",
      display_name: "Operator Console Intake Split",
      legacy_epic_id: 428,
      open_child_count: 0,
      package_posture: "Ready",
      source_ref: "Proposal IDEA-428",
      summary:
        "Console proposal is accepted and waiting for Delivery package shell confirmation.",
      target_pi: null,
      tone: "warn",
      tree_root_id: "node-intake-428",
      workflow_stage: "intake",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "parked",
      delivery_package_id: "pkg-intake-431",
      display_name: "Telemetry Intake Parking",
      legacy_epic_id: 431,
      open_child_count: 0,
      package_posture: "Deferred",
      source_ref: "Proposal IDEA-431",
      summary:
        "Accepted proposal is intentionally parked until platform telemetry scope is clarified.",
      target_pi: null,
      tone: "muted",
      tree_root_id: "node-intake-431",
      workflow_stage: "intake",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "new",
      delivery_package_id: "pkg-intake-436",
      display_name: "Repository Lifecycle Intake",
      legacy_epic_id: 436,
      open_child_count: 0,
      package_posture: "Ready",
      source_ref: "Proposal IDEA-436",
      summary:
        "Accepted repository lifecycle proposal is ready for intake handoff review.",
      target_pi: null,
      tone: "warn",
      tree_root_id: "node-intake-436",
      workflow_stage: "intake",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "new",
      delivery_package_id: "pkg-design-712",
      display_name: "Context Admission Work Design",
      legacy_epic_id: 712,
      open_child_count: 0,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #712",
      summary:
        "AI/operator design session is shaping the Epic, Feature, User story, and Risk tree before ART apply.",
      target_pi: "PI-2026-03",
      tone: "info",
      tree_root_id: "node-design-712",
      workflow_stage: "work_design",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "new",
      delivery_package_id: "pkg-design-724",
      display_name: "Control Fabric ART Design",
      legacy_epic_id: 724,
      open_child_count: 0,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #724",
      summary:
        "Design session needs feature and user-story decomposition before draft apply.",
      target_pi: "PI-2026-03",
      tone: "info",
      tree_root_id: "node-design-724",
      workflow_stage: "work_design",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "blocked",
      delivery_package_id: "pkg-design-732",
      display_name: "OOS Adapter Work Design Block",
      legacy_epic_id: 732,
      open_child_count: 0,
      package_posture: "Blocked",
      source_ref: "OpenProject Epic #732",
      summary:
        "Design cannot continue until adapter ownership and source boundary are confirmed.",
      target_pi: "PI-2026-03",
      tone: "danger",
      tree_root_id: "node-design-732",
      workflow_stage: "work_design",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "new",
      delivery_package_id: "pkg-design-739",
      display_name: "Context Gateway Draft Shape",
      legacy_epic_id: 739,
      open_child_count: 0,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #739",
      summary:
        "AI/operator session is building the package tree for context projection controls.",
      target_pi: "PI-2026-03",
      tone: "info",
      tree_root_id: "node-design-739",
      workflow_stage: "work_design",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "parked",
      delivery_package_id: "pkg-design-741",
      display_name: "Platform Runtime Design Hold",
      legacy_epic_id: 741,
      open_child_count: 0,
      package_posture: "Deferred",
      source_ref: "OpenProject Epic #741",
      summary:
        "Work design is parked while platform runtime scope is sequenced behind upstream work.",
      target_pi: null,
      tone: "warn",
      tree_root_id: "node-design-741",
      workflow_stage: "work_design",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "new",
      delivery_package_id: "pkg-design-746",
      display_name: "Audit Trail Work Design",
      legacy_epic_id: 746,
      open_child_count: 0,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #746",
      summary:
        "Package design is ready for tree drafting but still needs risk branches.",
      target_pi: "PI-2026-04",
      tone: "info",
      tree_root_id: "node-design-746",
      workflow_stage: "work_design",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "ready",
      delivery_package_id: "pkg-refinement-760",
      display_name: "Adapter Contract Metadata Repair",
      legacy_epic_id: 760,
      open_child_count: 7,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #760",
      summary:
        "Package tree exists, but execution metadata still needs whole-package completion before it can enter the board.",
      target_pi: "PI-2026-03",
      tone: "warn",
      tree_root_id: "node-refinement-760",
      workflow_stage: "refinement",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "ready",
      delivery_package_id: "pkg-refinement-766",
      display_name: "WGCF Receipt Refinement",
      legacy_epic_id: 766,
      open_child_count: 9,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #766",
      summary:
        "Whole-package metadata is mostly complete but milestone checkpoint rules still need review.",
      target_pi: "PI-2026-03",
      tone: "warn",
      tree_root_id: "node-refinement-766",
      workflow_stage: "refinement",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "blocked",
      delivery_package_id: "pkg-refinement-771",
      display_name: "Security Boundary Metadata Block",
      legacy_epic_id: 771,
      open_child_count: 5,
      package_posture: "Blocked",
      source_ref: "OpenProject Epic #771",
      summary:
        "Refinement is blocked until security boundary ownership is accepted.",
      target_pi: "PI-2026-03",
      tone: "danger",
      tree_root_id: "node-refinement-771",
      workflow_stage: "refinement",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "ready",
      delivery_package_id: "pkg-refinement-778",
      display_name: "Repository Onboarding Metadata",
      legacy_epic_id: 778,
      open_child_count: 4,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #778",
      summary:
        "Owner repo and team metadata are ready for final readiness review.",
      target_pi: "PI-2026-04",
      tone: "warn",
      tree_root_id: "node-refinement-778",
      workflow_stage: "refinement",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "parked",
      delivery_package_id: "pkg-refinement-782",
      display_name: "Deferred Metadata Repair",
      legacy_epic_id: 782,
      open_child_count: 6,
      package_posture: "Deferred",
      source_ref: "OpenProject Epic #782",
      summary:
        "Refinement is parked until upstream architecture anchor is settled.",
      target_pi: null,
      tone: "muted",
      tree_root_id: "node-refinement-782",
      workflow_stage: "refinement",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "ready",
      delivery_package_id: "pkg-refinement-789",
      display_name: "Operator Workflow Metadata",
      legacy_epic_id: 789,
      open_child_count: 8,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #789",
      summary:
        "Operator workflow metadata is complete enough for final review before board entry.",
      target_pi: "PI-2026-04",
      tone: "warn",
      tree_root_id: "node-refinement-789",
      workflow_stage: "refinement",
    },
    {
      available_actions: packageActions([
        {
          action_type: "start-work",
          enabled: true,
          expected_backend_route: "work-item.update",
          label: "Start Work",
          reason: "A next executable child front is selected and ready.",
          scope: "child_front",
          tone: "ok",
        },
        {
          action_type: "defer",
          enabled: true,
          expected_backend_route: "work-item.parking",
          label: "Defer",
          reason: "Operator may intentionally remove the package from active focus.",
          scope: "package_with_children",
          tone: "warn",
        },
      ]),
      backend_status: "ready",
      delivery_package_id: "pkg-698",
      display_name: "Governed AI Control Plane",
      legacy_epic_id: 698,
      open_child_count: 6,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #698",
      summary: "Control-plane work is refined and ready for selected front execution.",
      target_pi: "PI-2026-03",
      tone: "info",
      tree_root_id: "node-698",
      workflow_stage: "execution",
    },
    {
      available_actions: packageActions([
        {
          action_type: "block",
          enabled: true,
          expected_backend_route: "work-item.blocker",
          label: "Block",
          reason: "Active front has an unresolved execution blocker.",
          scope: "child_front",
          tone: "danger",
        },
        {
          action_type: "defer",
          enabled: true,
          expected_backend_route: "work-item.parking",
          label: "Defer",
          reason: "Blocked scope may be removed from active focus with justification.",
          scope: "package_with_children",
          tone: "warn",
        },
      ]),
      backend_status: "blocked",
      delivery_package_id: "pkg-753",
      display_name: "Receipt Projection Repair",
      legacy_epic_id: 753,
      open_child_count: 4,
      package_posture: "Blocked",
      source_ref: "OpenProject Epic #753",
      summary: "Receipt projection signal is blocked until source drift is repaired.",
      target_pi: "PI-2026-03",
      tone: "danger",
      tree_root_id: "node-753",
      workflow_stage: "execution",
    },
    {
      available_actions: packageActions([
        {
          action_type: "open-closeout",
          enabled: true,
          expected_backend_route: null,
          label: "Open Closeout",
          reason: "Completed child work needs closeout evidence review.",
          scope: "package_with_children",
          tone: "warn",
        },
      ]),
      backend_status: "in-progress",
      delivery_package_id: "pkg-681",
      display_name: "Broker Apply Controls",
      legacy_epic_id: 681,
      open_child_count: 2,
      package_posture: "Closeout Pending",
      source_ref: "OpenProject Epic #681",
      summary: "Most children are complete; closeout review decides the remaining move.",
      target_pi: "PI-2026-02",
      tone: "warn",
      tree_root_id: "node-681",
      workflow_stage: "execution",
    },
    {
      available_actions: packageActions([
        {
          action_type: "resume",
          enabled: true,
          expected_backend_route: "work-item.parking",
          label: "Resume",
          reason: "Parked scope can return to ready posture after review.",
          scope: "package_with_children",
          tone: "info",
        },
      ]),
      backend_status: "parked",
      delivery_package_id: "pkg-087",
      display_name: "Security Baseline Review",
      legacy_epic_id: 87,
      open_child_count: 5,
      package_posture: "Deferred",
      source_ref: "OpenProject Epic #87",
      summary: "Security baseline remains intentionally parked outside current focus.",
      target_pi: null,
      tone: "warn",
      tree_root_id: "node-087",
      workflow_stage: "execution",
    },
    {
      available_actions: packageActions([
        {
          action_type: "continue-remaining-work",
          enabled: true,
          expected_backend_route: null,
          label: "Continue Remaining Work",
          reason: "Read model found remaining open scope after a completed front.",
          scope: "read_only",
          tone: "info",
        },
      ]),
      backend_status: "in-progress",
      delivery_package_id: "pkg-714",
      display_name: "Broker Draft Validation",
      legacy_epic_id: 714,
      open_child_count: 3,
      package_posture: "In Progress",
      source_ref: "OpenProject Epic #714",
      summary: "Execution has started and remaining child work items are still open.",
      target_pi: "PI-2026-03",
      tone: "ok",
      tree_root_id: "node-714",
      workflow_stage: "execution",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "done",
      delivery_package_id: "pkg-540",
      display_name: "Stale Open Closeout",
      legacy_epic_id: 540,
      open_child_count: 0,
      package_posture: "Done",
      source_ref: "OpenProject Epic #540",
      summary: "Closed with accepted receipt and no remaining child work.",
      target_pi: "PI-2026-02",
      tone: "ok",
      tree_root_id: "node-540",
      workflow_stage: "audit_only",
    },
    {
      available_actions: readOnlyActions,
      backend_status: "retired",
      delivery_package_id: "pkg-251",
      display_name: "Superseded AI Assist Slice",
      legacy_epic_id: 251,
      open_child_count: 0,
      package_posture: "Retired",
      source_ref: "OpenProject Epic #251",
      summary: "Superseded scope is retained for audit only.",
      target_pi: null,
      tone: "muted",
      tree_root_id: "node-251",
      workflow_stage: "audit_only",
    },
    {
      available_actions: packageActions([
        {
          action_type: "open-details",
          enabled: false,
          expected_backend_route: null,
          label: "Open Details",
          reason: "Projection is stale; refresh before acting.",
          scope: "read_only",
          tone: "stale",
        },
      ]),
      backend_status: "ready",
      delivery_package_id: "pkg-900",
      display_name: "Large Tree Migration Probe",
      legacy_epic_id: 900,
      open_child_count: 42,
      package_posture: "Ready",
      source_ref: "OpenProject Epic #900",
      summary: "Large-tree mock package for collapsed rendering and future lazy loading.",
      target_pi: "PI-2026-04",
      tone: "stale",
      tree_root_id: "node-900",
      workflow_stage: "execution",
    },
  ],
  art_map: {
    lanes: [
      {
        id: "family-governance",
        label: "Governance Control Plane",
        summary: "2 ready, 1 blocked",
        packages: [
          {
            delivery_package_id: "pkg-698",
            display_name: "Governed AI Control Plane",
            legacy_epic_id: 698,
            package_posture: "Ready",
            selected: true,
            tone: "info",
          },
          {
            delivery_package_id: "pkg-753",
            display_name: "Receipt Projection Repair",
            legacy_epic_id: 753,
            package_posture: "Blocked",
            selected: false,
            tone: "danger",
          },
          {
            delivery_package_id: "pkg-900",
            display_name: "Large Tree Migration Probe",
            legacy_epic_id: 900,
            package_posture: "Ready",
            selected: false,
            tone: "stale",
          },
        ],
      },
      {
        id: "family-broker",
        label: "Operator Broker",
        summary: "1 active, 1 closeout",
        packages: [
          {
            delivery_package_id: "pkg-714",
            display_name: "Broker Draft Validation",
            legacy_epic_id: 714,
            package_posture: "In Progress",
            selected: false,
            tone: "ok",
          },
          {
            delivery_package_id: "pkg-681",
            display_name: "Broker Apply Controls",
            legacy_epic_id: 681,
            package_posture: "Closeout Pending",
            selected: false,
            tone: "warn",
          },
        ],
      },
      {
        id: "family-security",
        label: "Security Architecture",
        summary: "1 deferred, 1 retired",
        packages: [
          {
            delivery_package_id: "pkg-087",
            display_name: "Security Baseline Review",
            legacy_epic_id: 87,
            package_posture: "Deferred",
            selected: false,
            tone: "warn",
          },
          {
            delivery_package_id: "pkg-251",
            display_name: "Superseded AI Assist Slice",
            legacy_epic_id: 251,
            package_posture: "Retired",
            selected: false,
            tone: "muted",
          },
        ],
      },
    ],
  },
  art_tree: {
    roots: [
      {
        id: "node-698",
        legacy_work_package_id: 698,
        component_type: "Epic",
        title: "Governed AI Control Plane",
        description: "Delivery package shell with ready child work items and one milestone checkpoint.",
        backend_status: "ready",
        metadata_status: "complete",
        tone: "info",
        children: [
          {
            id: "node-698-feature-1",
            legacy_work_package_id: 710,
            component_type: "Feature",
            title: "Broker-owned orchestration path",
            description: "OOS mutation draft and apply path stays explicit.",
            backend_status: "ready",
            metadata_status: "complete",
            tone: "info",
            children: [
              {
                id: "node-698-story-1",
                legacy_work_package_id: 714,
                component_type: "User story",
                title: "Validate mutation draft before apply",
                description: "Selected executable front for the ready package.",
                backend_status: "ready",
                metadata_status: "complete",
                tone: "ok",
                children: [],
              },
              {
                id: "node-698-story-2",
                legacy_work_package_id: 715,
                component_type: "User story",
                title: "Render apply receipt in console",
                description: "Open front waiting behind the selected story.",
                backend_status: "new",
                metadata_status: "complete",
                tone: "info",
                children: [],
              },
            ],
          },
          {
            id: "node-698-feature-2",
            legacy_work_package_id: 720,
            component_type: "Feature",
            title: "Projection checkpoint handling",
            description: "Future orchestration path keeps stale projection visible.",
            backend_status: "new",
            metadata_status: "partial",
            tone: "warn",
            children: [],
          },
          {
            id: "node-698-risk-1",
            legacy_work_package_id: 721,
            component_type: "Risk",
            title: "Read-model drift after adapter write",
            description: "Risk remains visible but not executable.",
            backend_status: "new",
            metadata_status: "complete",
            tone: "warn",
            children: [],
          },
          {
            id: "node-698-milestone-1",
            legacy_work_package_id: 722,
            component_type: "Milestone",
            title: "Governance review checkpoint",
            description: "Checkpoint only; not an execution container.",
            backend_status: "ready",
            metadata_status: "complete",
            tone: "info",
            children: [],
          },
        ],
      },
      {
        id: "node-900",
        legacy_work_package_id: 900,
        component_type: "Epic",
        title: "Large Tree Migration Probe",
        description: "Collapsed-count mock package for large ART trees.",
        backend_status: "ready",
        metadata_status: "complete",
        tone: "stale",
        children: [],
      },
    ],
  },
  selected_packages: [
    {
      delivery_package_id: "pkg-698",
      active_front_id: null,
      advisor_summary:
        "Advisor recommends starting User story #714 after operator confirms source revision is current.",
      lineage_refs: {
        architecture_anchor_ref: "Epic #681",
        required_upstream_ref: "Epic #540",
      },
      milestones: [
        {
          checkpoint_kind: "governance_review",
          evidence_refs: ["WGCF-READY-698"],
          execution_context:
            "Review control-plane governance assumptions before reducing OpenProject dependency.",
          exit_condition: "Operator accepts WGCF readiness receipt and OOS draft route proof.",
          id: "milestone-698-governance-review",
          status: "ready",
          target_pi: "PI-2026-03",
          title: "Governance review checkpoint",
        },
      ],
      next_front_id: "node-698-story-1",
      owner_repo: "workspace-governance-control-fabric",
      source_revision: "mock-delivery-v1:pkg-698",
    },
  ],
  apply_intents: [
    {
      action_type: "start-work",
      advisor_reason:
        "The selected story has complete metadata, Target PI, and no active blocker.",
      dirty_state: "clean",
      expected_backend_route: "work-item.update",
      gate_checks: [
        {
          label: "Target front selected",
          passed: true,
          tone: "ok",
        },
        {
          label: "Source revision current",
          passed: true,
          tone: "ok",
        },
        {
          label: "No active blocker",
          passed: true,
          tone: "ok",
        },
      ],
      intent_id: "intent-start-698-714",
      operator_payload: {
        target_status: "in-progress",
        operator_note: "Start selected broker validation story.",
      },
      receipt_category: null,
      target_display_name: "User story #714 - Validate mutation draft before apply",
      target_id: "node-698-story-1",
      target_type: "User story",
    },
  ],
  audit_events: [
    {
      actor: "operator",
      category: "readiness",
      delivery_package_id: "pkg-698",
      detail: "Refinement receipt accepted the package metadata and selected next front.",
      event_id: "audit-698-readiness",
      occurred_at: "2026-05-27T05:18:00.000Z",
      receipt_id: "WGCF-READY-698",
      title: "Refinement readiness accepted",
      tone: "ok",
    },
    {
      actor: "advisor",
      category: "action",
      delivery_package_id: "pkg-698",
      detail: "Advisor suggested User story #714 as the next executable front.",
      event_id: "audit-698-suggestion",
      occurred_at: "2026-05-27T05:22:00.000Z",
      receipt_id: null,
      title: "Next-front suggestion prepared",
      tone: "info",
    },
    {
      actor: "system",
      category: "projection",
      delivery_package_id: "pkg-900",
      detail: "Large tree package is intentionally stale to exercise projection UI state.",
      event_id: "audit-900-stale",
      occurred_at: "2026-05-27T05:30:00.000Z",
      receipt_id: null,
      title: "Projection stale scenario",
      tone: "stale",
    },
  ],
};
