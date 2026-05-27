"use client";

import { useMemo, useState } from "react";
import type { CSSProperties } from "react";

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
    description: "Control ready and active packages without flooding child work items into the desk.",
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

  const activeSurface =
    deliverySurfaces.find((surface) => surface.id === activeSurfaceId) ??
    deliverySurfaces[0];
  const executionCount = useMemo(
    () => getExecutionBoardPackages(model).length,
    [model],
  );

  return (
    <div
      className="operation-desk-content delivery-operation-content"
      data-operation-desk="delivery"
    >
      <div className="desk-overview delivery-operation-overview rounded-3xl p-5 md:p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="min-w-0">
            <p className="mono desk-overview-kicker text-xs font-black uppercase tracking-[0.22em]">
              Operations Desk
            </p>
            <h2 className="desk-overview-title mt-2 text-3xl font-semibold tracking-[-0.055em] md:text-4xl">
              Delivery
            </h2>
            <p className="desk-overview-description mt-3 max-w-3xl text-sm leading-6">
              Control ART intake, work design, refinement, and execution board
              inspection from one Delivery read model.
            </p>
          </div>
          <div className={styles.sourceStack}>
            <DeliveryStatusPill tone="info">{model.source_truth}</DeliveryStatusPill>
            <DeliveryStatusPill tone={projectionTone(model)}>
              {model.projection_state.status.replaceAll("_", " ")}
            </DeliveryStatusPill>
          </div>
        </div>

        <div className="desk-overview-count-grid prototype-count-grid proposal-count-grid mt-5 grid gap-2 md:grid-cols-3 xl:grid-cols-6">
          {deliveryOverviewStats(model, executionCount).map((count) => (
            <div
              className={statusCardClass(
                count.tone,
                "desk-overview-count-card proposal-count-card prototype-count-card rounded-2xl p-3",
              )}
              key={count.label}
            >
              <p className="mono text-[9px] font-black uppercase tracking-[0.18em]">
                {count.label}
              </p>
              <p className="mt-2 truncate text-2xl font-semibold tracking-[-0.04em]">
                {count.value}
              </p>
            </div>
          ))}
        </div>
      </div>

      <div
        className="desk-tab-strip delivery-tab-strip mt-5 rounded-[22px] p-1.5"
        role="tablist"
        aria-label="Delivery surfaces"
        style={{ "--desk-tab-count": deliverySurfaces.length } as CSSProperties}
      >
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
              className={`desk-tab-button ${deskTabToneClass(surface.tone)} ${
                isActive ? "desk-tab-button-active" : ""
              }`}
              key={surface.id}
              onClick={() => setActiveSurfaceId(surface.id)}
              role="tab"
              type="button"
            >
              <span>{surface.title}</span>
              <span>
                {count} {count === 1 ? "item" : "items"}
              </span>
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
    <section className="desk-workflow-panel desk-work-surface mt-4 rounded-3xl p-4 md:p-5">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
        <div>
          <p className="mono desk-work-surface-kicker text-[10px] font-black uppercase tracking-[0.2em]">
            Execution Board
          </p>
          <h3 className="desk-work-surface-title mt-2 text-2xl font-semibold tracking-[-0.045em]">
            Open the delivery control workspace.
          </h3>
          <p className="desk-work-surface-description mt-2 max-w-2xl text-sm leading-6">
            Inspect package posture, ART map, ART tree, and selected package
            actions in the wide board workspace.
          </p>
        </div>
      </div>

      <div className="portfolio-selected-flow delivery-execution-overview mt-4 rounded-3xl p-3">
        {[
          ["Packages", String(executionCount), "info"],
          ["Blocked", String(model.board_summary.blocked_count), "danger"],
          ["Closeout", String(model.board_summary.closeout_pending_count), "warn"],
          [
            "Projection",
            model.projection_state.status.replaceAll("_", " "),
            projectionTone(model),
          ],
        ].map(([label, value, tone]) => (
          <div
            className={statusCardClass(
              tone as DeliveryTone,
              "portfolio-selected-flow-step rounded-2xl p-3",
            )}
            key={label}
          >
            <p className="mono text-[8px] font-black uppercase tracking-[0.16em]">
              {label}
            </p>
            <p className="mt-2 text-xs font-semibold leading-5">{value}</p>
          </div>
        ))}
      </div>

      <div className="desk-entry-dock delivery-intake-draft-dock delivery-execution-entry-dock mt-8">
        <button
          className="delivery-execution-primary-action delivery-intake-primary-action intake-focus-draft-action desk-entry-card w-full rounded-[24px] p-5 text-left"
          type="button"
          title="Open Delivery execution board"
          onClick={onOpenBoard}
        >
          <div>
            <div>
              <p className="mono text-[11px] font-black uppercase tracking-[0.22em]">
                Board entry
              </p>
              <h3 className="intake-focus-draft-action-title mt-3 font-semibold tracking-[-0.06em]">
                Open Board
              </h3>
              <p className="mt-2 max-w-xl text-sm leading-6">
                Select packages, switch board view, inspect tree context, and
                open the required package action.
              </p>
            </div>
            <div className="mt-7 flex justify-end">
              <span className="intake-focus-draft-action-cue mono rounded-2xl px-4 py-3">
                View Board
              </span>
            </div>
          </div>
          <span className="intake-focus-draft-action-arrow mono" aria-hidden="true">
            &gt;
          </span>
        </button>
      </div>
    </section>
  );
}

