import { Bot } from "lucide-react";

import { useControlRoom } from "../app/control-room-context";
import { api } from "../app/services";
import { EmptyState, ErrorState, LoadingState } from "../components/async-state";
import { PageFrame } from "../components/page-frame";
import { Panel } from "../components/panel";
import type { CoverageService } from "../domain/control-room";
import { useApiResource } from "../hooks/use-api-resource";
import { formatTimestamp, titleCase } from "../lib/format";

export function CoveragePage() {
  const { liveRevision } = useControlRoom();
  const resource = useApiResource((signal) => api.getCoverage(signal), [liveRevision]);

  return (
    <PageFrame
      eyebrow="System / Coverage"
      title="System Coverage"
      description="Monitoring, protected agents, and enforcement health without inferred success states."
      meta={resource.data ? <span className="data-time">As of {formatTimestamp(resource.data.dataAsOf)}</span> : undefined}
    >
      {resource.loading && <LoadingState />}
      {resource.error && <ErrorState error={resource.error} retry={resource.reload} />}
      {resource.data && (
        <>
          <section className="coverage-grid">
            <Panel eyebrow="Sources" title="Registry Monitoring">
              <ServiceList services={resource.data.registries} emptyLabel="No registries configured" />
            </Panel>
            <Panel eyebrow="Boundary" title="Protected Agents">
              <div className="coverage-hero-number">
                <Bot aria-hidden="true" />
                <strong>{resource.data.protectedAgents}</strong>
                <span>Active agents</span>
              </div>
            </Panel>
            <Panel eyebrow="Telemetry" title="Observation Window">
              <div className="observation-grid">
                <ObservationStat value={resource.data.observationDays} label="Observation days" />
                <ObservationStat value={resource.data.verifiedRecommendations} label="Verified recommendations" />
                <ObservationStat value={resource.data.publicFailedReferences} label="Public failed references" />
                <ObservationStat value={resource.data.modelConfigurations} label="Model configurations" />
              </div>
            </Panel>
            <Panel eyebrow="Control plane" title="System Health">
              <ServiceList services={resource.data.services} emptyLabel="No service health returned" />
            </Panel>
          </section>
        </>
      )}
    </PageFrame>
  );
}

function ServiceList({ services, emptyLabel }: { readonly services: readonly CoverageService[]; readonly emptyLabel: string }) {
  if (!services.length) {
    return <EmptyState title={emptyLabel} detail="The coverage API returned an empty list." />;
  }
  return (
    <ul className="service-list">
      {services.map((service) => (
        <li key={service.id}>
          <span className={`service-state service-state--${service.state}`} aria-hidden="true" />
          <span>
            <strong>{service.name}</strong>
            <small>{service.detail ?? "No additional detail"}</small>
          </span>
          <b>{titleCase(service.state)}</b>
        </li>
      ))}
    </ul>
  );
}

function ObservationStat({ value, label }: { readonly value: number; readonly label: string }) {
  return (
    <div>
      <strong>{value}</strong>
      <span>{label}</span>
    </div>
  );
}
