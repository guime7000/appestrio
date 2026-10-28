import { api } from "@/api/client";
import type { LoraSettingsPublic, LoraSettingsUpdate } from "@/api/types";

export const loraSettingsApi = {
  get: () => api.get<LoraSettingsPublic>("/lora-settings/"),
  update: (payload: LoraSettingsUpdate) =>
    api.patch<LoraSettingsPublic>("/lora-settings/", payload),
  syncClocksNow: () => api.post<{ message: string }>("/lora-settings/sync-now", undefined),
};
