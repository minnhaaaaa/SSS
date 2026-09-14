import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PrototypeControlRoomApi } from "./prototype-control-room";

describe("PrototypeControlRoomApi", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("keeps overview totals and package records connected", async () => {
    const api = new PrototypeControlRoomApi();
    const overviewPromise = api.getOverview();
    const packagesPromise = api.getPackages();
    await vi.runAllTimersAsync();

    const [overview, packageList] = await Promise.all([overviewPromise, packagesPromise]);

    expect(overview.radarNodes).toEqual(packageList);
    expect(overview.prioritizedTargets[0]?.name).toBe("@sss-demo/reserved-synthetic");
    expect(overview.verifiedRecommendations).toBe(46);

    const target = api.getPackage("@sss-demo/reserved-synthetic");
    await vi.runAllTimersAsync();
    await expect(target).resolves.toMatchObject({
      absenceConfidence: 100,
      attractiveness: 95,
      policyRisk: 75,
    });
  });

  it("runs the controlled demo only in the permitted sequence", async () => {
    const api = new PrototypeControlRoomApi();
    const replayPromise = api.runDemoAction("replay-evidence");
    await vi.runAllTimersAsync();
    await expect(replayPromise).resolves.toMatchObject({
      completedSteps: ["replay-evidence"],
      availableActions: ["register-target"],
    });

    await expect(api.runDemoAction("run-protected")).rejects.toThrow(
      "Complete the currently available demo step first",
    );

    const registerPromise = api.runDemoAction("register-target");
    await vi.runAllTimersAsync();
    await registerPromise;
    const unprotectedPromise = api.runDemoAction("run-unprotected");
    await vi.runAllTimersAsync();
    await unprotectedPromise;
    const protectedPromise = api.runDemoAction("run-protected");
    await vi.runAllTimersAsync();

    await expect(protectedPromise).resolves.toMatchObject({
      state: "blocked",
      protectedCanaryCount: 0,
      packageManagerStarted: false,
      availableActions: ["replay-evidence"],
    });
  });

  it("honors request cancellation", async () => {
    const api = new PrototypeControlRoomApi();
    const controller = new AbortController();
    const request = api.getPackages(controller.signal);
    controller.abort(new Error("cancelled prototype request"));

    await expect(request).rejects.toThrow("cancelled prototype request");
  });
});
