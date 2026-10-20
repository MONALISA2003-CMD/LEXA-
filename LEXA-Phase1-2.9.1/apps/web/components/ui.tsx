"use client";

import {
  cloneElement,
  isValidElement,
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type CSSProperties,
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
  type Ref,
} from "react";

export type ButtonVariant = "primary" | "secondary" | "light" | "danger";
export type ButtonSize = "sm" | "md" | "lg";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  fullWidth?: boolean;
  ref?: Ref<HTMLButtonElement>;
};

/** Shared button primitive. Existing button-* CSS classes remain supported during migration. */
export function Button({
  variant = "primary",
  size = "md",
  loading = false,
  fullWidth = false,
  ref,
  className = "",
  disabled,
  type = "button",
  children,
  ...props
}: ButtonProps) {
  const variantClass: Record<ButtonVariant, string> = {
    primary: "button-dark",
    secondary: "button-soft",
    light: "button-light",
    danger: "button-danger",
  };
  const sizeClass = size === "sm" ? "button-small" : size === "lg" ? "button-large" : "";
  const classes = ["button", variantClass[variant], sizeClass, fullWidth ? "button-full" : "", className]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      {...props}
      ref={ref}
      type={type}
      className={classes}
      disabled={Boolean(disabled || loading)}
      aria-busy={loading || undefined}
    >
      {loading && <span className="lexa-button-progress" aria-hidden="true">◌</span>}
      {children}
    </button>
  );
}

export type BadgeVariant = "neutral" | "info" | "success" | "warning" | "danger";

/** Compact, non-interactive label for record and workflow status. */
export function Badge({ variant = "neutral", children, className = "" }: {
  variant?: BadgeVariant;
  children: ReactNode;
  className?: string;
}) {
  return <span className={["lexa-badge", `lexa-badge-${variant}`, className].filter(Boolean).join(" ")}>{children}</span>;
}

export type SkeletonShape = "text" | "rect" | "circle";

/** Decorative loading placeholder; it deliberately carries no business values. */
export function Skeleton({ shape = "text", width, height, className = "" }: {
  shape?: SkeletonShape;
  width?: CSSProperties["width"];
  height?: CSSProperties["height"];
  className?: string;
}) {
  const style: CSSProperties = {};
  if (width !== undefined) style.width = width;
  if (height !== undefined) style.height = height;
  return <span className={["lexa-skeleton", `lexa-skeleton-${shape}`, className].filter(Boolean).join(" ")} style={style} aria-hidden="true" />;
}

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
        {(onRetry || action) && <div className="data-state-actions">{onRetry && <Button variant="secondary" size="sm" onClick={onRetry} loading={isLoading}>{isLoading ? "Checking…" : "Try again"}</Button>}{action}</div>}
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
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  let fieldControl = children;

  // Wire accessible names and validation state when the control is a direct child.
  // Wrapped controls retain their explicitly authored IDs (used by password fields).
  if (isValidElement(children) && typeof children.type === "string" && ["input", "select", "textarea"].includes(children.type)) {
    const control = children as ReactElement<{
      id?: string;
      "aria-describedby"?: string;
      "aria-invalid"?: boolean | "true" | "false";
    }>;
    const existingDescription = control.props["aria-describedby"];
    fieldControl = cloneElement(control, {
      id: control.props.id || inputId,
      "aria-describedby": [existingDescription, describedBy].filter(Boolean).join(" ") || undefined,
      "aria-invalid": error ? true : control.props["aria-invalid"],
    });
  }

  return (
    <div className={`form-field ${error ? "form-field-invalid" : ""}`}>
      <label htmlFor={inputId}>{label}{required && <span aria-hidden="true"> *</span>}</label>
      {fieldControl}
      {hint && <small id={hintId} className="form-field-hint">{hint}</small>}
      {error && <small id={errorId} className="form-field-error" role="alert">{error}</small>}
    </div>
  );
}

export function ConfirmDialog({ open, title, description, confirmLabel = "Confirm", cancelLabel = "Cancel", destructive = false, busy = false, onConfirm, onCancel }: { open: boolean; title: string; description: string; confirmLabel?: string; cancelLabel?: string; destructive?: boolean; busy?: boolean; onConfirm: () => void; onCancel: () => void }) {
  const titleId = useId();
  const descriptionId = useId();
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLElement>(null);
  const busyRef = useRef(busy);
  const onCancelRef = useRef(onCancel);
  useEffect(() => { busyRef.current = busy; onCancelRef.current = onCancel; }, [busy, onCancel]);

  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    const previouslyFocused = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape") {
        if (!busyRef.current) onCancelRef.current();
        return;
      }
      if (event.key !== "Tab") return;

      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])',
      );
      if (!focusable?.length) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;
      if (event.shiftKey && (active === first || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !dialogRef.current?.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    cancelRef.current?.focus();
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [open]);

  if (!open) return null;
  return (
    <div className="confirm-dialog-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
      <section ref={dialogRef} className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={descriptionId} tabIndex={-1}>
        <div className={`confirm-dialog-icon ${destructive ? "confirm-dialog-icon-danger" : ""}`} aria-hidden="true">{destructive ? "!" : "?"}</div>
        <h2 id={titleId}>{title}</h2>
        <p id={descriptionId}>{description}</p>
        <div className="confirm-dialog-actions">
          <Button ref={cancelRef} variant="secondary" onClick={onCancel} disabled={busy}>{cancelLabel}</Button>
          <Button variant={destructive ? "danger" : "primary"} onClick={onConfirm} loading={busy}>{busy ? "Working…" : confirmLabel}</Button>
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
