import { Check, Gavel, ShieldAlert, X } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useControlRoom } from "../app/control-room-context";
import { api } from "../app/services";
import { EmptyState, ErrorState, LoadingState } from "../components/async-state";
import { PageFrame } from "../components/page-frame";
import { Panel } from "../components/panel";
import type { DecisionItem } from "../domain/control-room";
import { useApiResource } from "../hooks/use-api-resource";
import { formatTimestamp, titleCase } from "../lib/format";

export function DecisionsPage() {
  const { liveRevision, openPackage } = useControlRoom();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const resource = useApiResource((signal) => api.getDecisions(signal), [liveRevision]);
  const selected = useMemo(
    () => resource.data?.find((item) => item.id === selectedId) ?? resource.data?.[0] ?? null,
    [resource.data, selectedId],
  );

  useEffect(() => {
    if (!selectedId && resource.data?.[0]) setSelectedId(resource.data[0].id);
  }, [resource.data, selectedId]);

  return (
    <PageFrame
      eyebrow="Guard / Audit"
      title="Guard Decisions"
      description="Deterministic enforcement decisions and the conditions behind them."
      meta={<span className="page-symbol"><Gavel size={20} aria-hidden="true" /> Policy ledger</span>}
    >
      {resource.loading && <LoadingState />}
      {resource.error && <ErrorState error={resource.error} retry={resource.reload} />}
      {resource.data && !resource.data.length && (
        <EmptyState title="No Guard decisions" detail="Decision records will appear after install attempts." />
      )}
      {resource.data && resource.data.length > 0 && (
        <section className="decision-layout">
          <Panel eyebrow="Chronological" title="Recent Decisions" className="decision-list-panel">
            <ol className="decision-list">
              {resource.data.map((item) => (
                <li key={item.id}>
                  <button
                    className={selected?.id === item.id ? "is-selected" : ""}
                    type="button"
                    onClick={() => setSelectedId(item.id)}
                  >
                    <span className={`decision-glyph decision-glyph--${item.result}`} aria-hidden="true">
                      {item.result === "allow" ? <Check /> : item.result === "review" ? <ShieldAlert /> : <X />}
                    </span>
                    <span>
                      <strong>{item.packageName}</strong>
                      <small>{formatTimestamp(item.occurredAt)}</small>
                    </span>
                    <b>{item.result}</b>
                  </button>
                </li>
              ))}
            </ol>
          </Panel>
          {selected && <DecisionInspector decision={selected} openPackage={openPackage} />}
        </section>
      )}
    </PageFrame>
  );
}

function DecisionInspector({
  decision,
  openPackage,
}: {
  readonly decision: DecisionItem;
  readonly openPackage: (name: string) => void;
}) {
  return (
    <Panel eyebrow="Decision inspector" title="Policy Evaluated" className="decision-inspector">
      <button className="package-link-large" type="button" onClick={() => openPackage(decision.packageName)}>
        {decision.packageName}
      </button>
      <div className={`decision-result decision-result--${decision.result}`}>
        <span>Result</span>
        <strong>{decision.result}</strong>
        <small>{decision.policy}</small>
      </div>

      <section className="decision-section">
        <p className="section-label">Audit conditions</p>
        <ul className="condition-list">
          {decision.reasonCodes.map((reason) => (
            <li key={reason}>
              <Check size={16} aria-hidden="true" /> {titleCase(reason)}
            </li>
          ))}
        </ul>
      </section>

      <section className="decision-section">
        <p className="section-label">Enforcement proof</p>
        <dl className="proof-list">
          <div>
            <dt>Package manager started</dt>
            <dd data-safe={decision.packageManagerStarted === false}>
              {decision.packageManagerStarted === null
                ? "Unknown"
                : decision.packageManagerStarted
                  ? "Yes"
                  : "No"}
            </dd>
          </div>
          <div>
            <dt>Package code executed</dt>
            <dd data-safe={decision.packageCodeExecuted === false}>
              {decision.packageCodeExecuted === null
                ? "Unknown"
                : decision.packageCodeExecuted
                  ? "Yes"
                  : "No"}
            </dd>
          </div>
        </dl>
      </section>
    </Panel>
  );
}
