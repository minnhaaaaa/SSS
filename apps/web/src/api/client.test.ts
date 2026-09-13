import { describe, expect, it, vi } from "vitest";

import { ApiClient, ApiError } from "./client";

const config = {
  apiBaseUrl: new URL("https://api.example.test"),
  httpTimeoutMs: 1000,
};

describe("ApiClient", () => {
  it("uses the browser fetch function without an invalid receiver", async () => {
    const nativeFetch = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(jsonResponse({ accepted: true }));
    const client = new ApiClient(config);

    try {
      await expect(client.request("/v1/example")).resolves.toEqual({ accepted: true });
      expect(nativeFetch).toHaveBeenCalledOnce();
    } finally {
      nativeFetch.mockRestore();
    }
  });

  it("sends JSON writes with credentials and an idempotency key", async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ accepted: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = new ApiClient(config, fetchImplementation);

    await expect(
      client.request<{ accepted: boolean }>("/v1/example", {
        method: "POST",
        body: { value: 1 },
        idempotencyKey: "request-key",
      }),
    ).resolves.toEqual({ accepted: true });

    const request = fetchImplementation.mock.calls[0];
    expect(request?.[0].toString()).toBe("https://api.example.test/v1/example");
    expect(request?.[1]?.credentials).toBe("include");
    expect(new Headers(request?.[1]?.headers).get("Idempotency-Key")).toBe("request-key");
  });

  it("preserves status and request ID on API errors", async () => {
    const fetchImplementation = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ detail: "blocked" }), {
        status: 403,
        headers: {
          "Content-Type": "application/json",
          "X-Request-ID": "request-id",
        },
      }),
    );
    const client = new ApiClient(config, fetchImplementation);

    const result = client.request("/v1/example");

    await expect(result).rejects.toMatchObject({
      message: "blocked",
      status: 403,
      requestId: "request-id",
    } satisfies Partial<ApiError>);
  });

  it("rejects absolute and protocol-relative request paths", async () => {
    const client = new ApiClient(config, vi.fn<typeof fetch>());

    await expect(client.request("https://attacker.example/path")).rejects.toThrow(TypeError);
    await expect(client.request("//attacker.example/path")).rejects.toThrow(TypeError);
  });

  it("aborts requests after the configured timeout", async () => {
    vi.useFakeTimers();
    const fetchImplementation = vi.fn<typeof fetch>((_input, init) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason));
      });
    });
    const client = new ApiClient(
      { apiBaseUrl: config.apiBaseUrl, httpTimeoutMs: 25 },
      fetchImplementation,
    );

    try {
      const request = client.request("/v1/slow");
      const assertion = expect(request).rejects.toThrow("SSS API request timed out");
      await vi.advanceTimersByTimeAsync(25);

      await assertion;
    } finally {
      vi.useRealTimers();
    }
  });

  it("honors a caller-provided abort signal", async () => {
    const fetchImplementation = vi.fn<typeof fetch>((_input, init) => {
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => reject(init.signal?.reason));
      });
    });
    const client = new ApiClient(config, fetchImplementation);
    const controller = new AbortController();

    const request = client.request("/v1/cancelled", { signal: controller.signal });
    controller.abort(new Error("cancelled by caller"));

    await expect(request).rejects.toThrow("cancelled by caller");
  });
});

function jsonResponse(body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}
