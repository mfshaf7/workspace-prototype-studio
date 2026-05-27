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
  DeliveryAdvisorPanel,
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

type DeliveryStageWorkflowRoute =
  | "blocker"
  | "deferral"
  | "intake"
  | "refinement"
  | "work-design";

type DeliveryStageWorkflowState = {
  deliveryPackage: DeliveryPackageSummary;
  route: DeliveryStageWorkflowRoute;
  surface: DeliverySurfaceConfig;
};

type DeliveryStageWorkflowStep = "draft" | "receipt" | "review";

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
  const [stageWorkflow, setStageWorkflow] =
    useState<DeliveryStageWorkflowState | null>(null);
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
    packageRegisterRow(deliveryPackage, index, setSelectedPackageId),
  );
  const workflowAction = selectedPackage
    ? stageWorkflowAction(surface, selectedPackage)
    : null;

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
                  {workflowAction ? (
                    <div className={styles.contextActionCard}>
                      <DeliverySectionHeader
                        actions={
                          <DeliveryStatusPill tone={workflowAction.tone}>
                            {workflowAction.statusLabel}
                          </DeliveryStatusPill>
                        }
                        kicker="Required Action"
                        title={workflowAction.title}
                        description={workflowAction.description}
                      />
                      <div className={styles.contextActionFooter}>
                        <DeliveryActionButton
                          onClick={() =>
                            setStageWorkflow({
                              deliveryPackage: selectedPackage,
                              route: workflowAction.route,
                              surface,
                            })
                          }
                          tone={workflowAction.tone}
                          variant={
                            workflowAction.tone === "danger"
                              ? "danger"
                              : "primary"
                          }
                        >
                          {workflowAction.buttonLabel}
                        </DeliveryActionButton>
                      </div>
                    </div>
                  ) : null}
                </div>
              ) : null}
            </DeliveryPanel>
          </div>
        </DeliveryModalShell>
      ) : null}

      {stageWorkflow ? (
        <DeliveryStageWorkflowModal
          model={model}
          onClose={() => setStageWorkflow(null)}
          workflow={stageWorkflow}
        />
      ) : null}
    </>
  );
}

