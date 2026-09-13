export type Ecosystem = "npm" | "pypi";
export type PackageState = "absent" | "monitored" | "registered" | "high_risk" | "blocked";
export type DecisionResult = "allow" | "review" | "block";
export type ServiceState = "operational" | "degraded" | "offline" | "unknown";

export interface PackageSummary {
  readonly id: string;
  readonly name: string;
  readonly ecosystem: Ecosystem;
  readonly state: PackageState;
  readonly attractiveness: number;
  readonly policyRisk: number | null;
  readonly lastSeen: string | null;
}

export interface ActivityItem {
  readonly id: string;
  readonly kind: string;
  readonly label: string;
  readonly packageName: string | null;
  readonly occurredAt: string;
}

export interface OverviewData {
  readonly dataAsOf: string;
  readonly guardStatus: ServiceState;
  readonly activeThreats: number;
  readonly protectedAgents: number;
  readonly verifiedRecommendations: number;
  readonly radarNodes: readonly PackageSummary[];
  readonly prioritizedTargets: readonly PackageSummary[];
  readonly recentActivity: readonly ActivityItem[];
}

export interface EvidenceItem {
  readonly id: string;
  readonly type: string;
  readonly label: string;
  readonly provenance: string;
  readonly occurredAt: string;
}

export interface PackageDetail extends PackageSummary {
  readonly absenceConfidence: number | null;
  readonly lifecycle: readonly string[];
}

export interface DecisionItem {
  readonly id: string;
  readonly packageName: string;
  readonly ecosystem: Ecosystem;
  readonly result: DecisionResult;
  readonly policy: string;
  readonly occurredAt: string;
  readonly reasonCodes: readonly string[];
  readonly packageManagerStarted: boolean;
  readonly packageCodeExecuted: boolean;
}

export interface CoverageService {
  readonly id: string;
  readonly name: string;
  readonly state: ServiceState;
  readonly detail: string | null;
}

export interface CoverageData {
  readonly dataAsOf: string;
  readonly registries: readonly CoverageService[];
  readonly services: readonly CoverageService[];
  readonly protectedAgents: number;
  readonly observationDays: number;
  readonly verifiedRecommendations: number;
  readonly publicFailedReferences: number;
  readonly modelConfigurations: number;
}

export type DemoState = "ready" | "running" | "blocked" | "failed";
export type DemoAction =
  | "replay-evidence"
  | "register-target"
  | "run-unprotected"
  | "run-protected";

export interface DemoStatus {
  readonly state: DemoState;
  readonly completedSteps: readonly DemoAction[];
  readonly availableActions: readonly DemoAction[];
  readonly targetPackage: string | null;
  readonly unprotectedCanaryCount: number;
  readonly protectedCanaryCount: number;
  readonly packageManagerStarted: boolean | null;
  readonly message: string | null;
  readonly scores: {
    readonly absenceConfidence: number;
    readonly targetAttractiveness: number;
    readonly packagePolicyRisk: number;
  };
  readonly policyVersion: string;
  readonly registrationAgeMinutes: number;
}

export interface HealthData {
  readonly status: string;
  readonly service: string;
}
