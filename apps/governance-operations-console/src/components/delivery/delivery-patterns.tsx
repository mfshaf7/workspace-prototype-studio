"use client";

import { X } from "lucide-react";
import type {
  ButtonHTMLAttributes,
  ReactNode,
  TableHTMLAttributes,
} from "react";
import { createPortal } from "react-dom";

import type {
  DeliveryComponentType,
  DeliveryTone,
} from "@/data/delivery-read-model";

import styles from "./delivery-patterns.module.css";

type ClassValue = string | false | null | undefined;

function cx(...classes: ClassValue[]) {
  return classes.filter(Boolean).join(" ");
}

function toneClass(tone: DeliveryTone) {
  switch (tone) {
    case "danger":
      return styles.toneDanger;
    case "muted":
      return styles.toneMuted;
    case "ok":
      return styles.toneOk;
    case "stale":
      return styles.toneStale;
    case "warn":
      return styles.toneWarn;
    case "info":
    default:
      return styles.toneInfo;
  }
}

function panelToneClass(tone: DeliveryTone) {
  switch (tone) {
    case "danger":
      return styles.panelDanger;
    case "muted":
      return styles.panelMuted;
    case "ok":
      return styles.panelOk;
    case "stale":
      return styles.panelStale;
    case "warn":
      return styles.panelWarn;
    case "info":
    default:
      return styles.panelInfo;
  }
}

export function DeliveryStatusPill({
  children,
  className,
  tone = "info",
}: {
  children: ReactNode;
  className?: string;
  tone?: DeliveryTone;
}) {
  return (
    <span className={cx(styles.statusPill, toneClass(tone), className)}>
      {children}
    </span>
  );
}

export function DeliveryActionButton({
  children,
  className,
  tone = "info",
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  tone?: DeliveryTone;
  variant?: "danger" | "primary" | "secondary";
}) {
  return (
    <button
      className={cx(
        styles.actionButton,
        variant === "secondary" && styles.actionButtonSecondary,
        (variant === "danger" || tone === "danger") && styles.actionButtonDanger,
        className,
      )}
      type="button"
      {...props}
    >
      {children}
    </button>
  );
}

export function DeliveryPanel({
  children,
  className,
  selected = false,
  tone = "info",
}: {
  children: ReactNode;
  className?: string;
  selected?: boolean;
  tone?: DeliveryTone;
}) {
  return (
    <section
      className={cx(
        styles.panel,
        panelToneClass(tone),
        selected && styles.panelSelected,
        className,
      )}
    >
      {children}
    </section>
  );
}

export function DeliverySectionHeader({
  actions,
  className,
  description,
  kicker,
  title,
}: {
  actions?: ReactNode;
  className?: string;
  description?: ReactNode;
  kicker: string;
  title: ReactNode;
}) {
  return (
    <div className={cx(styles.sectionHeader, className)}>
      <div>
        <p className={styles.kicker}>{kicker}</p>
        <h3 className={styles.title}>{title}</h3>
        {description ? <p className={styles.description}>{description}</p> : null}
      </div>
      {actions ? <div>{actions}</div> : null}
    </div>
  );
}

export function DeliveryModalShell({
  children,
  description,
  footer,
  kicker,
  onClose,
  size = "standard",
  title,
}: {
  children: ReactNode;
  description?: ReactNode;
  footer?: ReactNode;
  kicker: string;
  onClose: () => void;
  size?: "standard" | "wide";
  title: ReactNode;
}) {
  const modal = (
    <>
      <div className={styles.modalBackdrop} aria-hidden="true" />
      <div className={styles.modalLayer}>
        <section
          aria-modal="true"
          className={cx(styles.modal, size === "wide" && styles.modalWide)}
          role="dialog"
        >
          <header className={styles.modalHeader}>
            <div>
              <p className={styles.kicker}>{kicker}</p>
              <h3 className={styles.title}>{title}</h3>
              {description ? (
                <p className={styles.description}>{description}</p>
              ) : null}
            </div>
            <button
              aria-label="Close modal"
              className={styles.closeButton}
              onClick={onClose}
              type="button"
            >
              <X aria-hidden="true" size={16} />
            </button>
          </header>
          <div className={styles.modalBody}>{children}</div>
          {footer ? <footer className={styles.modalFooter}>{footer}</footer> : null}
        </section>
      </div>
    </>
  );

  if (typeof document === "undefined") {
    return null;
  }

  return createPortal(modal, document.body);
}

