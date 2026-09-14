import { AlertTriangle, DatabaseZap, RefreshCw } from "lucide-react";

export function LoadingState({ label = "Synchronizing live data" }: { readonly label?: string }) {
  return (
    <div className="state-state state-state--loading" role="status">
      <span className="loader-ring" aria-hidden="true" />
      <div>
        <strong>{label}</strong>
        <span>Waiting for the active data source to respond.</span>
      </div>
    </div>
  );
}

export function ErrorState({ error, retry }: { readonly error: Error; readonly retry: () => void }) {
  return (
    <div className="state-state state-state--error" role="alert">
      <AlertTriangle aria-hidden="true" />
      <div>
        <strong>Live data unavailable</strong>
        <span>{error.message}</span>
      </div>
      <button className="button button--quiet" type="button" onClick={retry}>
        <RefreshCw size={15} aria-hidden="true" /> Retry
      </button>
    </div>
  );
}

export function EmptyState({ title, detail }: { readonly title: string; readonly detail: string }) {
  return (
    <div className="state-state state-state--empty">
      <DatabaseZap aria-hidden="true" />
      <div>
        <strong>{title}</strong>
        <span>{detail}</span>
      </div>
    </div>
  );
}
