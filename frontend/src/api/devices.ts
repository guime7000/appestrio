import { api } from "@/api/client";
import type {
  DeviceCreate,
  DevicePublic,
  DeviceUpdate,
  FreeDeviceNumbers,
  Paginated,
  PendingSyncStatus,
} from "@/api/types";

export const devicesApi = {
  list: (skip = 0, limit = 100) =>
    api.get<Paginated<DevicePublic>>(`/devices/?skip=${skip}&limit=${limit}`),
  get: (deviceId: string) => api.get<DevicePublic>(`/devices/${deviceId}`),
  create: (payload: DeviceCreate) => api.post<DevicePublic>("/devices/", payload),
  update: (deviceId: string, payload: DeviceUpdate) =>
    api.patch<DevicePublic>(`/devices/${deviceId}`, payload),
  delete: (deviceIds: string[]) =>
    api.delete<{ message: string }>("/devices/", { device_ids: deviceIds }),
  freeDeviceNumbers: () => api.get<FreeDeviceNumbers>("/devices/free_devices_id"),
  pendingSync: () => api.get<PendingSyncStatus>("/devices/pending-sync"),
};
