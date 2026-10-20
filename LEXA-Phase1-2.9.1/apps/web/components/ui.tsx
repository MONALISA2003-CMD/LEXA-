"use client";

import { useEffect, useId, useRef, type ReactNode, type KeyboardEvent } from "react";

export type DataStateKind = "loading" | "empty" | "error" | "forbidden" | "unavailable" | "success";

type DataStateProps = {
  state: DataStateKind;
  title?: string;
  description?: string;
  onRetry?: () => void;
  action?: ReactNode;
  compact?: boolean;
};

const stateCopy: Record<Exclude<DataStateKind, "success">, { title: string; description: string; icon: string }> = {
  loading: { title: "Loading your data", description: "We are checking the latest information from LEXA.", icon: "◌" },
  empty: { title: "Nothing here yet", description: "When a record is created, it will appear here.", icon: "＋" },
  error: { title: "We could not load this data", description: "Your records have not been reported as changed. Retry to check the latest state.", icon: "!" },
  forbidden: { title: "You do not have access", description: "Ask your workspace administrator to review your access for this task.", icon: "⊘" },
  unavailable: { title: "LEXA is temporarily unavailable", description: "Check your connection and retry. We will not treat missing data as zero.", icon: "↻" },
};

export function DataState({ state, title, description, onRetry, action, compact = false }: DataStateProps) {
  if (state === "success") return null;
  const copy = stateCopy[state];
  const isLoading = state === "loading";
  return (
    <section className={`data-state ${compact ? "data-state-compact" : ""} data-state-${state}`} role={state === "error" || state === "forbidden" || state === "unavailable" ? "alert" : "status"} aria-live="polite">
      <span className={`data-state-icon ${isLoading ? "data-state-spinner" : ""}`} aria-hidden="true">{copy.icon}</span>
      <div className="data-state-copy">
        <strong>{title || copy.title}</strong>
        <p>{description || copy.description}</p>
        {(onRetry || action) && <div className="data-state-actions">{onRetry && <button type="button" className="button button-soft button-small" onClick={onRetry} disabled={isLoading}>{isLoading ? "Checking…" : "Try again"}</button>}{action}</div>}
      </div>
    </section>
  );
}

export function StatusBanner({ variant = "info", title, children, onDismiss }: { variant?: "info" | "success" | "warning" | "error"; title?: string; children: ReactNode; onDismiss?: () => void }) {
  return (
    <div className={`status-banner status-banner-${variant}`} role={variant === "error" ? "alert" : "status"} aria-live={variant === "error" ? "assertive" : "polite"}>
      <span className="status-banner-mark" aria-hidden="true">{variant === "success" ? "✓" : variant === "warning" ? "!" : variant === "error" ? "×" : "i"}</span>
      <div className="status-banner-content">{title && <strong>{title}</strong>}<div>{children}</div></div>
      {onDismiss && <button className="status-banner-dismiss" type="button" onClick={onDismiss} aria-label="Dismiss message">×</button>}
    </div>
  );
}

export function PageHeader({ eyebrow, title, description, context, action }: { eyebrow?: string; title: string; description?: string; context?: ReactNode; action?: ReactNode }) {
  return (
    <header className="standard-page-header">
      <div className="standard-page-heading">
        {eyebrow && <div className="page-eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
        {context && <div className="standard-page-context">{context}</div>}
      </div>
      {action && <div className="standard-page-action">{action}</div>}
    </header>
  );
}

export function FormField({ id, label, hint, error, required, children }: { id?: string; label: string; hint?: string; error?: string; required?: boolean; children: ReactNode }) {
  const generatedId = useId();
  const inputId = id || generatedId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  return (
    <div className={`form-field ${error ? "form-field-invalid" : ""}`}>
      <label htmlFor={inputId}>{label}{required && <span aria-hidden="true"> *</span>}</label>
      {children}
      {hint && <small id={hintId} className="form-field-hint">{hint}</small>}
      {error && <small id={errorId} className="form-field-error" role="alert">{error}</small>}
    </div>
  );
}

export function ConfirmDialog({ open, title, description, confirmLabel = "Confirm", cancelLabel = "Cancel", destructive = false, busy = false, onConfirm, onCancel }: { open: boolean; title: string; description: string; confirmLabel?: string; cancelLabel?: string; destructive?: boolean; busy?: boolean; onConfirm: () => void; onCancel: () => void }) {
  const titleId = useId();
  const descriptionId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape" && !busy) onCancel();
    };
    window.addEventListener("keydown", handleKeyDown);
    cancelRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, busy, onCancel]);
  if (!open) return null;
  return (
    <div className="confirm-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
      <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId}>
        <div className={`confirm-dialog-icon ${destructive ? "confirm-dialog-icon-danger" : ""}`} aria-hidden="true">{destructive ? "!" : "?"}</div>
        <h2 id={titleId}>{title}</h2>
        <p id={descriptionId}>{description}</p>
        <div className="confirm-dialog-actions">
          <button ref={cancelRef} type="button" className="button button-soft" onClick={onCancel} disabled={busy}>{cancelLabel}</button>
          <button type="button" className={`button ${destructive ? "button-danger" : "button-dark"}`} onClick={onConfirm} disabled={busy}>{busy ? "Working…" : confirmLabel}</button>
        </div>
      </section>
    </div>
  );
}

