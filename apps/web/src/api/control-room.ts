import { ApiClient } from "./client";
import type {
  ActivityItem,
  CoverageData,
  CoverageService,
  DecisionItem,
  DecisionResult,
  DemoAction,
  DemoState,
  DemoStatus,
  Ecosystem,
  EvidenceItem,
  HealthData,
  OverviewData,
  PackageDetail,
  PackageState,
  PackageSummary,
  ServiceState,
} from "../domain/control-room";

export class ApiContractError extends Error {}

export interface ControlRoomService {
  getHealth(signal?: AbortSignal): Promise<HealthData>;
  getOverview(signal?: AbortSignal): Promise<OverviewData>;
  getPackages(signal?: AbortSignal): Promise<readonly PackageSummary[]>;
  getPackage(name: string, signal?: AbortSignal): Promise<PackageDetail>;
  getEvidence(name: string, signal?: AbortSignal): Promise<readonly EvidenceItem[]>;
  getDecisions(signal?: AbortSignal): Promise<readonly DecisionItem[]>;
  getCoverage(signal?: AbortSignal): Promise<CoverageData>;
  getDemoStatus(signal?: AbortSignal): Promise<DemoStatus>;
  runDemoAction(action: DemoAction, signal?: AbortSignal): Promise<DemoStatus>;
}

export class ControlRoomApi implements ControlRoomService {
  public constructor(private readonly client: ApiClient) {}

  public async getHealth(signal?: AbortSignal): Promise<HealthData> {
    return parseHealth(await this.client.request<unknown>("/health/live", withSignal(signal)));
  }

  public async getOverview(signal?: AbortSignal): Promise<OverviewData> {
    return parseOverview(await this.client.request<unknown>("/v1/overview", withSignal(signal)));
  }

  public async getPackages(signal?: AbortSignal): Promise<readonly PackageSummary[]> {
    return parseList(
      await this.client.request<unknown>("/v1/packages", withSignal(signal)),
      parsePackageSummary,
    );
  }

  public async getPackage(name: string, signal?: AbortSignal): Promise<PackageDetail> {
    const path = `/v1/packages/${encodeURIComponent(name)}`;
    return parsePackageDetail(await this.client.request<unknown>(path, withSignal(signal)));
  }

  public async getEvidence(name: string, signal?: AbortSignal): Promise<readonly EvidenceItem[]> {
    const path = `/v1/evidence/${encodeURIComponent(name)}`;
    return parseList(
      await this.client.request<unknown>(path, withSignal(signal)),
      parseEvidence,
    );
  }

  public async getDecisions(signal?: AbortSignal): Promise<readonly DecisionItem[]> {
    return parseList(
      await this.client.request<unknown>("/v1/decisions", withSignal(signal)),
      parseDecision,
    );
  }

  public async getCoverage(signal?: AbortSignal): Promise<CoverageData> {
    return parseCoverage(await this.client.request<unknown>("/v1/coverage", withSignal(signal)));
  }

  public async getDemoStatus(signal?: AbortSignal): Promise<DemoStatus> {
    return parseDemoStatus(await this.client.request<unknown>("/v1/demo", withSignal(signal)));
  }

  public async runDemoAction(action: DemoAction, signal?: AbortSignal): Promise<DemoStatus> {
    void action;
    void signal;
    throw new Error("Run the terminal-first demo from the operator shell");
  }
}

function withSignal(signal: AbortSignal | undefined): { signal?: AbortSignal } {
  return signal ? { signal } : {};
}

function parseHealth(value: unknown): HealthData {
  const object = record(value, "health response");
  return { status: string(object, "status"), service: string(object, "service") };
}

function parseOverview(value: unknown): OverviewData {
  const object = record(value, "overview response");
  return {
    dataAsOf: string(object, "data_as_of"),
    guardStatus: enumValue(object, "guard_status", SERVICE_STATES),
    activeThreats: number(object, "active_threats"),
    protectedAgents: number(object, "protected_agents"),
    verifiedRecommendations: number(object, "verified_recommendations"),
    radarNodes: array(object, "radar_nodes").map(parsePackageSummary),
    prioritizedTargets: array(object, "prioritized_targets").map(parsePackageSummary),
    recentActivity: array(object, "recent_activity").map(parseActivity),
  };
}

function parsePackageSummary(value: unknown): PackageSummary {
  const object = record(value, "package summary");
  return {
    id: string(object, "id"),
    name: string(object, "name"),
    ecosystem: enumValue(object, "ecosystem", ECOSYSTEMS),
    state: enumValue(object, "state", PACKAGE_STATES),
    attractiveness: number(object, "attractiveness"),
    policyRisk: nullableNumber(object, "policy_risk"),
    lastSeen: nullableString(object, "last_seen"),
  };
}

function parsePackageDetail(value: unknown): PackageDetail {
  const object = record(value, "package detail");
  return {
    ...parsePackageSummary(object),
    absenceConfidence: nullableNumber(object, "absence_confidence"),
    lifecycle: array(object, "lifecycle").map((item) => primitiveString(item, "lifecycle")),
  };
}

function parseActivity(value: unknown): ActivityItem {
  const object = record(value, "activity item");
  return {
    id: string(object, "id"),
    kind: string(object, "kind"),
    label: string(object, "label"),
    packageName: nullableString(object, "package_name"),
    occurredAt: string(object, "occurred_at"),
  };
}

