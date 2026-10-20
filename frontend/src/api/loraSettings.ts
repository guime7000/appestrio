import { api } from "@/api/client";

export const loraSettingsApi = {
  syncClocksNow: () => api.post<{ message: string }>("/lora-settings/sync-now", undefined),
};
