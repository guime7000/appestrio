import { api } from "@/api/client";
import type {
  CalendarCreate,
  CalendarPublic,
  CalendarUpdate,
  Paginated,
} from "@/api/types";

export const calendarsApi = {
  list: (skip = 0, limit = 100) =>
    api.get<Paginated<CalendarPublic>>(`/calendars/?skip=${skip}&limit=${limit}`),
  get: (uuid: string) => api.get<CalendarPublic>(`/calendars/${uuid}`),
  create: (payload: CalendarCreate) => api.post<CalendarPublic>("/calendars/", payload),
  update: (uuid: string, payload: CalendarUpdate) =>
    api.patch<CalendarPublic>(`/calendars/${uuid}`, payload),
  duplicate: (uuid: string) =>
    api.post<CalendarPublic>(`/calendars/${uuid}/duplicate`, undefined),
  delete: (uuids: string[]) =>
    api.delete<{ message: string }>("/calendars/", { uuids }),
};