function DeliveryStageWorkflowModal({
  model,
  onClose,
  workflow,
}: {
  model: DeliveryReadModel;
  onClose: () => void;
  workflow: DeliveryStageWorkflowState;
}) {
  const [step, setStep] = useState<DeliveryStageWorkflowStep>("draft");
  const [operatorNote, setOperatorNote] = useState(
    initialOperatorNote(workflow),
  );
  const copy = stageWorkflowCopy(workflow);
  const gates = stageWorkflowGates(workflow, operatorNote);
  const openGateCount = gates.filter((gate) => gate.tone === "warn").length;
  const readyForReview = openGateCount === 0;
  const receiptReady = step === "receipt";

  return (
    <DeliveryModalShell
      description={copy.description}
      footer={
        <>
          <DeliveryActionButton onClick={onClose} variant="secondary">
            Back To Register
          </DeliveryActionButton>
          {step === "draft" ? (
            <DeliveryActionButton
              disabled={!readyForReview}
              onClick={() => setStep("review")}
              tone={copy.tone}
            >
              Review Apply
            </DeliveryActionButton>
          ) : step === "review" ? (
            <>
              <DeliveryActionButton
                onClick={() => setStep("draft")}
                variant="secondary"
              >
                Back To Draft
              </DeliveryActionButton>
              <DeliveryActionButton
                onClick={() => setStep("receipt")}
                tone={copy.tone}
              >
                Apply
              </DeliveryActionButton>
            </>
          ) : (
            <DeliveryActionButton onClick={onClose} tone="ok">
              Done
            </DeliveryActionButton>
          )}
        </>
      }
      kicker={copy.kicker}
      onClose={onClose}
      size="wide"
      title={copy.title}
    >
      <div className={styles.workflowModalGrid}>
        <div className={styles.workflowMainColumn}>
          <DeliveryPanel
            className={styles.workflowProgressPanel}
            selected
            tone={copy.tone}
          >
            <DeliverySectionHeader
              actions={
                <DeliveryStatusPill tone={receiptReady ? "ok" : copy.tone}>
                  {receiptReady ? "applied" : copy.statusLabel}
                </DeliveryStatusPill>
              }
              kicker="Workflow Progress"
              title={copy.progressTitle}
              description={copy.progressDescription}
            />
            <div className={styles.workflowStepGrid}>
              {copy.steps.map((item) => {
                const active = item.id === step;
                const complete =
                  step === "receipt" ||
                  (step === "review" && item.id === "draft");
                return (
                  <button
                    aria-pressed={active}
                    className={`${styles.workflowStepCard} ${
                      active ? styles.workflowStepCardActive : ""
                    }`}
                    key={item.id}
                    onClick={() => {
                      if (item.id === "draft" || readyForReview) {
                        setStep(item.id);
                      }
                    }}
                    type="button"
                  >
                    <span>{item.label}</span>
                    <DeliveryStatusPill tone={complete ? "ok" : active ? copy.tone : "muted"}>
                      {complete ? "ready" : active ? "current" : "next"}
                    </DeliveryStatusPill>
                  </button>
                );
              })}
            </div>
          </DeliveryPanel>

          <DeliveryPanel className={styles.workflowDraftPanel} tone={copy.tone}>
            <DeliverySectionHeader
              actions={
                <DeliveryStatusPill tone={workflow.deliveryPackage.tone}>
                  {workflow.deliveryPackage.package_posture}
                </DeliveryStatusPill>
              }
              kicker={copy.draftKicker}
              title={workflow.deliveryPackage.display_name}
              description={copy.draftDescription}
            />

            {step === "receipt" ? (
              <div className={styles.workflowReceiptLog}>
                {copy.receiptLines.map((line) => (
                  <div className={styles.workflowReceiptLine} key={line}>
                    <span>[ok]</span>
                    <p>{line}</p>
                  </div>
                ))}
              </div>
            ) : step === "review" ? (
              <div className={styles.workflowReviewList}>
                {stageWorkflowReviewRows(workflow, operatorNote).map((row) => (
                  <FactRow key={row[0]} label={row[0]} value={row[1]} />
                ))}
              </div>
            ) : (
              <div className={styles.workflowDraftBody}>
                <div className={styles.workflowDraftFacts}>
                  <FactRow label="Source" value={workflow.deliveryPackage.source_ref} />
                  <FactRow
                    label="Target PI"
                    value={workflow.deliveryPackage.target_pi ?? "Not committed"}
                  />
                  <FactRow
                    label="Open Children"
                    value={String(workflow.deliveryPackage.open_child_count)}
                  />
                  <FactRow
                    label="Apply Route"
                    value={copy.applyRoute}
                  />
                </div>
                <label className={styles.workflowNoteField}>
                  <span>Operator Note</span>
                  <textarea
                    onChange={(event) => setOperatorNote(event.target.value)}
                    placeholder={copy.notePlaceholder}
                    value={operatorNote}
                  />
                </label>
              </div>
            )}
          </DeliveryPanel>
        </div>

        <div className={styles.workflowSideColumn}>
          <DeliveryPanel className={styles.workflowGatePanel} tone={openGateCount ? "warn" : "ok"}>
            <DeliverySectionHeader
              actions={
                <DeliveryStatusPill tone={openGateCount ? "warn" : "ok"}>
                  {openGateCount ? `${openGateCount} open` : "ready"}
                </DeliveryStatusPill>
              }
              kicker="Readiness Gates"
              title={openGateCount ? "Operator Input Required" : "Ready For Apply Review"}
              description={copy.gateDescription}
            />
            <div className={styles.workflowGateList}>
              {gates.map((gate) => (
                <div className={styles.workflowGateRow} key={gate.label}>
                  <div>
                    <p>{gate.label}</p>
                    <span>{gate.detail}</span>
                  </div>
                  <DeliveryStatusPill tone={gate.tone}>
                    {gate.status}
                  </DeliveryStatusPill>
                </div>
              ))}
            </div>
          </DeliveryPanel>

          <DeliveryAdvisorPanel
            profileLabel={copy.advisorProfile}
            statusLabel="online"
            transcript={[
              {
                id: "advisor-1",
                role: "advisor",
                text: copy.advisorText,
              },
              {
                id: "operator-1",
                role: "operator",
                text: operatorNote.trim()
                  ? operatorNote.trim()
                  : "Operator note is empty.",
              },
            ]}
          />
        </div>
      </div>
    </DeliveryModalShell>
  );
}

