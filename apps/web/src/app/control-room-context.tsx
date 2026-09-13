import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import type { EventType } from "../api/events";
import { api, dataMode, eventStream } from "./services";

type ApiConnection = "checking" | "online" | "offline";
type LiveConnection = "connecting" | "live" | "offline";

interface ControlRoomContextValue {
  readonly apiConnection: ApiConnection;
  readonly liveConnection: LiveConnection;
  readonly serviceName: string | null;
  readonly lastEventType: EventType | null;
  readonly liveRevision: number;
  readonly dataMode: "live" | "prototype";
  readonly selectedPackage: string | null;
  readonly openPackage: (packageName: string) => void;
  readonly closePackage: () => void;
  readonly retryConnections: () => void;
}

const ControlRoomContext = createContext<ControlRoomContextValue | null>(null);

export function ControlRoomProvider({ children }: { readonly children: ReactNode }) {
  const [apiConnection, setApiConnection] = useState<ApiConnection>("checking");
  const [liveConnection, setLiveConnection] = useState<LiveConnection>("connecting");
  const [serviceName, setServiceName] = useState<string | null>(null);
  const [lastEventType, setLastEventType] = useState<EventType | null>(null);
  const [liveRevision, setLiveRevision] = useState(0);
  const [selectedPackage, setSelectedPackage] = useState<string | null>(null);
  const [connectionRevision, setConnectionRevision] = useState(0);

  const retryConnections = useCallback(() => setConnectionRevision((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setApiConnection("checking");
    void api
      .getHealth(controller.signal)
      .then((health) => {
        setServiceName(health.service);
        setApiConnection(health.status === "ok" ? "online" : "offline");
      })
      .catch(() => {
        if (!controller.signal.aborted) {
          setApiConnection("offline");
        }
      });
    return () => controller.abort();
  }, [connectionRevision]);

  useEffect(() => {
    setLiveConnection("connecting");
    eventStream.connect({
      onConnectionOpen: () => setLiveConnection("live"),
      onEvent: (eventType) => {
        setLiveConnection("live");
        setLastEventType(eventType);
        setLiveRevision((value) => value + 1);
      },
      onConnectionError: () => setLiveConnection("offline"),
    });
    return () => eventStream.close();
  }, [connectionRevision]);

  const value = useMemo<ControlRoomContextValue>(
    () => ({
      apiConnection,
      liveConnection,
      serviceName,
      lastEventType,
      liveRevision,
      dataMode,
      selectedPackage,
      openPackage: setSelectedPackage,
      closePackage: () => setSelectedPackage(null),
      retryConnections,
    }),
    [apiConnection, liveConnection, serviceName, lastEventType, liveRevision, selectedPackage, retryConnections],
  );

  return <ControlRoomContext.Provider value={value}>{children}</ControlRoomContext.Provider>;
}

export function useControlRoom(): ControlRoomContextValue {
  const value = useContext(ControlRoomContext);
  if (value === null) {
    throw new Error("useControlRoom must be used inside ControlRoomProvider");
  }
  return value;
}
