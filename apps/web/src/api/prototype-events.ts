import type { EventHandlers, EventStreamService } from "./events";

export class PrototypeEventStream implements EventStreamService {
  private connectionRevision = 0;

  public connect(handlers: EventHandlers): void {
    const revision = ++this.connectionRevision;
    queueMicrotask(() => {
      if (revision === this.connectionRevision) handlers.onConnectionOpen?.();
    });
  }

  public close(): void {
    this.connectionRevision += 1;
  }
}
