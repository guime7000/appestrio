import { api } from "@/api/client";
import type {
  IgnitionPresetCreate,
  IgnitionPresetPublic,
  IgnitionPresetUpdate,
  Paginated,
} from "@/api/types";

export const ignitionPresetsApi = {
  list: (skip = 0, limit = 100) =>
    api.get<Paginated<IgnitionPresetPublic>>(
      `/ignition-presets/?skip=${skip}&limit=${limit}`,
    ),
  get: (uuid: string) => api.get<IgnitionPresetPublic>(`/ignition-presets/${uuid}`),
  create: (payload: IgnitionPresetCreate) =>
    api.post<IgnitionPresetPublic>("/ignition-presets/", payload),
  update: (uuid: string, payload: IgnitionPresetUpdate) =>
    api.patch<IgnitionPresetPublic>(`/ignition-presets/${uuid}`, payload),
  delete: (uuids: string[]) =>
    api.delete<{ message: string }>("/ignition-presets/", { uuids }),
};
