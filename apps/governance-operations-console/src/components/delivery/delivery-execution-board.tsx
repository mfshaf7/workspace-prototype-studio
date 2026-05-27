"use client";

import { useMemo, useState } from "react";

import type {
  DeliveryArtNode,
  DeliveryPackagePosture,
  DeliveryPackageSummary,
  DeliveryReadModel,
} from "@/data/delivery-read-model";
import {
  deliveryPostureOrder,
  getAvailableActions,
  getChildCounts,
  getDeliveryBoardSummary,
  getDeliveryPackages,
  getPackageAuditEvents,
  getPackageById,
  getPackageDetailsById,
  getPackageTree,
} from "@/data/delivery-selectors";
import { deliveryPostureTerms } from "@/data/delivery-terms";

import {
  DeliveryActionButton,
  DeliveryPanel,
  DeliverySectionHeader,
  DeliveryStatusPill,
  DeliveryTreeNodeCard,
} from "./delivery-patterns";
import styles from "./delivery-execution-board.module.css";

type ExecutionBoardView = "art-map" | "art-tree" | "control-board";

type ClassValue = string | false | null | undefined;

function cx(...classes: ClassValue[]) {
  return classes.filter(Boolean).join(" ");
}

export function DeliveryExecutionBoard({
  model,
}: {
  model: DeliveryReadModel;
}) {
  const [activeView, setActiveView] = useState<ExecutionBoardView>("control-board");
  const [selectedPackageId, setSelectedPackageId] = useState(
    model.selected_delivery_package_id,
  );

  const packages = useMemo(() => getDeliveryPackages(model), [model]);
  const boardSummary = getDeliveryBoardSummary(model);
  const selectedPackage =
    getPackageById(selectedPackageId, model) ?? packages[0] ?? null;
  const selectedDetails = selectedPackage
    ? getPackageDetailsById(selectedPackage.delivery_package_id, model)
    : null;
  const selectedTree = selectedPackage
    ? getPackageTree(selectedPackage.delivery_package_id, model)
    : null;
  const selectedActions = selectedPackage
    ? getAvailableActions(selectedPackage.delivery_package_id, model)
    : [];
  const selectedAuditEvents = selectedPackage
    ? getPackageAuditEvents(selectedPackage.delivery_package_id, model)
    : [];

  return (
    <div className={styles.board}>
      <DeliveryPanel className={styles.mainPane} tone="info">
        <div className={styles.toolbar}>
          <DeliverySectionHeader
            kicker="Execution Board"
            title="Delivery Package Control"
            description="Select a package, inspect wider ART context, then open only the action draft or review modal required for the selected move."
          />
          <div
            aria-label="Execution board views"
            className={styles.tabs}
            role="tablist"
          >
            {[
              ["control-board", "Control Board"],
              ["art-map", "ART Map"],
              ["art-tree", "ART Tree"],
            ].map(([view, label]) => (
              <button
                aria-selected={activeView === view}
                className={cx(
                  styles.tab,
                  activeView === view && styles.tabActive,
                )}
                key={view}
                onClick={() => setActiveView(view as ExecutionBoardView)}
                role="tab"
                type="button"
              >
                {label}
              </button>
            ))}
          </div>
        </div>
      </DeliveryPanel>

      <div className={styles.summaryGrid} aria-label="Delivery board summary">
        <SummaryCard
          label="Packages"
          tone="info"
          value={String(boardSummary.total_packages)}
        />
        <SummaryCard
          label="Blocked"
          tone="danger"
          value={String(boardSummary.blocked_count)}
        />
        <SummaryCard
          label="Closeout"
          tone="warn"
          value={String(boardSummary.closeout_pending_count)}
        />
        <SummaryCard
          label="Stale"
          tone={boardSummary.stale_count > 0 ? "stale" : "ok"}
          value={String(boardSummary.stale_count)}
        />
      </div>

      <div className={styles.workspace}>
        <DeliveryPanel className={styles.mainPane} tone="info">
          {activeView === "control-board" ? (
            <ControlBoardView
              packages={packages}
              selectedPackageId={selectedPackage?.delivery_package_id ?? null}
              onSelectPackage={setSelectedPackageId}
            />
          ) : null}
          {activeView === "art-map" ? (
            <ArtMapView
              model={model}
              selectedPackageId={selectedPackage?.delivery_package_id ?? null}
              onSelectPackage={setSelectedPackageId}
            />
          ) : null}
          {activeView === "art-tree" ? (
            <ArtTreeView tree={selectedTree} />
          ) : null}
        </DeliveryPanel>

        <DeliveryPanel
          className={styles.selectedPane}
          selected={Boolean(selectedPackage)}
          tone={selectedPackage?.tone ?? "info"}
        >
          {selectedPackage ? (
            <SelectedPackagePanel
              auditEvents={selectedAuditEvents}
              details={selectedDetails}
              packageSummary={selectedPackage}
              packageTree={selectedTree}
              selectedActions={selectedActions}
            />
          ) : (
            <div className={styles.emptyState}>
              Select a Delivery Package to inspect available actions, current
              front, audit events, and tree context.
            </div>
          )}
        </DeliveryPanel>
      </div>
    </div>
  );
}

