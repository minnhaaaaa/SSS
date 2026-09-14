import type {
  ActivityItem,
  CoverageData,
  DecisionItem,
  DemoAction,
  DemoStatus,
  EvidenceItem,
  OverviewData,
  PackageDetail,
  PackageSummary,
} from "../domain/control-room";
import type { ControlRoomService } from "./control-room";

const TARGET_PACKAGE = "@sss-demo/reserved-synthetic";

const packages: readonly PackageSummary[] = [
  packageSummary("pkg-001", TARGET_PACKAGE, "npm", "blocked", 95, 75, 7),
  packageSummary("pkg-002", "neural-optimizer-core", "npm", "registered", 88, 64, 25),
  packageSummary("pkg-003", "agent-memory-kit", "pypi", "high_risk", 84, 70, 44),
  packageSummary("pkg-004", "llm-orchestration-base", "pypi", "registered", 79, 55, 68),
  packageSummary("pkg-005", "fast-json-sanitizer", "npm", "monitored", 72, 41, 91),
  packageSummary("pkg-006", "vector-context-tools", "pypi", "absent", 66, 23, 135),
  packageSummary("pkg-007", "py-tensor-toolkit", "pypi", "absent", 61, 18, 172),
  packageSummary("pkg-008", "prompt-schema", "npm", "monitored", 57, 27, 214),
  packageSummary("pkg-009", "secure-fetch-utils", "npm", "monitored", 49, 12, 288),
  packageSummary("pkg-010", "trusted-package", "npm", "registered", 22, 4, 360),
  packageSummary("pkg-011", "context-window-parser", "npm", "monitored", 54, 25, 402),
  packageSummary("pkg-012", "agent-route-core", "pypi", "absent", 58, 31, 438),
  packageSummary("pkg-013", "vector-store-lite", "npm", "monitored", 47, 19, 486),
  packageSummary("pkg-014", "model-cache-utils", "pypi", "registered", 69, 48, 524),
  packageSummary("pkg-015", "prompt-safety-kit", "npm", "monitored", 64, 37, 566),
  packageSummary("pkg-016", "embedding-pipeline", "pypi", "absent", 44, 16, 615),
  packageSummary("pkg-017", "json-agent-tools", "npm", "monitored", 52, 21, 662),
  packageSummary("pkg-018", "semantic-retry", "pypi", "registered", 73, 51, 708),
  packageSummary("pkg-019", "tool-call-router", "npm", "monitored", 56, 28, 752),
  packageSummary("pkg-020", "safe-output-parser", "npm", "registered", 42, 14, 804),
  packageSummary("pkg-021", "graph-memory-core", "pypi", "absent", 63, 35, 848),
  packageSummary("pkg-022", "async-model-client", "npm", "monitored", 39, 11, 896),
  packageSummary("pkg-023", "token-budget-tools", "pypi", "registered", 46, 20, 944),
  packageSummary("pkg-024", "schema-guard", "npm", "monitored", 68, 44, 996),
  packageSummary("pkg-025", "agent-trace-kit", "pypi", "absent", 51, 24, 1040),
  packageSummary("pkg-026", "retrieval-core-utils", "npm", "registered", 59, 33, 1106),
  packageSummary("pkg-027", "llm-response-cache", "pypi", "monitored", 43, 17, 1172),
  packageSummary("pkg-028", "guard-policy-types", "npm", "registered", 37, 9, 1240),
];

const absenceConfidence: Readonly<Record<string, number>> = {
  [TARGET_PACKAGE]: 100,
  "neural-optimizer-core": 91,
  "agent-memory-kit": 94,
  "llm-orchestration-base": 87,
  "fast-json-sanitizer": 82,
  "vector-context-tools": 96,
  "py-tensor-toolkit": 93,
  "prompt-schema": 79,
  "secure-fetch-utils": 74,
  "trusted-package": 8,
};

const evidenceByPackage: Readonly<Record<string, readonly EvidenceItem[]>> = {
  [TARGET_PACKAGE]: [
    evidence("ev-001", "registry", "npm 404 verified", "npm registry observation", 14400),
    evidence("ev-002", "recommendation", "Repeated AI recommendation", "verified model run", 12480),
    evidence("ev-003", "registration", "Package registration detected", "controlled registry", 18),
    evidence("ev-004", "enforcement", "Installation stopped before package manager", "SSS Guard", 7),
  ],
  "neural-optimizer-core": [
    evidence("ev-005", "recommendation", "Recurrence threshold reached", "verified model run", 2880),
    evidence("ev-006", "registration", "Package appeared in registry", "npm registry observation", 25),
  ],
  "agent-memory-kit": [
    evidence("ev-007", "registry", "PyPI absence verified", "PyPI registry observation", 8640),
    evidence("ev-008", "recommendation", "High-risk temporal pattern", "verified model run", 44),
  ],
  "llm-orchestration-base": [
    evidence("ev-009", "registry", "Registration transition observed", "PyPI registry observation", 68),
  ],
  "fast-json-sanitizer": [
    evidence("ev-010", "recommendation", "Recurrence observed", "verified model run", 91),
  ],
};