function DeliveryStageSurface({
  model,
  surface,
}: {
  model: DeliveryReadModel;
  surface: DeliverySurfaceConfig;
}) {
  const [registerOpen, setRegisterOpen] = useState(false);
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);
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
    packageRegisterRow(deliveryPackage, index, surface, setSelectedPackageId),
  );

  return (
    <>
      <section className="desk-workflow-panel desk-work-surface mt-4 rounded-3xl p-4 md:p-5">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <p className="mono desk-work-surface-kicker text-[10px] font-black uppercase tracking-[0.2em]">
              {surface.title}
            </p>
            <h3 className="desk-work-surface-title mt-2 text-2xl font-semibold tracking-[-0.045em]">
              {stageHeadline(surface)}
            </h3>
            <p className="desk-work-surface-description mt-2 max-w-2xl text-sm leading-6">
              {surface.description}
            </p>
          </div>
        </div>

        <div className="portfolio-selected-flow delivery-stage-overview mt-4 rounded-3xl p-3">
          {stageOverviewRows(surface, packages, selectedPackage).map((item) => (
            <div
              className={statusCardClass(
                item.tone,
                "portfolio-selected-flow-step rounded-2xl p-3",
              )}
              key={item.label}
            >
              <p className="mono text-[8px] font-black uppercase tracking-[0.16em]">
                {item.label}
              </p>
              <p className="mt-2 text-xs font-semibold leading-5">{item.value}</p>
            </div>
          ))}
        </div>

        <div className="desk-entry-dock delivery-intake-draft-dock delivery-stage-entry-dock mt-8">
          <button
            className="delivery-stage-primary-action delivery-intake-primary-action intake-focus-draft-action desk-entry-card w-full rounded-[24px] p-5 text-left"
            type="button"
            title={`Open ${surface.title} register`}
            onClick={() => setRegisterOpen(true)}
          >
            <div>
              <div>
                <p className="mono text-[11px] font-black uppercase tracking-[0.22em]">
                  Register entry
                </p>
                <h3 className="intake-focus-draft-action-title mt-3 font-semibold tracking-[-0.06em]">
                  Open {surface.title}
                </h3>
                <p className="mt-2 max-w-xl text-sm leading-6">
                  {stageEntryCopy(surface)}
                </p>
              </div>
              <div className="mt-7 flex justify-end">
                <span className="intake-focus-draft-action-cue mono rounded-2xl px-4 py-3">
                  View Register
                </span>
              </div>
            </div>
            <span className="intake-focus-draft-action-arrow mono" aria-hidden="true">
              &gt;
            </span>
          </button>
        </div>
      </section>

      {registerOpen ? (
        <DeliveryModalShell
          description={surface.description}
          footer={
            <DeliveryActionButton onClick={() => setRegisterOpen(false)}>
              Close
            </DeliveryActionButton>
          }
          kicker={`${surface.title} Register`}
          onClose={() => setRegisterOpen(false)}
          size="wide"
          title={surface.title}
        >
          <div className={styles.stageRegisterLayout}>
            <DeliveryPanel className={styles.stageRegisterPanel} tone={surface.tone}>
              <div className={styles.registerHeader}>
                <DeliverySectionHeader
                  kicker={surface.title}
                  title={`${surface.title} Register`}
                  description="Select a row to inspect the projected package context."
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
        </DeliveryModalShell>
      ) : null}
    </>
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
    statusLabel: deliveryPackage.package_posture,
    statusTone: deliveryPackage.tone,
    title: deliveryPackage.display_name,
  };
}

