import type { RuntimeConfig } from "../runtime/config";

export const EVENT_TYPES = [
  "observation.completed",
  "registration.transition",
  "install.blocked",
  "approval.consumed",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];
export type EventSourceFactory = (url: string | URL, init: EventSourceInit) => EventSource;

export interface EventHandlers {
  readonly onEvent: (eventType: EventType, event: MessageEvent<string>) => void;
  readonly onConnectionOpen?: () => void;
  readonly onConnectionError: (event: Event) => void;
}

export interface EventStreamService {
  connect(handlers: EventHandlers): void;
  close(): void;
}

export class ApiEventStream implements EventStreamService {
  private source: EventSource | null = null;

  public constructor(
    private readonly config: Pick<RuntimeConfig, "apiBaseUrl" | "httpTimeoutMs">,
    private readonly factory: EventSourceFactory = (url, init) => new EventSource(url, init),
  ) {}

  public connect(handlers: EventHandlers): void {
    this.close();
    const url = new URL("/v1/events", this.config.apiBaseUrl);
    const source = this.factory(url, { withCredentials: true });
    for (const eventType of EVENT_TYPES) {
      source.addEventListener(eventType, (event) => {
        handlers.onEvent(eventType, event as MessageEvent<string>);
      });
    }
    source.onopen = handlers.onConnectionOpen ?? null;
    source.onerror = handlers.onConnectionError;
    this.source = source;
  }

  public close(): void {
    this.source?.close();
    this.source = null;
  }
}
