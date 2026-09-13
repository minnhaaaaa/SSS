export type RuntimeValues = Readonly<Record<string, string | undefined>>;

export interface RuntimeConfig {
  readonly apiBaseUrl: URL;
  readonly httpTimeoutMs: number;
}

export class RuntimeConfigurationError extends Error {}

export function loadRuntimeConfig(values: RuntimeValues, applicationOrigin: string): RuntimeConfig {
  const configuredBase = values.VITE_SSS_API_BASE_URL?.trim();
  const apiBaseUrl = new URL(configuredBase || applicationOrigin);
  if (!isHttpProtocol(apiBaseUrl.protocol)) {
    throw new RuntimeConfigurationError("VITE_SSS_API_BASE_URL must use HTTP or HTTPS");
  }
  if (apiBaseUrl.username || apiBaseUrl.password || apiBaseUrl.hash) {
    throw new RuntimeConfigurationError(
      "VITE_SSS_API_BASE_URL cannot contain credentials or a fragment",
    );
  }
  if (apiBaseUrl.pathname !== "/" || apiBaseUrl.search) {
    throw new RuntimeConfigurationError(
      "VITE_SSS_API_BASE_URL must be an origin without a path or query",
    );
  }

  const rawTimeout = values.VITE_SSS_HTTP_TIMEOUT_MS?.trim() || "5000";
  const httpTimeoutMs = Number(rawTimeout);
  if (!Number.isSafeInteger(httpTimeoutMs) || httpTimeoutMs <= 0) {
    throw new RuntimeConfigurationError("VITE_SSS_HTTP_TIMEOUT_MS must be a positive integer");
  }

  return {
    apiBaseUrl: new URL(apiBaseUrl.toString().replace(/\/$/, "")),
    httpTimeoutMs,
  };
}

function isHttpProtocol(protocol: string): boolean {
  return protocol === "http:" || protocol === "https:";
}