function deskTabToneClass(tone: DeliveryTone) {
  return `desk-tab-summary-${tone}`;
}

function statusCardClass(tone: DeliveryTone, className = "") {
  return `status-card status-card-${tone} ${className}`.trim();
}

function deliveryOverviewStats(
  model: DeliveryReadModel,
  executionCount: number,
): Array<{ label: string; tone: DeliveryTone; value: string }> {
  return [
    {
      label: "Packages",
      tone: "info",
      value: String(model.packages.length),
    },
    {
      label: "Intake",
      tone: getDeliveryWorkflowStageCount("intake", model) > 0 ? "warn" : "muted",
      value: String(getDeliveryWorkflowStageCount("intake", model)),
    },
    {
      label: "Design",
      tone: getDeliveryWorkflowStageCount("work_design", model) > 0 ? "info" : "muted",
      value: String(getDeliveryWorkflowStageCount("work_design", model)),
    },
    {
      label: "Refinement",
      tone: getDeliveryWorkflowStageCount("refinement", model) > 0 ? "warn" : "muted",
      value: String(getDeliveryWorkflowStageCount("refinement", model)),
    },
    {
      label: "Execution",
      tone: executionCount > 0 ? "info" : "muted",
      value: String(executionCount),
    },
    {
      label: "Blocked",
      tone: model.board_summary.blocked_count > 0 ? "danger" : "ok",
      value: String(model.board_summary.blocked_count),
    },
  ];
}

function stageHeadline(surface: DeliverySurfaceConfig) {
  switch (surface.id) {
    case "intake":
      return "Open the delivery intake register.";
    case "work-design":
      return "Open the work design register.";
    case "refinement":
      return "Open the refinement register.";
    case "execution-board":
      return "Open the delivery control workspace.";
  }
}

function stageEntryCopy(surface: DeliverySurfaceConfig) {
  switch (surface.id) {
    case "intake":
      return "Search accepted proposal sources, inspect intake posture, and continue the handoff into Delivery.";
    case "work-design":
      return "Inspect packages that still need work design before they can move to refinement.";
    case "refinement":
      return "Inspect packages that need refinement before they can enter execution control.";
    case "execution-board":
      return "Select packages, switch board view, inspect tree context, and open the required package action.";
  }
}

function stageOverviewRows(
  surface: DeliverySurfaceConfig,
  packages: DeliveryPackageSummary[],
  selectedPackage: DeliveryPackageSummary | null,
): Array<{ label: string; tone: DeliveryTone; value: string }> {
  return [
    {
      label: "Register",
      tone: packages.length > 0 ? surface.tone : "muted",
      value: `${packages.length} ${packages.length === 1 ? "item" : "items"}`,
    },
    {
      label: "Selected",
      tone: selectedPackage?.tone ?? "muted",
      value: selectedPackage?.source_ref ?? "none",
    },
    {
      label: "Stage",
      tone: surface.tone,
      value: surface.title,
    },
    {
      label: "Projection",
      tone: packages.length > 0 ? "ok" : "muted",
      value: packages.length > 0 ? "ready" : "empty",
    },
  ];
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
      return "Execution Board after refinement apply is accepted.";
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