export type TableColumn<T> = { key: string; label: string; render: (row: T) => ReactNode; hideOnMobile?: boolean; align?: "left" | "right" | "center" };

export function ResponsiveDataTable<T>({ rows, columns, getKey, mobileTitle, mobileSubtitle, state = "success", stateTitle, stateDescription, onRetry, onRowClick, emptyAction }: { rows: T[]; columns: TableColumn<T>[]; getKey: (row: T) => string; mobileTitle: (row: T) => ReactNode; mobileSubtitle?: (row: T) => ReactNode; state?: DataStateKind; stateTitle?: string; stateDescription?: string; onRetry?: () => void; onRowClick?: (row: T) => void; emptyAction?: ReactNode }) {
  const needsState = rows.length === 0 && state !== "success";
  const stateElement = needsState ? <DataState state={state} title={stateTitle} description={stateDescription} onRetry={onRetry} action={emptyAction} /> : null;
  const rowProps = (row: T) => onRowClick ? {
    role: "button" as const,
    tabIndex: 0,
    onClick: () => onRowClick(row),
    onKeyDown: (event: KeyboardEvent<HTMLTableRowElement>) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); onRowClick(row); } },
  } : {};
  return (
    <div className="responsive-data-table">
      {rows.length > 0 && (state === "error" || state === "forbidden" || state === "unavailable" || state === "loading") && <DataState state={state} title={stateTitle} description={stateDescription} onRetry={onRetry} compact />}
      {needsState ? stateElement : <>
        <div className="responsive-table-desktop data-table-wrap">
          <table className="data-table">
            <thead><tr>{columns.map((column) => <th key={column.key} className={column.align ? `align-${column.align}` : ""}>{column.label}</th>)}</tr></thead>
            <tbody>{rows.map((row) => <tr key={getKey(row)} className={onRowClick ? "responsive-table-row-clickable" : ""} {...rowProps(row)}>{columns.map((column) => <td key={column.key} className={`${column.align ? `align-${column.align}` : ""} ${column.hideOnMobile ? "column-mobile-hidden" : ""}`}>{column.render(row)}</td>)}</tr>)}</tbody>
          </table>
        </div>
        <div className="responsive-table-mobile">
          {rows.map((row) => <MobileRecordCard
            key={getKey(row)}
            title={mobileTitle(row)}
            subtitle={mobileSubtitle?.(row)}
            onClick={onRowClick ? () => onRowClick(row) : undefined}
          >
            <dl className="mobile-record-fields">{columns.filter((column) => !column.hideOnMobile).map((column) => <div key={column.key} className="mobile-record-field"><dt>{column.label}</dt><dd>{column.render(row)}</dd></div>)}</dl>
          </MobileRecordCard>)}
        </div>
      </>}
    </div>
  );
}

export function MobileRecordCard({ title, subtitle, status, children, onClick }: { title: ReactNode; subtitle?: ReactNode; status?: ReactNode; children?: ReactNode; onClick?: () => void }) {
  const body = <><div className="mobile-record-card-head"><div className="mobile-record-card-title-row"><strong className="mobile-record-title-static">{title}</strong>{status}</div>{subtitle && <div className="mobile-record-subtitle">{subtitle}</div>}</div>{children && <div className="mobile-record-card-body">{children}</div>}</>;
  return onClick ? <button type="button" className="mobile-record-card mobile-record-card-button" onClick={onClick}>{body}</button> : <article className="mobile-record-card">{body}</article>;
}
