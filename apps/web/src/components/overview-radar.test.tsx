import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import type { PackageSummary } from "../domain/control-room";
import { OverviewRadar } from "./overview-radar";

const nodes: readonly PackageSummary[] = [
  {
    id: "pkg-1",
    name: "synthetic-npm-name",
    ecosystem: "npm",
    state: "blocked",
    attractiveness: 95,
    policyRisk: 95,
    lastSeen: "2026-09-13T00:00:00.000Z",
  },
];

describe("OverviewRadar", () => {
  it("keeps dashboard statistics separate from the state legend", () => {
    const markup = renderToStaticMarkup(
      <OverviewRadar
        nodes={nodes}
        stats={[{ label: "High-Risk Threats", value: 3, color: "#D9544F" }]}
        onSelectPackage={() => undefined}
      />,
    );

    expect(markup).toContain('aria-label="Dashboard statistics"');
    expect(markup).not.toContain('aria-label="Radar node legend"');
  });

  it("renders the five reference state filters without dashboard statistics", () => {
    const markup = renderToStaticMarkup(
      <OverviewRadar nodes={nodes} showStateLegend onSelectPackage={() => undefined} />,
    );

    expect(markup).toContain('aria-label="Radar node legend"');
    expect(markup).not.toContain('aria-label="Dashboard statistics"');
    expect(markup).toContain("Package State");
    for (const label of ["Blocked", "High Risk", "Registered", "Monitored", "Absent"]) {
      expect(markup).toContain(`>${label}</button>`);
    }
  });

  it("uses the supplied fitted zoom and keeps node intelligence hidden until hover", () => {
    const markup = renderToStaticMarkup(
      <OverviewRadar nodes={nodes} initialZoom={1.1} onSelectPackage={() => undefined} />,
    );

    expect(markup).toContain(">110%</output>");
    expect(markup).toContain("scale(1.1)");
    expect(markup).toContain('pointer-events="none" opacity="0"');
    expect(markup).toContain("NODE INTELLIGENCE");
  });
});
