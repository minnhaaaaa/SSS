import { describe, expect, it, vi } from "vitest";

import { ApiEventStream, EVENT_TYPES } from "./events";

describe("ApiEventStream", () => {
  it("subscribes to every fixed event type and closes the connection", () => {
    const listeners: string[] = [];
    const close = vi.fn();
    const source = {
      addEventListener: (type: string) => listeners.push(type),
      close,
      onerror: null,
    } as unknown as EventSource;
    const factory = vi.fn(() => source);
    const stream = new ApiEventStream(
      { apiBaseUrl: new URL("https://api.example.test"), httpTimeoutMs: 1000 },
      factory,
    );

    stream.connect({ onEvent: vi.fn(), onConnectionError: vi.fn() });
    stream.close();

    expect(listeners).toEqual(EVENT_TYPES);
    expect(factory).toHaveBeenCalledWith(new URL("https://api.example.test/v1/public/events"), {
      withCredentials: true,
    });
    expect(close).toHaveBeenCalledOnce();
  });

  it("closes the existing source before reconnecting", () => {
    const firstClose = vi.fn();
    const secondClose = vi.fn();
    const sources = [
      { addEventListener: vi.fn(), close: firstClose, onerror: null },
      { addEventListener: vi.fn(), close: secondClose, onerror: null },
    ] as unknown as EventSource[];
    const factory = vi.fn(() => {
      const source = sources.shift();
      if (!source) {
        throw new Error("unexpected connection");
      }
      return source;
    });
    const stream = new ApiEventStream(
      { apiBaseUrl: new URL("https://api.example.test"), httpTimeoutMs: 1000 },
      factory,
    );
    const handlers = { onEvent: vi.fn(), onConnectionError: vi.fn() };

    stream.connect(handlers);
    stream.connect(handlers);

    expect(firstClose).toHaveBeenCalledOnce();
    expect(secondClose).not.toHaveBeenCalled();
    expect(factory).toHaveBeenCalledTimes(2);
  });
});
