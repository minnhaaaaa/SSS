import { useControlRoom } from "../app/control-room-context";
import { api } from "../app/services";
import { ErrorState, LoadingState } from "../components/async-state";
import { OverviewRadar } from "../components/overview-radar";
import { PageFrame } from "../components/page-frame";
import { useApiResource } from "../hooks/use-api-resource";

export function RadarPage() {
  const { liveRevision, openPackage } = useControlRoom();
  const resource = useApiResource((signal) => api.getOverview(signal), [liveRevision]);
  const legendStats = resource.data
    ? [
        { kind: "risk", value: resource.data.activeThreats, label: "High-Risk Threats", color: "#D9544F" },
        { kind: "protected", value: resource.data.protectedAgents, label: "Active Protected Agents", color: "#4CD7F6" },
        { kind: "verified", value: resource.data.verifiedRecommendations, label: "Verified Recurrences", color: "#E6AA3C" },
      ] as const
    : [];

  return (
    <PageFrame
      eyebrow="Intelligence / Recurrence"
      title="Global Recurrence Radar"
      description="Inspect recurring package signals across npm and PyPI."
    >
      {resource.loading && <LoadingState />}
      {resource.error && <ErrorState error={resource.error} retry={resource.reload} />}
      {resource.data && (
        <section className="radar-page-surface flex min-w-0 flex-col rounded-[20px] bg-[#626362] p-5" data-reveal>
          <OverviewRadar
            nodes={resource.data.radarNodes}
            legendStats={legendStats}
            onSelectPackage={openPackage}
          />
        </section>
      )}
    </PageFrame>
  );
}