const decisions: readonly DecisionItem[] = [
  decision("dec-001", TARGET_PACKAGE, "npm", "block", "sss-hackathon-v3", 43, [
    "REGISTERED_AFTER_HALLUCINATION",
    "HIGH_GLOBAL_RECURRENCE",
  ], false, false),
  decision("dec-002", "neural-optimizer-core", "npm", "review", "TEMPORAL_PACKAGE_RISK_V1", 25, [
    "registration_transition_detected",
    "manual_review_required",
  ], false, false),
  decision("dec-003", "trusted-package", "npm", "allow", "TRUSTED_PACKAGE_V1", 61, [
    "registry_history_confirmed",
    "risk_below_threshold",
  ], true, true),
  decision("dec-004", "agent-memory-kit", "pypi", "review", "TEMPORAL_PACKAGE_RISK_V1", 144, [
    "historical_absence_confirmed",
    "recommendation_recurrence_detected",
  ], false, false),
  decision("dec-005", "fast-json-sanitizer", "npm", "allow", "MONITOR_ONLY_V1", 280, [
    "monitored_target",
    "no_registration_transition",
  ], true, false),
];

const initialDemoStatus: DemoStatus = {
  state: "ready",
  completedSteps: [],
  availableActions: ["replay-evidence"],
  targetPackage: TARGET_PACKAGE,
  unprotectedCanaryCount: 0,
  protectedCanaryCount: 0,
  packageManagerStarted: null,
  message: "Controlled scenario ready. No package code has been executed.",
  scores: { absenceConfidence: 100, targetAttractiveness: 95, packagePolicyRisk: 75 },
  policyVersion: "sss-hackathon-v3",
  registrationAgeMinutes: 43,
};

export class PrototypeControlRoomApi implements ControlRoomService {
  private demoStatus: DemoStatus = copyDemoStatus(initialDemoStatus);

  public async getHealth(signal?: AbortSignal) {
    return delayed({ status: "ok", service: "sss-prototype" }, signal);
  }

  public async getOverview(signal?: AbortSignal): Promise<OverviewData> {
    const activity: readonly ActivityItem[] = [
      activityItem("act-001", "blocked", "Installation stopped", TARGET_PACKAGE, 7),
      activityItem("act-002", "registered", "Package appeared in registry", "neural-optimizer-core", 25),
      activityItem("act-003", "monitored", "Recurrence observed", "fast-json-sanitizer", 91),
      activityItem("act-004", "high_risk", "Temporal risk threshold exceeded", "agent-memory-kit", 144),
    ];
    return delayed(
      {
        dataAsOf: new Date().toISOString(),
        guardStatus: "operational",
        activeThreats: packages.filter((item) => (item.policyRisk ?? 0) >= 60).length,
        protectedAgents: 8,
        verifiedRecommendations: 46,
        radarNodes: packages,
        prioritizedTargets: packages.filter((item) =>
          [TARGET_PACKAGE, "neural-optimizer-core", "fast-json-sanitizer"].includes(item.name),
        ),
        recentActivity: activity,
      },
      signal,
    );
  }

  public async getPackages(signal?: AbortSignal): Promise<readonly PackageSummary[]> {
    return delayed(packages, signal);
  }

  public async getPackage(name: string, signal?: AbortSignal): Promise<PackageDetail> {
    const item = packages.find((candidate) => candidate.name === name);
    if (!item) throw new Error(`No prototype package named ${name}`);
    return delayed(
      {
        ...item,
        absenceConfidence: absenceConfidence[name] ?? null,
        lifecycle: lifecycleFor(item),
      },
      signal,
    );
  }

  public async getEvidence(name: string, signal?: AbortSignal): Promise<readonly EvidenceItem[]> {
    return delayed(evidenceByPackage[name] ?? [], signal);
  }

  public async getDecisions(signal?: AbortSignal): Promise<readonly DecisionItem[]> {
    return delayed(decisions, signal);
  }

  public async getCoverage(signal?: AbortSignal): Promise<CoverageData> {
    return delayed(
      {
        dataAsOf: new Date().toISOString(),
        registries: [
          { id: "registry-npm", name: "npm", state: "operational", detail: "Registry feed connected" },
          { id: "registry-pypi", name: "PyPI", state: "operational", detail: "Registry feed connected" },
        ],
        services: [
          { id: "service-sync", name: "Registry feed sync", state: "operational", detail: "Last cycle completed" },
          { id: "service-ingestion", name: "Evidence ingestion", state: "operational", detail: "Accepting observations" },
          { id: "service-guard", name: "Guard Core", state: "operational", detail: "Policy loaded" },
          { id: "service-interception", name: "Package interception", state: "operational", detail: "Protected workspace active" },
        ],
        protectedAgents: 8,
        observationDays: 11,
        verifiedRecommendations: 46,
        publicFailedReferences: 5,
        modelConfigurations: 3,
      },
      signal,
    );
  }

