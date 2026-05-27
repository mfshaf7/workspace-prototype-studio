"use client";

import { useMemo, useState } from "react";

import type {
  DeliveryPackageSummary,
  DeliveryReadModel,
  DeliveryTone,
  DeliveryWorkflowStage,
} from "@/data/delivery-read-model";
import {
  getDeliveryPackagesByWorkflowStage,
  getDeliveryReadModel,
  getDeliveryWorkflowStageCount,
  getExecutionBoardPackages,
} from "@/data/delivery-selectors";

import {
  DeliveryActionButton,
  DeliveryModalShell,
  DeliveryPanel,
  DeliveryRegisterTable,
  DeliverySectionHeader,
  DeliveryStatusPill,
  type DeliveryRegisterRow,
} from "./delivery-patterns";
import { DeliveryExecutionBoard } from "./delivery-execution-board";
import styles from "./delivery-operation-focus.module.css";

type DeliverySurfaceId =
  | "execution-board"
  | "intake"
  | "refinement"
  | "work-design";

type DeliverySurfaceConfig = {
  description: string;
  id: DeliverySurfaceId;
  kicker: string;
  stage?: DeliveryWorkflowStage;
  title: string;
  tone: DeliveryTone;
};

type DeliveryOperationPath = {
  label?: string;
};

const deliverySurfaces: DeliverySurfaceConfig[] = [
  {
    description: "Accepted proposals become ART-backed Delivery Package shells.",
    id: "intake",
    kicker: "01",
    stage: "intake",
    title: "Intake",
    tone: "warn",
  },
  {
    description: "AI and operator shape the Epic, Feature, User story, and Risk tree.",
    id: "work-design",
    kicker: "02",
    stage: "work_design",
    title: "Work Design",
    tone: "info",
  },
  {
    description: "Complete whole-package metadata before execution control.",
    id: "refinement",
    kicker: "03",
    stage: "refinement",
    title: "Refinement",
    tone: "warn",
  },
  {
    description: "Control ready and active packages without flooding child fronts into the desk.",
    id: "execution-board",
    kicker: "04",
    title: "Execution Board",
    tone: "info",
  },
];

export function DeliveryOperationFocus({
  path: _path,
}: {
  path?: DeliveryOperationPath;
}) {
  const model = getDeliveryReadModel();
  const [activeSurfaceId, setActiveSurfaceId] =
    useState<DeliverySurfaceId>("execution-board");
  const [executionBoardOpen, setExecutionBoardOpen] = useState(false);
  const [selectedStagePackageIds, setSelectedStagePackageIds] = useState<
    Partial<Record<DeliverySurfaceId, string>>
  >({});

  const activeSurface =
    deliverySurfaces.find((surface) => surface.id === activeSurfaceId) ??
    deliverySurfaces[0];
  const executionCount = useMemo(
    () => getExecutionBoardPackages(model).length,
    [model],
  );

  return (
    <div className={styles.shell}>
      <DeliveryPanel className={styles.hero} tone="warn">
        <div className={styles.heroTop}>
          <DeliverySectionHeader
            kicker="Delivery Operation Desk"
            title="Delivery System"
            description="Delivery now uses Intake, Work Design, Refinement, and Execution Board as separate operator jobs over one OOS-shaped read model."
          />
          <div className={styles.sourceStack}>
            <DeliveryStatusPill tone="info">{model.source_truth}</DeliveryStatusPill>
            <DeliveryStatusPill tone={projectionTone(model)}>
              {model.projection_state.status.replaceAll("_", " ")}
            </DeliveryStatusPill>
          </div>
        </div>
      </DeliveryPanel>

      <div className={styles.tabs} role="tablist" aria-label="Delivery surfaces">
        {deliverySurfaces.map((surface) => {
          const isActive = activeSurfaceId === surface.id;
          const count =
            surface.id === "execution-board"
              ? executionCount
              : surface.stage
                ? getDeliveryWorkflowStageCount(surface.stage, model)
                : 0;

          return (
            <button
              aria-selected={isActive}
              className={`${styles.tab} ${isActive ? styles.tabActive : ""}`}
              key={surface.id}
              onClick={() => setActiveSurfaceId(surface.id)}
              role="tab"
              type="button"
            >
              <p className={styles.tabKicker}>{surface.kicker}</p>
              <p className={styles.tabTitle}>{surface.title}</p>
              <p className={styles.tabMeta}>
                {count} {count === 1 ? "item" : "items"}
              </p>
            </button>
          );
        })}
      </div>

      {activeSurface.id === "execution-board" ? (
        <DeliveryBoardEntry
          executionCount={executionCount}
          model={model}
          onOpenBoard={() => setExecutionBoardOpen(true)}
        />
      ) : (
        <DeliveryStageSurface
          model={model}
          onSelectPackage={(deliveryPackageId) =>
            setSelectedStagePackageIds((current) => ({
              ...current,
              [activeSurface.id]: deliveryPackageId,
            }))
          }
          selectedPackageId={selectedStagePackageIds[activeSurface.id] ?? null}
          surface={activeSurface}
        />
      )}

      {executionBoardOpen ? (
        <DeliveryModalShell
          description="Select a package, change board view, inspect the selected package panel, then open only the action draft or apply review that matches the selected move."
          kicker="Execution Board"
          onClose={() => setExecutionBoardOpen(false)}
          size="wide"
          title="Delivery Package Control"
        >
          <DeliveryExecutionBoard model={model} showIntro={false} />
        </DeliveryModalShell>
      ) : null}
    </div>
  );
}

