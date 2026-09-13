import { ApiClient } from "../api/client";
import { ControlRoomApi, type ControlRoomService } from "../api/control-room";
import { ApiEventStream, type EventStreamService } from "../api/events";
import { PrototypeControlRoomApi } from "../api/prototype-control-room";
import { PrototypeEventStream } from "../api/prototype-events";
import { loadRuntimeConfig } from "../runtime/config";

export const runtimeConfig = loadRuntimeConfig(import.meta.env, window.location.origin);
export const dataMode = runtimeConfig.prototypeDataEnabled ? "prototype" : "live";
export const api: ControlRoomService = runtimeConfig.prototypeDataEnabled
  ? new PrototypeControlRoomApi()
  : new ControlRoomApi(new ApiClient(runtimeConfig));
export const eventStream: EventStreamService = runtimeConfig.prototypeDataEnabled
  ? new PrototypeEventStream()
  : new ApiEventStream(runtimeConfig);
