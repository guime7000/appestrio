import { api } from "@/api/client";

export const whoamiApi = {
  get: () => api.get<{ is_master: boolean }>("/whoami"),
};
