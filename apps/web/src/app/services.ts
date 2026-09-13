import { ApiClient } from "../api/client";
import { ControlRoomApi, type ControlRoomService } from "../api/control-room";
import { ApiEventStream, type EventStreamService } from "../api/events";
import { loadRuntimeConfig } from "../runtime/config";

export const runtimeConfig = loadRuntimeConfig(import.meta.env, window.location.origin);
export const api: ControlRoomService = new ControlRoomApi(new ApiClient(runtimeConfig));
export const eventStream: EventStreamService = new ApiEventStream(runtimeConfig);
