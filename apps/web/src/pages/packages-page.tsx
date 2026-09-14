import { Ban, Boxes, Eye, Search, ShieldAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { useControlRoom } from "../app/control-room-context";
import { api } from "../app/services";
import { EmptyState, ErrorState, LoadingState } from "../components/async-state";
import { MetricTile } from "../components/metric-tile";
import { PageFrame } from "../components/page-frame";
import { Panel } from "../components/panel";
import type { Ecosystem, PackageState } from "../domain/control-room";
import { useApiResource } from "../hooks/use-api-resource";
import { formatTimestamp, score, titleCase } from "../lib/format";

type StateFilter = "all" | PackageState;
type EcosystemFilter = "all" | Ecosystem;
type SortKey = "name" | "attractiveness" | "policyRisk" | "lastSeen";

const stateFilters: readonly StateFilter[] = ["all", "absent", "monitored", "registered", "high_risk", "blocked"];

export function PackagesPage() {
  const { liveRevision, openPackage } = useControlRoom();
  const [query, setQuery] = useState("");
  const [state, setState] = useState<StateFilter>("all");
  const [ecosystem, setEcosystem] = useState<EcosystemFilter>("all");
  const [sort, setSort] = useState<SortKey>("attractiveness");
  const resource = useApiResource((signal) => api.getPackages(signal), [liveRevision]);
  const inventory = resource.data ?? [];
  const summary = useMemo(() => ({
    total: inventory.length,
    elevated: inventory.filter((item) => (item.policyRisk ?? 0) >= 60).length,
    blocked: inventory.filter((item) => item.state === "blocked").length,
    monitored: inventory.filter((item) => item.state === "monitored").length,
  }), [inventory]);
  const stateCounts = useMemo(() => Object.fromEntries(
    stateFilters.map((value) => [value, value === "all" ? inventory.length : inventory.filter((item) => item.state === value).length]),
  ) as Record<StateFilter, number>, [inventory]);
  const packages = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return [...(resource.data ?? [])]
      .filter(
        (item) =>
          (state === "all" || item.state === state) &&
          (ecosystem === "all" || item.ecosystem === ecosystem) &&
          (!normalized || item.name.toLocaleLowerCase().includes(normalized)),
      )
      .sort((left, right) => {
        if (sort === "name") return left.name.localeCompare(right.name);
        if (sort === "policyRisk") return (right.policyRisk ?? -1) - (left.policyRisk ?? -1);
        if (sort === "lastSeen") return dateValue(right.lastSeen) - dateValue(left.lastSeen);
        return right.attractiveness - left.attractiveness;
      });
  }, [resource.data, ecosystem, query, sort, state]);

  return (
    <PageFrame
      eyebrow="Inventory / Tracked"
      title="Tracked Packages"
      description="Registry entities associated with observed recommendations and temporal risk."
    >
      {resource.loading && <LoadingState />}
      {resource.error && <ErrorState error={resource.error} retry={resource.reload} />}
      {resource.data && (
        <>
          <section className="metrics-grid package-metrics" aria-label="Package inventory summary">
            <MetricTile icon={Boxes} label="Tracked" value={summary.total} detail="Registry entities" />
            <MetricTile icon={ShieldAlert} tone="danger" label="Elevated risk" value={summary.elevated} detail="Policy risk 60 or above" />
            <MetricTile icon={Ban} tone="danger" label="Blocked" value={summary.blocked} detail="Guard-enforced packages" />
            <MetricTile icon={Eye} tone="signal" label="Monitored" value={summary.monitored} detail="Active recurrence watch" />
          </section>

          <Panel className="package-workbench" eyebrow="Inventory controls" title="Signal Workbench">
            <div className="package-filter-grid">
              <label className="search-field">
                <Search size={17} aria-hidden="true" />
                <span className="sr-only">Search packages</span>
                <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search package name" />
              </label>
              <div className="segmented" aria-label="Registry filter">
                {(["all", "npm", "pypi"] as const).map((value) => (
                  <button key={value} type="button" className={ecosystem === value ? "is-active" : ""} onClick={() => setEcosystem(value)}>
                    {value === "all" ? "Both" : value}
                  </button>
                ))}
              </div>
              <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)} aria-label="Sort packages">
                <option value="attractiveness">Highest attractiveness</option>
                <option value="policyRisk">Highest policy risk</option>
                <option value="lastSeen">Most recently seen</option>
                <option value="name">Package name</option>
              </select>
            </div>
            <div className="state-filter-row" aria-label="Package state filter">
              {stateFilters.map((value) => (
                <button key={value} type="button" className={state === value ? "is-active" : ""} onClick={() => setState(value)}>
                  <span className={value === "all" ? "state-filter-dot" : `state-filter-dot state-filter-dot--${value}`} aria-hidden="true" />
                  {value === "all" ? "All states" : titleCase(value)}
                  <b>{stateCounts[value]}</b>
                </button>
              ))}
            </div>
          </Panel>

          <Panel className="panel--table package-table-panel" eyebrow="Registry view" title={`${packages.length} matching packages`}>
            {packages.length ? (
              <div className="data-table-wrap">
                <table className="data-table package-table">
                  <thead>
                    <tr>
                      <th>Package</th>
                      <th>Registry</th>
                      <th>State</th>
                      <th>Attractiveness</th>
                      <th>Policy risk</th>
                      <th>Last observation</th>
                      <th><span className="sr-only">Inspect</span></th>
                    </tr>
                  </thead>
                  <tbody>
                    {packages.map((item) => (
                      <tr key={item.id}>
                        <td>
                          <button type="button" onClick={() => openPackage(item.name)}>
                            <strong>{item.name}</strong>
                            <small>{item.id}</small>
                          </button>
                        </td>
                        <td><span className="registry-chip">{item.ecosystem}</span></td>
                        <td><span className={`state-chip state-chip--${item.state}`}>{titleCase(item.state)}</span></td>
                        <td><ScoreCell value={item.attractiveness} tone="cyan" /></td>
                        <td><ScoreCell value={item.policyRisk} tone="risk" /></td>
                        <td>{formatTimestamp(item.lastSeen)}</td>
                        <td><button className="inspect-package-button" type="button" onClick={() => openPackage(item.name)}>Inspect</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState title="No matching packages" detail="Change the filters or wait for ingestion." />
            )}
          </Panel>
        </>
      )}
    </PageFrame>
  );
}

function ScoreCell({ value, tone }: { readonly value: number | null; readonly tone: "cyan" | "risk" }) {
  const normalized = value ?? 0;
  return (
    <span className={`score-cell score-cell--${tone}`}>
      <span aria-hidden="true"><i style={{ width: `${normalized}%` }} /></span>
      <b>{score(value)}</b>
    </span>
  );
}

function dateValue(value: string | null): number {
  if (!value) return 0;
  const parsed = new Date(value).getTime();
  return Number.isNaN(parsed) ? 0 : parsed;
}