function packageRegisterRow(
  deliveryPackage: DeliveryPackageSummary,
  index: number,
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

function stageWorkflowAction(
  surface: DeliverySurfaceConfig,
  deliveryPackage: DeliveryPackageSummary,
): {
  buttonLabel: string;
  description: string;
  route: DeliveryStageWorkflowRoute;
  statusLabel: string;
  title: string;
  tone: DeliveryTone;
} {
  if (deliveryPackage.package_posture === "Blocked") {
    return {
      buttonLabel: "Open Blocker",
      description:
        "Route this selected package through the blocker workflow before normal stage work continues.",
      route: "blocker",
      statusLabel: "blocked",
      title: "Resolve Or Disposition Blocker",
      tone: "danger",
    };
  }

  if (deliveryPackage.package_posture === "Deferred") {
    return {
      buttonLabel: "Review Deferral",
      description:
        "Inspect the parked reason, review point, and resume decision before changing the package posture.",
      route: "deferral",
      statusLabel: "deferred",
      title: "Review Deferred Work",
      tone: "muted",
    };
  }

  if (surface.id === "intake") {
    return {
      buttonLabel: "Open Intake",
      description:
        "Consume the accepted proposal into the Delivery shell and produce an apply receipt.",
      route: "intake",
      statusLabel: "ready",
      title: "Run Intake Workflow",
      tone: "warn",
    };
  }

  if (surface.id === "work-design") {
    return {
      buttonLabel: "Open Work Design",
      description:
        "Open the AI/operator work design flow to shape the package tree before refinement.",
      route: "work-design",
      statusLabel: "ready",
      title: "Run Work Design Workflow",
      tone: "info",
    };
  }

  return {
    buttonLabel: "Open Refinement",
    description:
      "Complete whole-package metadata and review the apply command before the package can enter execution control.",
    route: "refinement",
    statusLabel: "ready",
    title: "Run Refinement Workflow",
    tone: "warn",
  };
}

function initialOperatorNote(workflow: DeliveryStageWorkflowState) {
  switch (workflow.route) {
    case "blocker":
      return "Blocker needs operator disposition before this package can continue.";
    case "deferral":
      return "Deferred package should stay parked until the review point is reached.";
    case "intake":
      return "Accepted source is ready for Delivery shell intake.";
    case "work-design":
      return "Shape the Epic, Feature, User story, and optional Risk tree before refinement.";
    case "refinement":
      return "Complete the package metadata contract before execution board entry.";
  }
}

function stageWorkflowCopy(workflow: DeliveryStageWorkflowState): {
  advisorProfile: string;
  advisorText: string;
  applyRoute: string;
  description: string;
  draftDescription: string;
  draftKicker: string;
  gateDescription: string;
  kicker: string;
  notePlaceholder: string;
  progressDescription: string;
  progressTitle: string;
  receiptLines: string[];
  statusLabel: string;
  steps: Array<{ id: DeliveryStageWorkflowStep; label: string }>;
  title: string;
  tone: DeliveryTone;
} {
  const baseSteps: Array<{ id: DeliveryStageWorkflowStep; label: string }> = [
    { id: "draft", label: "Draft" },
    { id: "review", label: "Review" },
    { id: "receipt", label: "Receipt" },
  ];
  const packageName = workflow.deliveryPackage.display_name;

  switch (workflow.route) {
    case "blocker":
      return {
        advisorProfile: "Delivery Blocker Advisor",
        advisorText:
          "I will preserve the blocker signal, ask for an operator disposition, and avoid moving this package until the disposition is explicit.",
        applyRoute: "oos://delivery/blocker",
        description:
          "Record the blocker disposition, owner, and review point before the package can return to its normal stage workflow.",
        draftDescription:
          "Use the draft to capture the blocker decision that the apply review will send through OOS.",
        draftKicker: "Blocker Draft",
        gateDescription:
          "A blocker workflow must include a reason and a visible next review point.",
        kicker: "Blocker Workflow",
        notePlaceholder:
          "State the blocker, owner, disposition, and review point.",
        progressDescription:
          "Draft, review, apply, and receipt stay in one guarded blocker flow.",
        progressTitle: "Blocker Disposition",
        receiptLines: [
          "Console submitted blocker disposition to OOS.",
          "WGCF readiness gate kept the blocker visible in the receipt.",
          "OpenProject adapter accepted the blocker update for preview.",
        ],
        statusLabel: "blocked",
        steps: baseSteps,
        title: packageName,
        tone: "danger",
      };
    case "deferral":
      return {
        advisorProfile: "Delivery Deferral Advisor",
        advisorText:
          "I will keep the work parked unless the operator records a resume path and review reason.",
        applyRoute: "oos://delivery/defer",
        description:
          "Review the parked state and decide whether the package remains deferred or should return to active workflow.",
        draftDescription:
          "Use the draft to record the deferral reason and review checkpoint.",
        draftKicker: "Deferral Draft",
        gateDescription:
          "Deferred work needs an operator note so the parked state is not ambiguous.",
        kicker: "Deferral Review",
        notePlaceholder:
          "State why this remains deferred, or what must change before it resumes.",
        progressDescription:
          "Draft, review, apply, and receipt stay in one guarded deferral flow.",
        progressTitle: "Deferral Decision",
        receiptLines: [
          "Console submitted deferral review to OOS.",
          "WGCF receipt preserved the parked rationale.",
          "OpenProject adapter accepted the defer update for preview.",
        ],
        statusLabel: "deferred",
        steps: baseSteps,
        title: packageName,
        tone: "muted",
      };
    case "intake":
      return {
        advisorProfile: "Delivery Intake Advisor",
        advisorText:
          "I will check the accepted source, preserve the proposal reference, and prepare the Delivery shell intake apply.",
        applyRoute: "oos://delivery/intake",
        description:
          "Consume the accepted source into an ART-backed Delivery Package shell through the guarded apply path.",
        draftDescription:
          "Use the draft to confirm source binding, package shell, and handoff target.",
        draftKicker: "Intake Draft",
        gateDescription:
          "Intake needs source binding, shell identity, and an operator note before apply review.",
        kicker: "Intake Workflow",
        notePlaceholder:
          "Confirm source proposal, Delivery shell, owner boundary, and next handoff.",
        progressDescription:
          "Draft, review, apply, and receipt stay in one guarded intake flow.",
        progressTitle: "Delivery Shell Intake",
        receiptLines: [
          "Console submitted intake apply request to OOS.",
          "WGCF readiness gate accepted the source and shell binding.",
          "OpenProject adapter accepted the Delivery shell update for preview.",
        ],
        statusLabel: "ready",
        steps: baseSteps,
        title: packageName,
        tone: "warn",
      };
    case "work-design":
      return {
        advisorProfile: "Work Design Advisor",
        advisorText:
          "I will keep planning inside the draft session, help shape the tree, and avoid setting execution-only metadata here.",
        applyRoute: "oos://delivery/work-design",
        description:
          "Open the AI/operator design flow that shapes the package tree before refinement.",
        draftDescription:
          "Use the draft to confirm tree shape, child groups, support branches, and handoff readiness.",
        draftKicker: "Work Design Draft",
        gateDescription:
          "Work Design needs tree shape, child grouping, and handoff note before apply review.",
        kicker: "Work Design Workflow",
        notePlaceholder:
          "Summarize the tree shape, missing children, support branches, and handoff to refinement.",
        progressDescription:
          "Draft, review, apply, and receipt stay in one guarded work design flow.",
        progressTitle: "Package Tree Design",
        receiptLines: [
          "Console submitted work design result to OOS.",
          "WGCF validation preserved the designed tree reference.",
          "OpenProject adapter accepted the draft handoff update for preview.",
        ],
        statusLabel: "ready",
        steps: baseSteps,
        title: packageName,
        tone: "info",
      };
    case "refinement":
      return {
        advisorProfile: "Refinement Advisor",
        advisorText:
          "I will inspect whole-package metadata, highlight missing contract fields, and keep the operator as the apply authority.",
        applyRoute: "oos://delivery/refinement",
        description:
          "Complete whole-package metadata so OOS/OpenProject can accept clean execution-ready state.",
        draftDescription:
          "Use the draft to confirm Epic contract, child metadata, readiness gates, and apply intent.",
        draftKicker: "Refinement Draft",
        gateDescription:
          "Refinement needs whole-package metadata, child work classification, and operator note before apply review.",
        kicker: "Refinement Workflow",
        notePlaceholder:
          "Summarize metadata gaps fixed, remaining deferrals, child work classification, and apply intent.",
        progressDescription:
          "Draft, review, apply, and receipt stay in one guarded refinement flow.",
        progressTitle: "Execution-Ready Refinement",
        receiptLines: [
          "Console submitted refinement apply request to OOS.",
          "WGCF readiness gate validated metadata completeness.",
          "OpenProject adapter accepted the refinement update for preview.",
        ],
        statusLabel: "ready",
        steps: baseSteps,
        title: packageName,
        tone: "warn",
      };
  }
}

function stageWorkflowGates(
  workflow: DeliveryStageWorkflowState,
  operatorNote: string,
): Array<{
  detail: string;
  label: string;
  status: string;
  tone: DeliveryTone;
}> {
  const hasNote = operatorNote.trim().length > 12;
  const sourceReady = Boolean(workflow.deliveryPackage.source_ref);
  const targetReady =
    workflow.route === "intake" ||
    workflow.route === "deferral" ||
    workflow.route === "blocker" ||
    Boolean(workflow.deliveryPackage.target_pi);

  return [
    {
      detail: sourceReady
        ? workflow.deliveryPackage.source_ref
        : "Source binding is missing.",
      label: "Source Binding",
      status: sourceReady ? "ready" : "open",
      tone: sourceReady ? "ok" : "warn",
    },
    {
      detail: targetReady
        ? workflow.deliveryPackage.target_pi ?? "Stage does not require Target PI."
        : "Target PI must be set before this apply route.",
      label: "Stage Target",
      status: targetReady ? "ready" : "open",
      tone: targetReady ? "ok" : "warn",
    },
    {
      detail: hasNote
        ? "Operator rationale is present."
        : "Add a concise operator rationale before apply review.",
      label: "Operator Rationale",
      status: hasNote ? "ready" : "open",
      tone: hasNote ? "ok" : "warn",
    },
  ];
}

function stageWorkflowReviewRows(
  workflow: DeliveryStageWorkflowState,
  operatorNote: string,
): Array<[string, string]> {
  const copy = stageWorkflowCopy(workflow);
  return [
    ["Package", workflow.deliveryPackage.display_name],
    ["Source", workflow.deliveryPackage.source_ref],
    ["Stage", stageLabel(workflow.deliveryPackage.workflow_stage)],
    ["Action", copy.title],
    ["Apply Route", copy.applyRoute],
    ["Operator Note", operatorNote.trim() || "No operator note recorded"],
  ];
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
