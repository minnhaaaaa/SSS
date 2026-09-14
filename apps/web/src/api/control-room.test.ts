import { describe, expect, it, vi } from "vitest";

import { ApiClient } from "./client";
import { ApiContractError, ControlRoomApi } from "./control-room";

const config = {
  apiBaseUrl: new URL("https://api.example.test"),
  httpTimeoutMs: 1000,
};

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ControlRoomApi", () => {
  it("maps the overview wire contract into the UI domain", async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        data_as_of: "2026-09-13T10:00:00Z",
        guard_status: "operational",
        active_threats: 1,
        protected_agents: 2,
        verified_recommendations: 3,
        radar_nodes: [],
        prioritized_targets: [],
        recent_activity: [],
      }),
    );
    const api = new ControlRoomApi(new ApiClient(config, fetchImplementation));

    await expect(api.getOverview()).resolves.toEqual({
      dataAsOf: "2026-09-13T10:00:00Z",
      guardStatus: "operational",
      activeThreats: 1,
      protectedAgents: 2,
      verifiedRecommendations: 3,
      radarNodes: [],
      prioritizedTargets: [],
      recentActivity: [],
    });
    expect(fetchImplementation.mock.calls[0]?.[0].toString()).toBe(
      "https://api.example.test/v1/overview",
    );
  });

  it("encodes package names before requesting detail", async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        id: "pkg-1",
        name: "@scope/tool name",
        ecosystem: "npm",
        state: "monitored",
        attractiveness: 42,
        policy_risk: null,
        last_seen: null,
        absence_confidence: null,
        lifecycle: [],
      }),
    );
    const api = new ControlRoomApi(new ApiClient(config, fetchImplementation));

    await api.getPackage("@scope/tool name");

    expect(fetchImplementation.mock.calls[0]?.[0].toString()).toBe(
      "https://api.example.test/v1/packages/%40scope%2Ftool%20name",
    );
  });

  it("rejects an unsupported backend enum instead of displaying invented state", async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      jsonResponse({
        data_as_of: "2026-09-13T10:00:00Z",
        guard_status: "perfect",
        active_threats: 0,
        protected_agents: 0,
        verified_recommendations: 0,
        radar_nodes: [],
        prioritized_targets: [],
        recent_activity: [],
      }),
    );
    const api = new ControlRoomApi(new ApiClient(config, fetchImplementation));

    await expect(api.getOverview()).rejects.toBeInstanceOf(ApiContractError);
  });

  it("does not simulate or expose demo mutations in live browser mode", async () => {
    const fetchImplementation = vi.fn<typeof fetch>();
    const api = new ControlRoomApi(new ApiClient(config, fetchImplementation));

    await expect(api.runDemoAction("replay-evidence")).rejects.toThrow(
      "Run the terminal-first demo from the operator shell",
    );
    expect(fetchImplementation).not.toHaveBeenCalled();
  });
});
