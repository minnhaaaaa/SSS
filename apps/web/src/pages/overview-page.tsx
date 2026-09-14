import { type ReactNode } from "react";

import { useControlRoom } from "../app/control-room-context";
import { api } from "../app/services";
import { ErrorState, LoadingState } from "../components/async-state";
import { OverviewRadar } from "../components/overview-radar";
import type { PackageState } from "../domain/control-room";
import { useApiResource } from "../hooks/use-api-resource";
import { titleCase } from "../lib/format";

export function OverviewPage() {
  const { liveRevision, openPackage } = useControlRoom();
  const resource = useApiResource((signal) => api.getOverview(signal), [liveRevision]);

  if (resource.loading) {
    return <OverviewState><LoadingState /></OverviewState>;
  }

  if (resource.error) {
    return <OverviewState><ErrorState error={resource.error} retry={resource.reload} /></OverviewState>;
  }

  if (!resource.data) return null;

  const stats = [
    { value: resource.data.activeThreats, label: "High-Risk Threats", color: "#D9544F" },
    { value: resource.data.protectedAgents, label: "Active Protected Agents", color: "#4CD7F6" },
    { value: resource.data.verifiedRecommendations, label: "Verified Recurrences", color: "#E6AA3C" },
  ] as const;

  return (
    <main className="overview-screen text-[#FFF9F4]">
      <div className="overview-layout mx-auto max-w-[1380px]">
        <section className="overview-radar-panel flex min-h-0 min-w-0 flex-col rounded-[20px] bg-[#626362] p-5">
          <header className="shrink-0 pb-2">
            <h1 className="m-0 text-[1rem] leading-none font-semibold tracking-[-0.025em] text-[#0C0F0C]">
              GLOBAL RECURRENCE RADAR
            </h1>
            <p className="mt-1.5 mb-0 text-[0.65rem] leading-none text-[#0C0F0C]/58">
              Autonomously monitoring AI hallucinated package names and temporal package transitions.
            </p>
          </header>

          <OverviewRadar nodes={resource.data.radarNodes} stats={stats} onSelectPackage={openPackage} />
        </section>

        <aside className="overview-side-panel flex min-h-0 min-w-0 flex-col rounded-[20px] bg-[#626362] p-4">
          <section className="shrink-0">
            <h2 className="m-0 flex h-[28px] items-start text-[0.95rem] leading-none font-semibold tracking-[-0.02em] text-[#0C0F0C]">
              Prioritized Target Queue
            </h2>
            <ol className="overview-queue-card m-0 grid h-[257px] list-none content-center rounded-[20px] bg-[#0C0F0C] px-4 py-3">
              {resource.data.prioritizedTargets.map((item) => (
                <li key={item.id} className="border-b border-[#FFF9F4]/8 last:border-0">
                  <button type="button" onClick={() => openPackage(item.name)} className="grid h-[58px] w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 bg-transparent px-0 text-left">
                    <span className="min-w-0">
                      <strong className="block truncate font-mono text-[0.68rem] font-medium text-[#FFF9F4]">{item.name}</strong>
                      <span className="mt-1 flex items-center gap-3 font-mono text-[0.55rem] uppercase text-[#626362]">
                        {item.ecosystem}
                        <b className="font-medium" style={{ color: stateColor(item.state) }}>{titleCase(item.state)}</b>
                      </span>
                    </span>
                    <span className="flex items-center gap-1 font-mono text-[0.68rem] font-semibold" style={{ color: stateColor(item.state) }}>
                      {item.attractiveness}<i className="text-[#626362] not-italic">›</i>
                    </span>
                  </button>
                </li>
              ))}
            </ol>
          </section>

          <div className="hidden min-h-0 flex-1 xl:block" aria-hidden="true" />

          <section className="shrink-0">
            <div className="overview-activity-heading flex h-[109px] items-center xl:items-end xl:pb-5">
              <h2 className="m-0 text-[0.95rem] leading-none font-semibold tracking-[-0.02em] text-[#0C0F0C]">Recent Activity</h2>
            </div>
            <ol className="overview-activity-card m-0 grid h-[292px] list-none content-center rounded-[20px] bg-[#0C0F0C] px-4 py-3">
              {resource.data.recentActivity.slice(0, 4).map((item, index) => (
                <li key={item.id} className="grid min-h-[61px] grid-cols-[24px_minmax(0,1fr)] gap-3 py-1">
                  <span className="grid size-6 place-items-center rounded-full font-mono text-[0.52rem] font-semibold text-[#0C0F0C]" style={{ backgroundColor: activityColor(item.kind) }}>
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0 font-mono">
                    <div className="flex items-center gap-2 text-[0.53rem] font-semibold uppercase" style={{ color: activityColor(item.kind) }}>
                      <time dateTime={item.occurredAt}>{formatActivityDate(item.occurredAt)}</time>
                      <span>·</span>
                      <strong className="font-semibold">{titleCase(item.kind)}</strong>
                    </div>
                    {item.packageName ? (
                      <button type="button" onClick={() => openPackage(item.packageName!)} className="mt-0.5 block max-w-full truncate bg-transparent p-0 text-[0.58rem] leading-none text-[#FFF9F4] hover:text-[#4CD7F6]">
                        {item.packageName}
                      </button>
                    ) : (
                      <span className="mt-0.5 block text-[0.58rem] text-[#FFF9F4]">System</span>
                    )}
                    <p className="mt-0.5 mb-0 truncate text-[0.52rem] leading-none text-[#626362]">{item.label}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </main>
  );
}

function OverviewState({ children }: { readonly children: ReactNode }) {
  return <main className="grid min-h-screen place-items-center bg-[#0C0F0C] p-6">{children}</main>;
}

function stateColor(state: PackageState): string {
  if (state === "blocked" || state === "high_risk") return "#D9544F";
  if (state === "registered") return "#E6AA3C";
  if (state === "monitored") return "#4CD7F6";
  return "#FFF9F4";
}

function activityColor(kind: string): string {
  if (kind === "blocked" || kind === "high_risk") return "#D9544F";
  if (kind === "registered") return "#E6AA3C";
  return "#4CD7F6";
}

function formatActivityDate(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "2-digit" }).format(date);
}
