// Mirrors backend/app/models/*.py *Public / *Create / *Update schemas.

// ISO weekday numbers: 1=Monday .. 7=Sunday.
export type Weekday = 1 | 2 | 3 | 4 | 5 | 6 | 7;

export interface IgnitionPresetPublic {
  uuid: string;
  calendar_id: string;
  name: string;
  description: string | null;
  start_date: string;
  stop_date: string;
  start_time: string;
  stop_time: string;
  created_at: string;
  updated_at: string;
}

export interface IgnitionPresetCreate {
  calendar_id: string;
  name: string;
  description?: string | null;
  start_date: string;
  stop_date: string;
  start_time: string;
  stop_time: string;
}

export interface IgnitionPresetUpdate {
  calendar_id?: string;
  name?: string;
  description?: string | null;
  start_date?: string;
  stop_date?: string;
  start_time?: string;
  stop_time?: string;
}

export interface CalendarPublic {
  uuid: string;
  label: string;
  weekdays: Weekday[];
  updated_at: string;
  ignition_presets: IgnitionPresetPublic[];
}

// GET /calendars/ only exposes this trimmed-down shape; the full
// CalendarPublic (weekdays + ignition_presets) is only returned by the
// per-calendar detail endpoint.
export interface CalendarSummaryPublic {
  uuid: string;
  label: string;
  updated_at: string;
}

export interface CalendarCreate {
  label: string;
  weekdays?: Weekday[];
}

export interface CalendarUpdate {
  label?: string;
  weekdays?: Weekday[];
}

export interface GroupDevicePublic {
  uuid: string;
  device_id: string;
  device_name: string;
  active: boolean;
  handles_audio: boolean;
  handles_dmx: boolean;
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

export type DeviceType = "lumestrio" | "relaystrio";

export interface DevicePublic {
  uuid: string;
  device_id: string;
  device_name: string;
  device_type: DeviceType;
  active: boolean;
  is_master: boolean;
  handles_audio: boolean;
  handles_dmx: boolean;
  group: string | null;
  group_id: string | null;
  calendar: CalendarPublic | null;
  audiofile: string | null;
  ip: string | null;
  master_ip: string | null;
  updated_at: string;
}

export interface DeviceCreate {
  device_id: string;
  device_name: string;
  device_type: DeviceType;
  active?: boolean;
  is_master?: boolean;
  handles_audio?: boolean;
  handles_dmx?: boolean;
  audiofile?: string | null;
  ip?: string | null;
  master_ip?: string | null;
  group_id?: string | null;
}

export interface DeviceUpdate {
  device_id?: string;
  device_name?: string;
  device_type?: DeviceType;
  active?: boolean;
  is_master?: boolean;
  handles_audio?: boolean;
  handles_dmx?: boolean;
  audiofile?: string | null;
  ip?: string | null;
  master_ip?: string | null;
  group_id?: string | null;
}

export interface Paginated<T> {
  data: T[];
  count: number;
}
