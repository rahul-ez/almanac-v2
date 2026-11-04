import { useEffect, useRef, type ReactNode } from 'react';
import { useBlocker } from 'react-router';
import { ArrowClockwise, WarningCircle, X } from '@phosphor-icons/react';
import { ApiError, errorMessage } from '../api/errors';

export function Notice({
  children,
  tone = 'info',
}: {
  children: ReactNode;
  tone?: 'info' | 'warning' | 'success';
}) {
  return (
    <div className={`notice ${tone}`} role={tone === 'warning' ? 'alert' : 'status'}>
      {children}
    </div>
  );
}
export function ErrorNotice({ error, retry }: { error: unknown; retry?: () => void }) {
  return (
    <div className="error-notice" role="alert">
      <WarningCircle size={23} />
      <div>
        <strong>{errorMessage(error)}</strong>
        {error instanceof ApiError && error.requestId && (
          <small>Reference: {error.requestId}</small>
        )}
        {retry && (
          <button className="text-button" onClick={retry}>
            <ArrowClockwise size={16} /> Try again
          </button>
        )}
      </div>
    </div>
  );
}
export function Skeleton({ count = 3 }: { count?: number }) {
  return (
    <div className="skeleton-stack" role="status" aria-label="Loading">
      {Array.from({ length: count }, (_, i) => (
        <div className="skeleton" key={i}>
          <span />
          <span />
          <span />
        </div>
      ))}
    </div>
  );
}
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon?: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      {icon && <span className="empty-icon">{icon}</span>}
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function PageHeading({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function Dialog({
  open,
  onClose,
  title,
  children,
  className = '',
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const el = ref.current;
    if (open && el && !el.open) el.showModal();
    else if (!open && el?.open) el.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      className={`dialog ${className}`}
      aria-label={title}
      onCancel={(e) => {
        e.preventDefault();
        closeRef.current();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) closeRef.current();
      }}
    >
      <div className="dialog-heading">
        <h2>{title}</h2>
        <button className="icon-button" onClick={onClose} aria-label="Close dialog">
          <X size={20} />
        </button>
      </div>
      {children}
    </dialog>
  );
}
export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  children,
  busy,
  label = 'Delete',
  error,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  children: ReactNode;
  busy?: boolean;
  label?: string;
  error?: unknown;
}) {
  return (
    <Dialog
      open={open}
      onClose={() => {
        if (!busy) onClose();
      }}
      title={title}
    >
      <p>{children}</p>
      {!!error && <ErrorNotice error={error} />}
      <div className="dialog-actions">
        <button className="button secondary" onClick={onClose} disabled={busy}>
          Keep it
        </button>
        <button className="button danger" disabled={busy} onClick={onConfirm}>
          {busy ? 'Working…' : label}
        </button>
      </div>
    </Dialog>
  );
}
export function useUnsavedChanges(dirty: boolean) {
  const allow = useRef(false);
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && !allow.current && currentLocation.pathname !== nextLocation.pathname,
  );
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (dirty && !allow.current) event.preventDefault();
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);
  return {
    allow,
    dialog: (
      <Dialog
        open={blocker.state === 'blocked'}
        onClose={() => blocker.state === 'blocked' && blocker.reset()}
        title="Leave without saving?"
      >
        <p>Your changes have not been saved.</p>
        <div className="dialog-actions">
          <button
            className="button secondary"
            onClick={() => blocker.state === 'blocked' && blocker.reset()}
          >
            Keep editing
          </button>
          <button
            className="button danger"
            onClick={() => blocker.state === 'blocked' && blocker.proceed()}
          >
            Discard changes
          </button>
        </div>
      </Dialog>
    ),
  };
}
export function FieldError({ message, id }: { message?: string; id: string }) {
  return message ? (
    <span id={id} className="field-error">
      {message}
    </span>
  ) : null;
}
export function Pagination({
  next,
  busy,
  onNext,
}: {
  next: string | null;
  busy?: boolean;
  onNext: () => void;
}) {
  return next ? (
    <div className="pagination">
      <button className="button secondary" disabled={busy} onClick={onNext}>
        {busy ? 'Loading…' : 'Load more'}
      </button>
    </div>
  ) : null;
}
