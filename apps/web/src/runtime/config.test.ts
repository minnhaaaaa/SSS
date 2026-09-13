import { describe, expect, it } from "vitest";

import { RuntimeConfigurationError, loadRuntimeConfig } from "./config";

describe("loadRuntimeConfig", () => {
  it("uses supplied runtime values", () => {
    const config = loadRuntimeConfig(
      {
        VITE_SSS_API_BASE_URL: "https://api.example.test/",
        VITE_SSS_HTTP_TIMEOUT_MS: "2500",
      },
      "https://application.example.test",
    );

    expect(config.apiBaseUrl.toString()).toBe("https://api.example.test/");
    expect(config.httpTimeoutMs).toBe(2500);
  });

  it("rejects credentials in a browser-visible URL", () => {
    expect(() =>
      loadRuntimeConfig(
        { VITE_SSS_API_BASE_URL: "https://user:secret@api.example.test" },
        "https://application.example.test",
      ),
    ).toThrow(RuntimeConfigurationError);
  });

  it("rejects a base URL with a path", () => {
    expect(() =>
      loadRuntimeConfig(
        { VITE_SSS_API_BASE_URL: "https://api.example.test/unexpected" },
        "https://application.example.test",
      ),
    ).toThrow(RuntimeConfigurationError);
  });

});