export function DeliveryAdvisorPanel({
  footer,
  profileLabel,
  statusLabel,
  transcript,
}: {
  footer?: ReactNode;
  profileLabel: string;
  statusLabel: string;
  transcript: Array<{
    id: string;
    role: "advisor" | "operator";
    text: string;
  }>;
}) {
  return (
    <DeliveryPanel className={styles.advisorPanel} tone="ok">
      <DeliverySectionHeader
        actions={<DeliveryStatusPill tone="ok">{statusLabel}</DeliveryStatusPill>}
        kicker="Advisor Console"
        title={profileLabel}
      />
      <div className={styles.advisorTranscript}>
        {transcript.map((line) => (
          <p
            className={cx(
              styles.advisorLine,
              line.role === "operator" && styles.advisorOperator,
            )}
            key={line.id}
          >
            {line.text}
          </p>
        ))}
      </div>
      {footer}
    </DeliveryPanel>
  );
}

export type DeliveryRegisterRow = {
  actionLabel: string;
  description: string;
  id: string;
  index: string;
  onAction?: () => void;
  statusLabel: string;
  statusTone: DeliveryTone;
  title: string;
};

export function DeliveryRegisterTable({
  className,
  rows,
  ...props
}: Omit<TableHTMLAttributes<HTMLTableElement>, "children"> & {
  rows: DeliveryRegisterRow[];
}) {
  return (
    <div className={styles.registerShell}>
      <table className={cx(styles.registerTable, className)} {...props}>
        <colgroup>
          <col className={styles.registerIndex} />
          <col />
          <col className={styles.registerStatus} />
          <col className={styles.registerAction} />
        </colgroup>
        <thead>
          <tr>
            <th>No.</th>
            <th>Package</th>
            <th>Status</th>
            <th className={styles.registerActionHeader}>Action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td className={styles.registerIndex}>{row.index}</td>
              <td>
                <p className={styles.registerTitle}>{row.title}</p>
                <p className={styles.registerDescription}>{row.description}</p>
              </td>
              <td>
                <DeliveryStatusPill tone={row.statusTone}>
                  {row.statusLabel}
                </DeliveryStatusPill>
              </td>
              <td className={styles.registerAction}>
                <DeliveryActionButton
                  onClick={row.onAction}
                  variant="secondary"
                >
                  {row.actionLabel}
                </DeliveryActionButton>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function DeliveryTreeNodeCard({
  childrenCount,
  className,
  description,
  selected = false,
  title,
  type,
}: {
  childrenCount?: number;
  className?: string;
  description: string;
  selected?: boolean;
  title: string;
  type: DeliveryComponentType;
}) {
  return (
    <article
      className={cx(
        styles.treeCard,
        type === "Epic" && styles.treeCardEpic,
        type === "Milestone" && styles.treeCardMilestone,
        selected && styles.panelSelected,
        className,
      )}
    >
      <div className={styles.treeMeta}>
        <span className={styles.treeType}>{type}</span>
        {typeof childrenCount === "number" ? (
          <DeliveryStatusPill tone={childrenCount > 0 ? "info" : "muted"}>
            {childrenCount} child
          </DeliveryStatusPill>
        ) : null}
      </div>
      <h4 className={styles.treeTitle}>{title}</h4>
      <p className={styles.treeDescription}>{description}</p>
    </article>
  );
}
