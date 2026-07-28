// Mirrors backend/app/models.py *Public / *Create / *Update schemas.

export interface CalendarPublic {
  uuid: string;
  label: string;
  presets: Record<string, unknown>;
  days: Record<string, unknown>;
  updated_at: string;
}

export interface CalendarCreate {
  label: string;
  presets?: Record<string, unknown>;
  days?: Record<string, unknown>;
}

export interface CalendarUpdate {
  label?: string;
  presets?: Record<string, unknown>;
  days?: Record<string, unknown>;
}

export interface GroupDevicePublic {
  uuid: string;
  device_id: string;
  device_name: string;
  active: boolean;
}

export interface GroupPublic {
  uuid: string;
  label: string;
  calendar_id: string | null;
  updated_at: string;
  devices: GroupDevicePublic[];
}

export interface GroupCreate {
  label: string;
  calendar_id?: string | null;
}

export interface GroupUpdate {
  label?: string;
  calendar_id?: string | null;
}

export interface DevicePublic {
  uuid: string;
  device_id: string;
  device_name: string;
  active: boolean;
  group: string | null;
  calendar: CalendarPublic | null;
  audiofile: string | null;
  ip: string | null;
  master_ip: string | null;
  updated_at: string;
}

export interface DeviceCreate {
  device_id: string;
  device_name: string;
  active?: boolean;
  audiofile?: string | null;
  ip?: string | null;
  master_ip?: string | null;
  group_id?: string | null;
}

export interface DeviceUpdate {
  device_id?: string;
  device_name?: string;
  active?: boolean;
  audiofile?: string | null;
  ip?: string | null;
  master_ip?: string | null;
  group_id?: string | null;
}

export interface Paginated<T> {
  data: T[];
  count: number;
}
