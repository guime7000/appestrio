import { api } from "@/api/client";
import type {
  DevicePublic,
  GroupCreate,
  GroupPublic,
  GroupUpdate,
  Paginated,
} from "@/api/types";

export const groupsApi = {
  list: (skip = 0, limit = 100) =>
    api.get<Paginated<GroupPublic>>(`/groups/?skip=${skip}&limit=${limit}`),
  get: (uuid: string) => api.get<GroupPublic>(`/groups/${uuid}`),
  create: (payload: GroupCreate) => api.post<GroupPublic>("/groups/", payload),
  update: (uuid: string, payload: GroupUpdate) =>
    api.patch<GroupPublic>(`/groups/${uuid}`, payload),
  delete: (uuids: string[]) => api.delete<{ message: string }>("/groups/", { uuids }),
  setDevices: (uuid: string, deviceUuids: string[]) =>
    api.patch<Paginated<DevicePublic>>(`/groups/${uuid}/devices`, {
      device_uuids: deviceUuids,
    }),
};
