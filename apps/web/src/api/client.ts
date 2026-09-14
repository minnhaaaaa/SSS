import type { RuntimeConfig } from "../runtime/config";

export type FetchImplementation = typeof fetch;

export interface RequestOptions {
  readonly method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  readonly body?: unknown;
  readonly idempotencyKey?: string;
  readonly signal?: AbortSignal;
}

export class ApiError extends Error {
  public constructor(
    message: string,
    public readonly status: number,
    public readonly requestId: string | null,
  ) {
    super(message);
  }
}

export class ApiClient {
  public constructor(
    private readonly config: Pick<RuntimeConfig, "apiBaseUrl" | "httpTimeoutMs">,
    private readonly fetchImplementation: FetchImplementation = (input, init) => fetch(input, init),
  ) {}

  public async request<ResponseBody>(
    path: string,
    options: RequestOptions = {},
  ): Promise<ResponseBody> {
    const url = resolveApiPath(this.config.apiBaseUrl, path);
    const timeoutController = new AbortController();
    const timeout = globalThis.setTimeout(
      () => timeoutController.abort(new Error("SSS API request timed out")),
      this.config.httpTimeoutMs,
    );
    const signal = combineSignals(timeoutController.signal, options.signal);
    const headers = new Headers({ Accept: "application/json" });
    if (options.body !== undefined) {
      headers.set("Content-Type", "application/json");
    }
    if (options.idempotencyKey) {
      headers.set("Idempotency-Key", options.idempotencyKey);
    }
    const requestInit: RequestInit = {
      method: options.method ?? "GET",
      headers,
      credentials: "include",
      signal,
    };
    if (options.body !== undefined) {
      requestInit.body = JSON.stringify(options.body);
    }

    try {
      const response = await this.fetchImplementation(url, requestInit);
      if (!response.ok) {
        throw new ApiError(
          await readErrorMessage(response),
          response.status,
          response.headers.get("X-Request-ID"),
        );
      }
      if (response.status === 204) {
        return undefined as ResponseBody;
      }
      return (await response.json()) as ResponseBody;
    } finally {
      globalThis.clearTimeout(timeout);
    }
  }
}

function resolveApiPath(baseUrl: URL, path: string): URL {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new TypeError("API path must be a single-root relative path");
  }
  return new URL(path, `${baseUrl.toString()}/`);
}

function combineSignals(primary: AbortSignal, secondary: AbortSignal | undefined): AbortSignal {
  return secondary ? AbortSignal.any([primary, secondary]) : primary;
}

async function readErrorMessage(response: Response): Promise<string> {
  const contentType = response.headers.get("Content-Type") ?? "";
  if (contentType.includes("application/json")) {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  }
  return `SSS API request failed with HTTP ${response.status}`;
}