function DeliveryBoardEntry({
  executionCount,
  model,
  onOpenBoard,
}: {
  executionCount: number;
  model: DeliveryReadModel;
  onOpenBoard: () => void;
}) {
  return (
    <DeliveryPanel className={styles.boardEntry} selected tone="info">
      <div className={styles.boardEntryCopy}>
        <DeliverySectionHeader
          kicker="Execution Board"
          title="Open The Delivery Control Workspace"
          description="The board opens in a wide workspace so package posture, ART Map, ART Tree, and selected package actions do not fight for space inside the command rail."
        />
      </div>
      <div className={styles.boardEntryFacts}>
        <FactRow label="Board Packages" value={String(executionCount)} />
        <FactRow
          label="Projection"
          value={`${model.source_truth} / ${model.projection_state.status.replaceAll("_", " ")}`}
        />
        <FactRow label="Source Revision" value={model.projection_state.source_revision} />
      </div>
      <div className={styles.boardEntryAction}>
        <DeliveryActionButton onClick={onOpenBoard}>
          Open Execution Board
        </DeliveryActionButton>
      </div>
    </DeliveryPanel>
  );
}

function DeliveryStageSurface({
  model,
  onSelectPackage,
  selectedPackageId,
  surface,
}: {
  model: DeliveryReadModel;
  onSelectPackage: (deliveryPackageId: string) => void;
  selectedPackageId: string | null;
  surface: DeliverySurfaceConfig;
}) {
  const packages = surface.stage
    ? getDeliveryPackagesByWorkflowStage(surface.stage, model)
    : [];
  const selectedPackage =
    packages.find(
      (deliveryPackage) =>
        deliveryPackage.delivery_package_id === selectedPackageId,
    ) ??
    packages[0] ??
    null;
  const rows = packages.map((deliveryPackage, index) =>
    packageRegisterRow(deliveryPackage, index, surface, onSelectPackage),
  );

  return (
    <div className={styles.stageLayout}>
      <DeliveryPanel className={styles.stagePanel} tone={surface.tone}>
        <div className={styles.registerHeader}>
          <DeliverySectionHeader
            kicker={surface.title}
            title={`${surface.title} Register`}
            description={surface.description}
          />
          <DeliveryStatusPill tone={surface.tone}>
            {packages.length} {packages.length === 1 ? "item" : "items"}
          </DeliveryStatusPill>
        </div>
        {rows.length > 0 ? (
          <DeliveryRegisterTable rows={rows} />
        ) : (
          <div className={styles.emptyState}>
            No projected package currently belongs to this Delivery surface.
          </div>
        )}
      </DeliveryPanel>

      <DeliveryPanel
        className={styles.contextPanel}
        selected={Boolean(selectedPackage)}
        tone={selectedPackage?.tone ?? surface.tone}
      >
        <DeliverySectionHeader
          kicker="Selected Package"
          title={selectedPackage?.display_name ?? "No package selected"}
          description={
            selectedPackage
              ? selectedPackage.summary
              : "Select a register item to inspect its current workflow context."
          }
        />
        {selectedPackage ? (
          <div className={styles.contextCard}>
            <FactRow label="Source" value={selectedPackage.source_ref} />
            <FactRow
              label="Target PI"
              value={selectedPackage.target_pi ?? "Not committed"}
            />
            <FactRow
              label="Workflow Stage"
              value={stageLabel(selectedPackage.workflow_stage)}
            />
            <FactRow
              label="Next Surface"
              value={nextSurfaceHint(selectedPackage.workflow_stage)}
            />
          </div>
        ) : null}
      </DeliveryPanel>
    </div>
  );
}

function packageRegisterRow(
  deliveryPackage: DeliveryPackageSummary,
  index: number,
  surface: DeliverySurfaceConfig,
  onSelectPackage: (deliveryPackageId: string) => void,
): DeliveryRegisterRow {
  return {
    actionLabel: "Inspect",
    description: `${deliveryPackage.source_ref} - ${deliveryPackage.summary}`,
    id: deliveryPackage.delivery_package_id,
    index: String(index + 1).padStart(2, "0"),
    onAction: () => onSelectPackage(deliveryPackage.delivery_package_id),
    statusLabel: stageLabel(deliveryPackage.workflow_stage),
    statusTone: surface.tone,
    title: deliveryPackage.display_name,
  };
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.factRow}>
      <p className={styles.factLabel}>{label}</p>
      <p className={styles.factValue}>{value}</p>
    </div>
  );
}

function stageLabel(stage: DeliveryWorkflowStage) {
  switch (stage) {
    case "audit_only":
      return "Audit Only";
    case "execution":
      return "Execution";
    case "intake":
      return "Intake";
    case "refinement":
      return "Refinement";
    case "work_design":
      return "Work Design";
  }
}

function nextSurfaceHint(stage: DeliveryWorkflowStage) {
  switch (stage) {
    case "intake":
      return "Work Design after intake shell creation.";
    case "work_design":
      return "Refinement after the package tree draft is accepted.";
    case "refinement":
      return "Execution Board after metadata readiness apply is accepted.";
    case "execution":
      return "Package Actions from the Execution Board.";
    case "audit_only":
      return "Package-scoped Audit Trail only.";
  }
}

function projectionTone(model: DeliveryReadModel): DeliveryTone {
  switch (model.projection_state.status) {
    case "backend_unavailable":
    case "permission_denied":
    case "read_error":
      return "danger";
    case "projection_sync_required":
    case "stale":
      return "stale";
    case "fresh":
    default:
      return "ok";
  }
}