function SummaryCard({
  label,
  tone,
  value,
}: {
  label: string;
  tone: DeliveryPackageSummary["tone"];
  value: string;
}) {
  return (
    <DeliveryPanel className={styles.summaryCard} tone={tone}>
      <DeliveryStatusPill tone={tone}>{label}</DeliveryStatusPill>
      <p className={styles.summaryValue}>{value}</p>
      <p className={styles.summaryLabel}>Projected package count</p>
    </DeliveryPanel>
  );
}

function ControlBoardView({
  onSelectPackage,
  packages,
  selectedPackageId,
}: {
  onSelectPackage: (deliveryPackageId: string) => void;
  packages: DeliveryPackageSummary[];
  selectedPackageId: string | null;
}) {
  const groupedPackages = deliveryPostureOrder.map((posture) => ({
    posture,
    packages: packages.filter(
      (deliveryPackage) => deliveryPackage.package_posture === posture,
    ),
  }));

  return (
    <div className={styles.controlColumns}>
      {groupedPackages.map(({ packages: posturePackages, posture }) => (
        <section className={styles.postureColumn} key={posture}>
          <div className={styles.postureHeader}>
            <p className={styles.postureTitle}>
              {deliveryPostureTerms[posture].label}
            </p>
            <DeliveryStatusPill tone={postureTone(posture)}>
              {posturePackages.length}
            </DeliveryStatusPill>
          </div>
          {posturePackages.length > 0 ? (
            <div className={styles.packageStack}>
              {posturePackages.map((deliveryPackage) => (
                <PackageCard
                  key={deliveryPackage.delivery_package_id}
                  onSelectPackage={onSelectPackage}
                  packageSummary={deliveryPackage}
                  selected={
                    deliveryPackage.delivery_package_id === selectedPackageId
                  }
                />
              ))}
            </div>
          ) : (
            <div className={styles.emptyState}>
              No package currently projects to this posture.
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

function PackageCard({
  onSelectPackage,
  packageSummary,
  selected,
}: {
  onSelectPackage: (deliveryPackageId: string) => void;
  packageSummary: DeliveryPackageSummary;
  selected: boolean;
}) {
  return (
    <button
      className={cx(styles.packageCard, selected && styles.packageCardSelected)}
      onClick={() => onSelectPackage(packageSummary.delivery_package_id)}
      type="button"
    >
      <p className={styles.packageKicker}>{packageSummary.source_ref}</p>
      <p className={styles.packageTitle}>{packageSummary.display_name}</p>
      <p className={styles.packageSummary}>{packageSummary.summary}</p>
      <div className={styles.packageMeta}>
        <DeliveryStatusPill tone={packageSummary.tone}>
          {packageSummary.package_posture}
        </DeliveryStatusPill>
        <DeliveryStatusPill tone="muted">
          {packageSummary.open_child_count} open
        </DeliveryStatusPill>
      </div>
    </button>
  );
}

function ArtMapView({
  model,
  onSelectPackage,
  selectedPackageId,
}: {
  model: DeliveryReadModel;
  onSelectPackage: (deliveryPackageId: string) => void;
  selectedPackageId: string | null;
}) {
  return (
    <div className={styles.mapGrid}>
      {model.art_map.lanes.map((lane) => {
        const laneSelected = lane.packages.some(
          (deliveryPackage) =>
            deliveryPackage.delivery_package_id === selectedPackageId,
        );

        return (
          <section
            className={cx(styles.mapLane, laneSelected && styles.mapLaneSelected)}
            key={lane.id}
          >
            <p className={styles.mapLaneTitle}>{lane.label}</p>
            <p className={styles.mapLaneSummary}>{lane.summary}</p>
            <div className={styles.packageStack}>
              {lane.packages.map((deliveryPackage) => (
                <button
                  className={cx(
                    styles.packageCard,
                    deliveryPackage.delivery_package_id === selectedPackageId &&
                      styles.packageCardSelected,
                  )}
                  key={deliveryPackage.delivery_package_id}
                  onClick={() =>
                    onSelectPackage(deliveryPackage.delivery_package_id)
                  }
                  type="button"
                >
                  <p className={styles.packageKicker}>
                    Epic #{deliveryPackage.legacy_epic_id}
                  </p>
                  <p className={styles.packageTitle}>
                    {deliveryPackage.display_name}
                  </p>
                  <div className={styles.packageMeta}>
                    <DeliveryStatusPill tone={deliveryPackage.tone}>
                      {deliveryPackage.package_posture}
                    </DeliveryStatusPill>
                  </div>
                </button>
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

function ArtTreeView({ tree }: { tree: DeliveryArtNode | null }) {
  if (!tree) {
    return (
      <div className={styles.emptyState}>
        No projected ART tree is available for this package yet.
      </div>
    );
  }

  return (
    <div className={styles.treeLayout}>
      <TreeNode node={tree} selected />
    </div>
  );
}

function TreeNode({
  node,
  selected = false,
}: {
  node: DeliveryArtNode;
  selected?: boolean;
}) {
  const childCounts = getChildCounts(node);

  return (
    <div className={styles.treeLayout}>
      <DeliveryTreeNodeCard
        childrenCount={childCounts.total_child_count}
        description={node.description}
        selected={selected}
        title={node.title}
        type={node.component_type}
      />
      {node.children.length > 0 ? (
        <div className={styles.treeChildren}>
          {node.children.map((child) => (
            <TreeNode key={child.id} node={child} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function SelectedPackagePanel({
  auditEvents,
  details,
  packageSummary,
  packageTree,
  selectedActions,
}: {
  auditEvents: ReturnType<typeof getPackageAuditEvents>;
  details: ReturnType<typeof getPackageDetailsById>;
  packageSummary: DeliveryPackageSummary;
  packageTree: DeliveryArtNode | null;
  selectedActions: ReturnType<typeof getAvailableActions>;
}) {
  const childCounts = packageTree ? getChildCounts(packageTree) : null;

  return (
    <>
      <div className={styles.selectedHeader}>
        <div>
          <p className={styles.packageKicker}>Delivery Package</p>
          <h3 className={styles.selectedTitle}>{packageSummary.display_name}</h3>
          <p className={styles.selectedSource}>{packageSummary.source_ref}</p>
        </div>
        <DeliveryStatusPill tone={packageSummary.tone}>
          {packageSummary.package_posture}
        </DeliveryStatusPill>
      </div>

      <section className={styles.selectedSection}>
        <p className={styles.selectedSectionTitle}>Package Context</p>
        <div className={styles.factList}>
          <FactRow label="Target PI" value={packageSummary.target_pi ?? "Not committed"} />
          <FactRow label="Owner Repo" value={details?.owner_repo ?? "Projected owner unavailable"} />
          <FactRow
            label="Open Children"
            value={String(childCounts?.open_child_count ?? packageSummary.open_child_count)}
          />
          <FactRow
            label="Advisor"
            value={details?.advisor_summary ?? "No advisor packet projected for this package."}
          />
        </div>
      </section>

      <section className={styles.selectedSection}>
        <p className={styles.selectedSectionTitle}>Package Actions</p>
        <div className={styles.actionList}>
          {selectedActions.map((action) => (
            <div className={styles.actionRow} key={action.action_type}>
              <div className={styles.selectedHeader}>
                <p className={styles.rowTitle}>{action.label}</p>
                <DeliveryStatusPill tone={action.tone}>
                  {action.enabled ? "Available" : "Locked"}
                </DeliveryStatusPill>
              </div>
              <p className={styles.rowDetail}>{action.reason}</p>
              {action.enabled ? (
                <DeliveryActionButton
                  aria-label={`${action.label} for ${packageSummary.display_name}`}
                  variant={action.tone === "danger" ? "danger" : "primary"}
                >
                  {action.label}
                </DeliveryActionButton>
              ) : null}
            </div>
          ))}
        </div>
      </section>

      <section className={styles.selectedSection}>
        <p className={styles.selectedSectionTitle}>Audit Trail</p>
        {auditEvents.length > 0 ? (
          <div className={styles.auditList}>
            {auditEvents.map((event) => (
              <div className={styles.auditRow} key={event.event_id}>
                <div className={styles.selectedHeader}>
                  <p className={styles.rowTitle}>{event.title}</p>
                  <DeliveryStatusPill tone={event.tone}>
                    {event.category}
                  </DeliveryStatusPill>
                </div>
                <p className={styles.rowDetail}>{event.detail}</p>
              </div>
            ))}
          </div>
        ) : (
          <div className={styles.emptyState}>
            No package-scoped audit events are projected for this package yet.
          </div>
        )}
      </section>
    </>
  );
}

function FactRow({ label, value }: { label: string; value: string }) {
  return (
    <div className={styles.factRow}>
      <p className={styles.rowTitle}>{label}</p>
      <p className={styles.rowDetail}>{value}</p>
    </div>
  );
}

function postureTone(posture: DeliveryPackagePosture): DeliveryPackageSummary["tone"] {
  switch (posture) {
    case "Blocked":
      return "danger";
    case "Closeout Pending":
    case "Deferred":
      return "warn";
    case "Done":
    case "In Progress":
      return "ok";
    case "Retired":
      return "muted";
    case "Ready":
    default:
      return "info";
  }
}
