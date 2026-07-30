import { api } from "@/api/client";
import type { DeviceCreate, DevicePublic, DeviceUpdate, Paginated } from "@/api/types";

export const devicesApi = {
  list: (skip = 0, limit = 100) =>
    api.get<Paginated<DevicePublic>>(`/devices/?skip=${skip}&limit=${limit}`),
  get: (uuid: string) => api.get<DevicePublic>(`/devices/${uuid}`),
  create: (payload: DeviceCreate) => api.post<DevicePublic>("/devices/", payload),
  update: (uuid: string, payload: DeviceUpdate) =>
    api.patch<DevicePublic>(`/devices/${uuid}`, payload),
  delete: (uuids: string[]) => api.delete<{ message: string }>("/devices/", { uuids }),
};