function parseEvidence(value: unknown): EvidenceItem {
  const object = record(value, "evidence item");
  return {
    id: string(object, "id"),
    type: string(object, "type"),
    label: string(object, "label"),
    provenance: string(object, "provenance"),
    occurredAt: string(object, "occurred_at"),
  };
}

function parseDecision(value: unknown): DecisionItem {
  const object = record(value, "decision item");
  return {
    id: string(object, "id"),
    packageName: string(object, "package_name"),
    ecosystem: enumValue(object, "ecosystem", ECOSYSTEMS),
    result: enumValue(object, "result", DECISION_RESULTS),
    policy: string(object, "policy"),
    occurredAt: string(object, "occurred_at"),
    reasonCodes: array(object, "reason_codes").map((item) =>
      primitiveString(item, "reason code"),
    ),
    packageManagerStarted: boolean(object, "package_manager_started"),
    packageCodeExecuted: boolean(object, "package_code_executed"),
  };
}

function parseCoverage(value: unknown): CoverageData {
  const object = record(value, "coverage response");
  return {
    dataAsOf: string(object, "data_as_of"),
    registries: array(object, "registries").map(parseCoverageService),
    services: array(object, "services").map(parseCoverageService),
    protectedAgents: number(object, "protected_agents"),
    observationDays: number(object, "observation_days"),
    verifiedRecommendations: number(object, "verified_recommendations"),
    publicFailedReferences: number(object, "public_failed_references"),
    modelConfigurations: number(object, "model_configurations"),
  };
}

function parseCoverageService(value: unknown): CoverageService {
  const object = record(value, "coverage service");
  return {
    id: string(object, "id"),
    name: string(object, "name"),
    state: enumValue(object, "state", SERVICE_STATES),
    detail: nullableString(object, "detail"),
  };
}

function parseDemoStatus(value: unknown): DemoStatus {
  const object = record(value, "demo status");
  return {
    state: enumValue(object, "state", DEMO_STATES),
    completedSteps: array(object, "completed_steps").map((item) =>
      primitiveEnum(item, "completed step", DEMO_ACTIONS),
    ),
    availableActions: array(object, "available_actions").map((item) =>
      primitiveEnum(item, "available action", DEMO_ACTIONS),
    ),
    targetPackage: nullableString(object, "target_package"),
    unprotectedCanaryCount: number(object, "unprotected_canary_count"),
    protectedCanaryCount: number(object, "protected_canary_count"),
    packageManagerStarted: nullableBoolean(object, "package_manager_started"),
    message: nullableString(object, "message"),
    scores: {
      absenceConfidence: number(record(object.scores, "scores"), "absence_confidence"),
      targetAttractiveness: number(record(object.scores, "scores"), "target_attractiveness"),
      packagePolicyRisk: number(record(object.scores, "scores"), "package_policy_risk"),
    },
    policyVersion: string(object, "policy_version"),
    registrationAgeMinutes: number(object, "registration_age_minutes"),
  };
}

function parseList<T>(value: unknown, parser: (item: unknown) => T): readonly T[] {
  if (Array.isArray(value)) {
    return value.map(parser);
  }
  const object = record(value, "list response");
  return array(object, "items").map(parser);
}

function record(value: unknown, label: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new ApiContractError(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

function array(object: Record<string, unknown>, key: string): readonly unknown[] {
  const value = object[key];
  if (!Array.isArray(value)) {
    throw new ApiContractError(`${key} must be an array`);
  }
  return value;
}

function string(object: Record<string, unknown>, key: string): string {
  return primitiveString(object[key], key);
}

function primitiveString(value: unknown, label: string): string {
  if (typeof value !== "string" || !value.trim()) {
    throw new ApiContractError(`${label} must be a non-empty string`);
  }
  return value;
}

function number(object: Record<string, unknown>, key: string): number {
  const value = object[key];
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new ApiContractError(`${key} must be a finite number`);
  }
  return value;
}

function boolean(object: Record<string, unknown>, key: string): boolean {
  const value = object[key];
  if (typeof value !== "boolean") {
    throw new ApiContractError(`${key} must be a boolean`);
  }
  return value;
}

function nullableString(object: Record<string, unknown>, key: string): string | null {
  const value = object[key];
  return value === null ? null : primitiveString(value, key);
}

function nullableNumber(object: Record<string, unknown>, key: string): number | null {
  return object[key] === null ? null : number(object, key);
}

function nullableBoolean(object: Record<string, unknown>, key: string): boolean | null {
  return object[key] === null ? null : boolean(object, key);
}

function enumValue<const T extends string>(
  object: Record<string, unknown>,
  key: string,
  values: readonly T[],
): T {
  return primitiveEnum(object[key], key, values);
}

function primitiveEnum<const T extends string>(
  value: unknown,
  label: string,
  values: readonly T[],
): T {
  if (typeof value !== "string" || !values.includes(value as T)) {
    throw new ApiContractError(`${label} has an unsupported value`);
  }
  return value as T;
}

const ECOSYSTEMS: readonly Ecosystem[] = ["npm", "pypi"];
const PACKAGE_STATES: readonly PackageState[] = [
  "absent",
  "monitored",
  "registered",
  "high_risk",
  "blocked",
];
const DECISION_RESULTS: readonly DecisionResult[] = ["allow", "review", "block"];
const SERVICE_STATES: readonly ServiceState[] = ["operational", "degraded", "offline", "unknown"];
const DEMO_STATES: readonly DemoState[] = ["ready", "running", "blocked", "failed"];
const DEMO_ACTIONS: readonly DemoAction[] = [
  "replay-evidence",
  "register-target",
  "run-unprotected",
  "run-protected",
];
