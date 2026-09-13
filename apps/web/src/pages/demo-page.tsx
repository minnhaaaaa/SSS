import { Activity, DatabaseZap, ShieldCheck, Terminal } from "lucide-react";

import { api } from "../app/services";
import { EmptyState, ErrorState, LoadingState } from "../components/async-state";
import { PageFrame } from "../components/page-frame";
import { Panel } from "../components/panel";
import type { DecisionItem } from "../domain/control-room";
import { useApiResource } from "../hooks/use-api-resource";
import { formatTimestamp, titleCase } from "../lib/format";

export function DemoPage() {
  const resource = useApiResource(async (signal) => {
    const [decisions, coverage] = await Promise.all([
      api.getDecisions(signal),
      api.getCoverage(signal),
    ]);
    return { decisions, coverage };
  }, []);

  return (
    <PageFrame
      eyebrow="Enforcement / Runtime"
      title="Live Protection Evidence"
      description="Observed enforcement outcomes and telemetry from the active control plane."
    >
      {resource.loading && <LoadingState label="Reading runtime evidence" />}
      {resource.error && <ErrorState error={resource.error} retry={resource.reload} />}
      {resource.data && (
        <div className="grid gap-5">
          <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-label="Observed totals">
            <Metric label="Guard decisions" value={resource.data.decisions.length} />
            <Metric label="Protected agents" value={resource.data.coverage.protectedAgents} />
            <Metric
              label="Verified recommendations"
              value={resource.data.coverage.verifiedRecommendations}
            />
            <Metric label="Observation days" value={resource.data.coverage.observationDays} />
          </section>

          {resource.data.decisions.length === 0 ? (
            <EmptyState
              title="No enforcement activity observed"
              detail="Guard decisions will appear here after an authenticated install check is received."
            />
          ) : (
            <Panel eyebrow="Observed decisions" title="Runtime Ledger">
              <ol className="m-0 grid list-none gap-3 p-0">
                {resource.data.decisions.slice(0, 20).map((decision) => (
                  <DecisionRow key={decision.id} decision={decision} />
                ))}
              </ol>
            </Panel>
          )}
        </div>
      )}
    </PageFrame>
  );
}

function Metric({ label, value }: { readonly label: string; readonly value: number }) {
  return (
    <article className="rounded-[20px] bg-[#626362] p-5 text-[#0C0F0C]">
      <Activity size={18} aria-hidden="true" />
      <span className="mt-5 block font-mono text-[0.68rem] uppercase tracking-[0.12em] opacity-65">
        {label}
      </span>
      <strong className="mt-2 block font-mono text-3xl">{value}</strong>
    </article>
  );
}

function DecisionRow({ decision }: { readonly decision: DecisionItem }) {
  return (
    <li className="grid gap-3 rounded-[18px] bg-[#0C0F0C] p-4 text-[#FFF9F4] md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
      <div className="min-w-0">
        <strong className="block truncate font-mono text-sm">{decision.packageName}</strong>
        <span className="mt-1 block font-mono text-[0.68rem] text-[#BCC9CD]">
          {decision.ecosystem.toUpperCase()} · {formatTimestamp(decision.occurredAt)} · {decision.policy}
        </span>
      </div>
      <div className="flex flex-wrap items-center gap-2 font-mono text-[0.68rem] uppercase">
        <span className="rounded-full bg-[#1E3B29] px-3 py-1.5">
          <ShieldCheck className="mr-1 inline" size={13} aria-hidden="true" />
          {titleCase(decision.result)}
        </span>
        <span className="rounded-full border border-[#FFF9F4]/15 px-3 py-1.5">
          <Terminal className="mr-1 inline" size={13} aria-hidden="true" />
          Manager {decision.packageManagerStarted === null ? "unknown" : decision.packageManagerStarted ? "started" : "not started"}
        </span>
        <span className="rounded-full border border-[#FFF9F4]/15 px-3 py-1.5">
          <DatabaseZap className="mr-1 inline" size={13} aria-hidden="true" />
          Code {decision.packageCodeExecuted === null ? "unknown" : decision.packageCodeExecuted ? "executed" : "not executed"}
        </span>
      </div>
    </li>
  );
}