  public async getDemoStatus(signal?: AbortSignal): Promise<DemoStatus> {
    return delayed(copyDemoStatus(this.demoStatus), signal);
  }

  public async runDemoAction(action: DemoAction, signal?: AbortSignal): Promise<DemoStatus> {
    if (!this.demoStatus.availableActions.includes(action)) {
      throw new Error("Complete the currently available demo step first");
    }
    if (action === "replay-evidence") {
      this.demoStatus = {
        state: "running",
        completedSteps: [action],
        availableActions: ["register-target"],
        targetPackage: TARGET_PACKAGE,
        unprotectedCanaryCount: 0,
        protectedCanaryCount: 0,
        packageManagerStarted: null,
        message: "Historical absence and recommendation evidence replayed.",
        scores: { absenceConfidence: 100, targetAttractiveness: 95, packagePolicyRisk: 75 },
        policyVersion: "sss-hackathon-v3",
        registrationAgeMinutes: 43,
      };
    } else if (action === "register-target") {
      this.demoStatus = {
        ...this.demoStatus,
        completedSteps: ["replay-evidence", action],
        availableActions: ["run-unprotected"],
        message: "Synthetic target registered in the controlled registry.",
      };
    } else if (action === "run-unprotected") {
      this.demoStatus = {
        ...this.demoStatus,
        completedSteps: ["replay-evidence", "register-target", action],
        availableActions: ["run-protected"],
        unprotectedCanaryCount: this.demoStatus.unprotectedCanaryCount + 1,
        packageManagerStarted: true,
        message: "Unprotected run reached the package manager and triggered the isolated canary.",
      };
    } else {
      this.demoStatus = {
        ...this.demoStatus,
        state: "blocked",
        completedSteps: ["replay-evidence", "register-target", "run-unprotected", action],
        availableActions: ["replay-evidence"],
        protectedCanaryCount: 0,
        packageManagerStarted: false,
        message: "SSS Guard blocked the request before the package manager or package code started.",
      };
    }
    return delayed(copyDemoStatus(this.demoStatus), signal, 260);
  }
}

function packageSummary(
  id: string,
  name: string,
  ecosystem: PackageSummary["ecosystem"],
  state: PackageSummary["state"],
  attractiveness: number,
  policyRisk: number,
  lastSeenMinutesAgo: number,
): PackageSummary {
  return { id, name, ecosystem, state, attractiveness, policyRisk, lastSeen: minutesAgo(lastSeenMinutesAgo) };
}

function evidence(id: string, type: string, label: string, provenance: string, minutes: number): EvidenceItem {
  return { id, type, label, provenance, occurredAt: minutesAgo(minutes) };
}

function decision(
  id: string,
  packageName: string,
  ecosystem: DecisionItem["ecosystem"],
  result: DecisionItem["result"],
  policy: string,
  minutes: number,
  reasonCodes: readonly string[],
  packageManagerStarted: boolean,
  packageCodeExecuted: boolean,
): DecisionItem {
  return {
    id,
    packageName,
    ecosystem,
    result,
    policy,
    occurredAt: minutesAgo(minutes),
    reasonCodes,
    packageManagerStarted,
    packageCodeExecuted,
  };
}

function activityItem(id: string, kind: string, label: string, packageName: string, minutes: number): ActivityItem {
  return { id, kind, label, packageName, occurredAt: minutesAgo(minutes) };
}

function lifecycleFor(item: PackageSummary): readonly string[] {
  const steps = ["Recommendation observed", "Public registry absence verified", "Recurrence monitored"];
  if (item.state === "registered" || item.state === "high_risk" || item.state === "blocked") {
    steps.push("Registry transition detected");
  }
  if (item.state === "high_risk" || item.state === "blocked") {
    steps.push("High-risk temporal pattern detected");
  }
  if (item.state === "blocked") steps.push("Installation blocked by Guard");
  return steps;
}

function copyDemoStatus(status: DemoStatus): DemoStatus {
  return {
    ...status,
    completedSteps: [...status.completedSteps],
    availableActions: [...status.availableActions],
  };
}

function minutesAgo(minutes: number): string {
  return new Date(Date.now() - minutes * 60_000).toISOString();
}

function delayed<T>(value: T, signal?: AbortSignal, duration = 140): Promise<T> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(signal.reason);
      return;
    }
    const timer = globalThis.setTimeout(() => {
      signal?.removeEventListener("abort", abort);
      resolve(value);
    }, duration);
    const abort = () => {
      globalThis.clearTimeout(timer);
      reject(signal?.reason ?? new DOMException("Request aborted", "AbortError"));
    };
    signal?.addEventListener("abort", abort, { once: true });
  });
}
