import { ArrowDownUp, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { useControlRoom } from "../app/control-room-context";
import { api } from "../app/services";
import { EmptyState, ErrorState, LoadingState } from "../components/async-state";
import { PageFrame } from "../components/page-frame";
import { Panel } from "../components/panel";
import type { PackageState } from "../domain/control-room";
import { useApiResource } from "../hooks/use-api-resource";
import { formatTimestamp, score, titleCase } from "../lib/format";

type StateFilter = "all" | PackageState;
type SortKey = "name" | "attractiveness" | "policyRisk";

export function PackagesPage() {
  const { liveRevision, openPackage } = useControlRoom();
  const [query, setQuery] = useState("");
  const [state, setState] = useState<StateFilter>("all");
  const [sort, setSort] = useState<SortKey>("attractiveness");
  const resource = useApiResource((signal) => api.getPackages(signal), [liveRevision]);
  const packages = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    return [...(resource.data ?? [])]
      .filter(
        (item) =>
          (state === "all" || item.state === state) &&
          (!normalized || item.name.toLocaleLowerCase().includes(normalized)),
      )
      .sort((left, right) => {
        if (sort === "name") return left.name.localeCompare(right.name);
        if (sort === "policyRisk") return (right.policyRisk ?? -1) - (left.policyRisk ?? -1);
        return right.attractiveness - left.attractiveness;
      });
  }, [resource.data, query, sort, state]);

  return (
    <PageFrame
      eyebrow="Inventory / Tracked"
      title="Tracked Packages"
      description="Registry entities associated with observed recommendations and temporal risk."
    >
      <div className="toolbar toolbar--wrap" data-reveal>
        <label className="search-field">
          <Search size={17} aria-hidden="true" />
          <span className="sr-only">Search packages</span>
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search packages"
          />
        </label>
        <select value={state} onChange={(event) => setState(event.target.value as StateFilter)}>
          <option value="all">All states</option>
          <option value="absent">Absent</option>
          <option value="monitored">Monitored</option>
          <option value="registered">Registered</option>
          <option value="high_risk">High risk</option>
          <option value="blocked">Blocked</option>
        </select>
        <label className="sort-select">
          <ArrowDownUp size={16} aria-hidden="true" />
          <span className="sr-only">Sort packages</span>
          <select value={sort} onChange={(event) => setSort(event.target.value as SortKey)}>
            <option value="attractiveness">Attractiveness</option>
            <option value="policyRisk">Policy risk</option>
            <option value="name">Package name</option>
          </select>
        </label>
      </div>

      {resource.loading && <LoadingState />}
      {resource.error && <ErrorState error={resource.error} retry={resource.reload} />}
      {resource.data && (
        <Panel className="panel--table" eyebrow="Registry view" title={`${packages.length} packages`}>
          {packages.length ? (
            <div className="data-table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Package</th>
                    <th>Registry</th>
                    <th>State</th>
                    <th>Attractiveness</th>
                    <th>Policy risk</th>
                    <th>Last seen</th>
                  </tr>
                </thead>
                <tbody>
                  {packages.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <button type="button" onClick={() => openPackage(item.name)}>
                          {item.name}
                        </button>
                      </td>
                      <td>{item.ecosystem}</td>
                      <td>
                        <span className={`state-chip state-chip--${item.state}`}>
                          {titleCase(item.state)}
                        </span>
                      </td>
                      <td>{item.attractiveness}</td>
                      <td>{score(item.policyRisk)}</td>
                      <td>{formatTimestamp(item.lastSeen)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No matching packages" detail="Change the filters or wait for ingestion." />
          )}
        </Panel>
      )}
    </PageFrame>
  );
}
