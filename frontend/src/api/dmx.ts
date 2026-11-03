import { api } from "@/api/client";
import type { DmxStatusPublic } from "@/api/types";

export const dmxApi = {
  status: () => api.get<DmxStatusPublic>("/dmx/status"),
};
