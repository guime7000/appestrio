<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, watch } from "vue";

import CalendarDetailModal from "@/components/CalendarDetailModal.vue";
import GroupDetailModal from "@/components/GroupDetailModal.vue";
import PendingSyncBanner from "@/components/PendingSyncBanner.vue";
import { devicesApi } from "@/api/devices";
import { groupsApi } from "@/api/groups";
import { loraSettingsApi } from "@/api/loraSettings";
import type {
  CalendarPublic,
  DevicePublic,
  DeviceType,
  FreeDeviceNumbers,
  GroupPublic,
} from "@/api/types";

const deviceTypes: DeviceType[] = ["lumestrio", "relaystrio"];
// Tolerates a couple of missed PING cycles before flagging a device
// unreachable, rather than flickering offline on one dropped PONG --
// same "don't overreact to a single miss" spirit `sync_device_config`'s
// own retry-next-cycle behavior already follows. Falls back to a 5s
// interval (the backend's own default) if `/lora-settings/` hasn't
// loaded yet.
const REACHABLE_MISSED_CYCLES = 3;
const DEFAULT_PING_INTERVAL_S = 5;
// Live status board: devices (incl. last_seen) and the pending-sync
// banner refresh on their own, without the user needing to do anything.
const REFRESH_INTERVAL_MS = 5000;

const devices = ref<DevicePublic[]>([]);
const groups = ref<GroupPublic[]>([]);
const selectedDeviceIds = ref<Set<string>>(new Set());
const pendingSyncCount = ref(0);
const pendingSyncDeviceIds = ref<string[]>([]);
const pingIntervalS = ref(DEFAULT_PING_INTERVAL_S);
// Ticks once a second purely to force "il y a Xs"/reachability to
// re-render as time passes, without needing a fresh fetch each time.
const now = ref(Date.now());

const detailModalOpen = ref(false);
const detailDevice = ref<DevicePublic | null>(null);

const groupDetailModalOpen = ref(false);
const groupDetail = ref<GroupPublic | null>(null);
// The group's calendar is already available on the device that linked to it
// (device.calendar === device.group.calendar on the backend), so opening the
// group modal from a device row needs no extra fetch for this.
const groupDetailCalendar = ref<CalendarPublic | null>(null);

const calendarDetailModalOpen = ref(false);
const calendarDetail = ref<CalendarPublic | null>(null);

const formModalOpen = ref(false);
const formError = ref<string | null>(null);
const editingDeviceId = ref<string | null>(null);
const freeDeviceNumbers = ref<FreeDeviceNumbers>({ relaystrio: [], lumestrio: [] });
const deviceForm = reactive({
  device_id: "",
  device_number: null as number | null,
  device_name: "",
  device_type: "lumestrio" as DeviceType,
  active: true,
  is_master: false,
  handles_audio: false,
  handles_dmx: false,
  ip: "",
  master_ip: "",
  audiofile: "",
  group_id: "",
});

const availableDeviceNumbers = computed(() => freeDeviceNumbers.value[deviceForm.device_type]);

const allSelected = computed(
  () => devices.value.length > 0 && selectedDeviceIds.value.size === devices.value.length,
);

const existingMaster = computed(
  () => devices.value.find((d) => d.is_master && d.device_id !== editingDeviceId.value) ?? null,
);

function resetDeviceNumberToFirstAvailable() {
  deviceForm.device_number = availableDeviceNumbers.value[0] ?? null;
}

// The free-number pool differs per type, so switching type while creating a
// device must re-pick a number valid for the newly selected type.
watch(
  () => deviceForm.device_type,
  () => {
    if (!editingDeviceId.value) {
      resetDeviceNumberToFirstAvailable();
    }
  },
);

// The master device can never be in a group (guard requested
// 2026-11-04, also enforced backend-side so a direct API call can't
// bypass it) -- clearing the selection the moment "Maître" is checked
// keeps the form from ever submitting a combination the backend would
// reject anyway.
watch(
  () => deviceForm.is_master,
  (isMaster) => {
    if (isMaster) {
      deviceForm.group_id = "";
    }
  },
);

async function loadPingInterval() {
  try {
    const settings = await loraSettingsApi.get();
    pingIntervalS.value = settings.ping_interval_s;
  } catch {
    // Keep the default -- not critical enough to surface an error for.
  }
}

function isReachable(device: DevicePublic): boolean {
  if (!device.last_seen) return false;
  const lastSeenMs = new Date(device.last_seen).getTime();
  const thresholdMs = Math.max(pingIntervalS.value, 1) * REACHABLE_MISSED_CYCLES * 1000;
  return now.value - lastSeenMs <= thresholdMs;
}

function lastSeenLabel(device: DevicePublic): string {
  if (!device.last_seen) return "Jamais vu";
  const diffS = Math.max(0, Math.round((now.value - new Date(device.last_seen).getTime()) / 1000));
  if (diffS < 60) return `il y a ${diffS} s`;
  const diffMin = Math.round(diffS / 60);
  if (diffMin < 60) return `il y a ${diffMin} min`;
  const diffH = Math.round(diffMin / 60);
  return `il y a ${diffH} h`;
}

async function loadDevices() {
  const [devicesResult, groupsResult, pendingSyncResult] = await Promise.all([
    devicesApi.list(),
    groupsApi.list(),
    devicesApi.pendingSync(),
  ]);
  devices.value = devicesResult.data;
  groups.value = groupsResult.data;
  pendingSyncCount.value = pendingSyncResult.count;
  pendingSyncDeviceIds.value = pendingSyncResult.device_ids;
  selectedDeviceIds.value = new Set(
    [...selectedDeviceIds.value].filter((id) => devices.value.some((d) => d.device_id === id)),
  );
}

async function openCreateModal() {
  formError.value = null;
  editingDeviceId.value = null;
  deviceForm.device_id = "";
  deviceForm.device_name = "";
  deviceForm.device_type = "lumestrio";
  deviceForm.active = true;
  deviceForm.is_master = false;
  deviceForm.handles_audio = false;
  deviceForm.handles_dmx = false;
  deviceForm.ip = "";
  deviceForm.master_ip = "";
  deviceForm.audiofile = "";
  deviceForm.group_id = "";
  freeDeviceNumbers.value = await devicesApi.freeDeviceNumbers();
  resetDeviceNumberToFirstAvailable();
  formModalOpen.value = true;
}

function openEditModal(device: DevicePublic) {
  formError.value = null;
  editingDeviceId.value = device.device_id;
  deviceForm.device_id = device.device_id;
  deviceForm.device_name = device.device_name;
  deviceForm.device_type = device.device_type;
  deviceForm.active = device.active;
  deviceForm.is_master = device.is_master;
  deviceForm.handles_audio = device.handles_audio;
  deviceForm.handles_dmx = device.handles_dmx;
  deviceForm.ip = device.ip ?? "";
  deviceForm.master_ip = device.master_ip ?? "";
  deviceForm.audiofile = device.audiofile ?? "";
  deviceForm.group_id = device.group_id ?? "";
  detailModalOpen.value = false;
  formModalOpen.value = true;
}

function closeFormModal() {
  formModalOpen.value = false;
}

async function submitDeviceForm() {
  formError.value = null;
  if (!deviceForm.device_name.trim()) {
    formError.value = "Le nom sur le projet est obligatoire.";
    return;
  }
  try {
    if (editingDeviceId.value) {
      await devicesApi.update(editingDeviceId.value, {
        device_name: deviceForm.device_name.trim(),
        device_type: deviceForm.device_type,
        // The master device's `active` state can't be toggled at all
        // (backend-enforced, 2026-11-04) -- omitted here entirely when
        // editing a device that will end up master, so saving an
        // unrelated field (e.g. its name) never trips that guard just
        // because this form always carries the checkbox's current
        // value alongside everything else.
        ...(deviceForm.is_master ? {} : { active: deviceForm.active }),
        is_master: deviceForm.is_master,
        handles_audio: deviceForm.device_type === "lumestrio" ? deviceForm.handles_audio : false,
        handles_dmx: deviceForm.device_type === "lumestrio" ? deviceForm.handles_dmx : false,
        ip: deviceForm.ip.trim() || null,
        master_ip: deviceForm.master_ip.trim() || null,
        audiofile: deviceForm.audiofile.trim() || null,
        group_id: deviceForm.group_id || null,
      });
    } else {
      if (deviceForm.device_number === null) {
        formError.value = "Aucun numéro disponible pour ce type d'appareil.";
        return;
      }
      await devicesApi.create({
        device_type: deviceForm.device_type,
        device_number: deviceForm.device_number,
        device_name: deviceForm.device_name.trim(),
        active: deviceForm.active,
        is_master: deviceForm.is_master,
        handles_audio: deviceForm.device_type === "lumestrio" ? deviceForm.handles_audio : false,
        handles_dmx: deviceForm.device_type === "lumestrio" ? deviceForm.handles_dmx : false,
        ip: deviceForm.ip.trim() || null,
        master_ip: deviceForm.master_ip.trim() || null,
        audiofile: deviceForm.audiofile.trim() || null,
        group_id: deviceForm.group_id || null,
      });
    }
    formModalOpen.value = false;
    await loadDevices();
  } catch (err) {
    formError.value = err instanceof Error ? err.message : String(err);
  }
}

async function openDetailModal(deviceId: string) {
  detailDevice.value = await devicesApi.get(deviceId);
  detailModalOpen.value = true;
}

function closeDetailModal() {
  detailModalOpen.value = false;
}

async function openGroupDetailModal(device: DevicePublic) {
  if (!device.group_id) return;
  groupDetail.value = await groupsApi.get(device.group_id);
  groupDetailCalendar.value = device.calendar;
  groupDetailModalOpen.value = true;
}

function closeGroupDetailModal() {
  groupDetailModalOpen.value = false;
}

function openCalendarDetailModal(calendar: CalendarPublic) {
  calendarDetail.value = calendar;
  calendarDetailModalOpen.value = true;
}

function closeCalendarDetailModal() {
  calendarDetailModalOpen.value = false;
}

function openCalendarFromGroup() {
  groupDetailModalOpen.value = false;
  if (groupDetailCalendar.value) {
    openCalendarDetailModal(groupDetailCalendar.value);
  }
}

async function openMasterDetailFromForm(deviceId: string) {
  closeFormModal();
  await openDetailModal(deviceId);
}

async function unsetMaster(deviceId: string) {
  await devicesApi.update(deviceId, { is_master: false });
  await loadDevices();
  detailDevice.value = await devicesApi.get(deviceId);
}

async function toggleActive(device: DevicePublic) {
  await devicesApi.update(device.device_id, { active: !device.active });
  await loadDevices();
}

function toggleSelection(deviceId: string) {
  if (selectedDeviceIds.value.has(deviceId)) {
    selectedDeviceIds.value.delete(deviceId);
  } else {
    selectedDeviceIds.value.add(deviceId);
  }
}

function toggleSelectAll() {
  selectedDeviceIds.value = allSelected.value
    ? new Set()
    : new Set(devices.value.map((d) => d.device_id));
}

async function removeSelectedDevices() {
  await devicesApi.delete([...selectedDeviceIds.value]);
  await loadDevices();
}

let refreshTimer: ReturnType<typeof setInterval> | undefined;
let clockTimer: ReturnType<typeof setInterval> | undefined;

onMounted(() => {
  loadDevices();
  loadPingInterval();
  refreshTimer = setInterval(loadDevices, REFRESH_INTERVAL_MS);
  clockTimer = setInterval(() => {
    now.value = Date.now();
  }, 1000);
});

onUnmounted(() => {
  clearInterval(refreshTimer);
  clearInterval(clockTimer);
});
</script>

<template>
  <PendingSyncBanner
    :count="pendingSyncCount"
    :device-ids="pendingSyncDeviceIds"
    @synced="loadDevices"
  />

  <div class="bulk-actions">
    <button type="button" @click="openCreateModal">Créer un appareil</button>
    <button class="clear-selection" :disabled="selectedDeviceIds.size === 0" @click="removeSelectedDevices">
      Effacer la sélection ({{ selectedDeviceIds.size }})
    </button>
  </div>

  <table>
    <thead>
      <tr>
        <th>
          <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" />
        </th>
        <th>Nom de série</th>
        <th>Nom sur le projet</th>
        <th>Statut</th>
        <th>Joignable</th>
        <th>Groupe</th>
        <th>Calendrier</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="device in devices" :key="device.device_id">
        <td>
          <input
            type="checkbox"
            :checked="selectedDeviceIds.has(device.device_id)"
            @change="toggleSelection(device.device_id)"
          />
        </td>
        <td>{{ device.device_id }}</td>
        <td>
          <a href="#" class="item-link" @click.prevent="openDetailModal(device.device_id)">
            {{ device.device_name }}
          </a>
        </td>
        <td>
          <div class="status-cell">
            <span
              class="bulb"
              :class="device.active ? 'bulb-on' : 'bulb-off'"
              :title="device.active ? 'Allumé' : 'Éteint'"
            >
              💡
            </span>
            <button v-if="!device.is_master" type="button" @click="toggleActive(device)">
              {{ device.active ? "Éteindre" : "Allumer" }}
            </button>
            <span v-else class="hint">Maître — toujours actif</span>
          </div>
        </td>
        <td>
          <div class="reachable-cell">
            <span
              class="reachable-dot"
              :class="isReachable(device) ? 'reachable-yes' : 'reachable-no'"
              :title="device.last_seen ? `Dernier contact ${lastSeenLabel(device)}` : 'Jamais contacté'"
            >
              ●
            </span>
            <span class="hint">{{ lastSeenLabel(device) }}</span>
            <span v-if="device.last_roundtrip_ms !== null" class="hint">
              ({{ device.last_roundtrip_ms }} ms)
            </span>
          </div>
        </td>
        <td>
          <a
            v-if="device.group_id"
            href="#"
            class="item-link"
            @click.prevent="openGroupDetailModal(device)"
          >
            {{ device.group }}
          </a>
          <span v-else>—</span>
        </td>
        <td>
          <a
            v-if="device.calendar"
            href="#"
            class="item-link"
            @click.prevent="openCalendarDetailModal(device.calendar)"
          >
            {{ device.calendar.label }}
          </a>
          <span v-else>—</span>
        </td>
      </tr>
    </tbody>
  </table>

  <div v-if="detailModalOpen" class="modal-backdrop" @click.self="closeDetailModal">
    <div class="modal" v-if="detailDevice">
      <button type="button" class="modal-close" aria-label="Fermer" @click="closeDetailModal">
        ✕
      </button>
      <h2>{{ detailDevice.device_name }}</h2>
      <dl class="detail-list">
        <dt>Nom de série</dt>
        <dd>{{ detailDevice.device_id }}</dd>
        <dt>Type d'appareil</dt>
        <dd>{{ detailDevice.device_type }}</dd>
        <dt>Actif</dt>
        <dd>{{ detailDevice.active ? "ON" : "OFF" }}</dd>
        <dt>Maître</dt>
        <dd>
          {{ detailDevice.is_master ? "Oui" : "Non" }}
          <button v-if="detailDevice.is_master" type="button" @click="unsetMaster(detailDevice.device_id)">
            Retirer le statut de maître
          </button>
        </dd>
        <template v-if="detailDevice.device_type === 'lumestrio'">
          <dt>Options</dt>
          <dd class="options-row">
            <span class="option-status">
              <span :class="detailDevice.handles_audio ? 'icon-ok' : 'icon-ko'">
                {{ detailDevice.handles_audio ? "✓" : "✗" }}
              </span>
              Audio
            </span>
            <span class="option-status">
              <span :class="detailDevice.handles_dmx ? 'icon-ok' : 'icon-ko'">
                {{ detailDevice.handles_dmx ? "✓" : "✗" }}
              </span>
              DMX
            </span>
          </dd>
        </template>
        <dt>Groupe</dt>
        <dd>
          <a
            v-if="detailDevice.group_id"
            href="#"
            class="item-link"
            @click.prevent="openGroupDetailModal(detailDevice)"
          >
            {{ detailDevice.group }}
          </a>
          <span v-else>—</span>
        </dd>
        <dt>Calendrier</dt>
        <dd>
          <a
            v-if="detailDevice.calendar"
            href="#"
            class="item-link"
            @click.prevent="openCalendarDetailModal(detailDevice.calendar)"
          >
            {{ detailDevice.calendar.label }}
          </a>
          <span v-else>—</span>
        </dd>
        <dt>IP</dt>
        <dd>{{ detailDevice.ip ?? "—" }}</dd>
        <dt>IP du master</dt>
        <dd>{{ detailDevice.master_ip ?? "—" }}</dd>
        <dt>Fichier audio</dt>
        <dd>{{ detailDevice.audiofile ?? "—" }}</dd>
        <dt>Joignable</dt>
        <dd>
          <span
            class="reachable-dot"
            :class="isReachable(detailDevice) ? 'reachable-yes' : 'reachable-no'"
          >
            ●
          </span>
          {{ lastSeenLabel(detailDevice) }}
          <span v-if="detailDevice.last_roundtrip_ms !== null">
            ({{ detailDevice.last_roundtrip_ms }} ms)
          </span>
        </dd>
        <dt>Dernière modification</dt>
        <dd>{{ detailDevice.updated_at }}</dd>
      </dl>
      <div class="modal-actions">
        <button type="button" @click="openEditModal(detailDevice)">Mettre à jour</button>
      </div>
    </div>
  </div>

  <div v-if="formModalOpen" class="modal-backdrop" @click.self="closeFormModal">
    <div class="modal">
      <button type="button" class="modal-close" aria-label="Fermer" @click="closeFormModal">
        ✕
      </button>
      <h2>{{ editingDeviceId ? "Modifier le lumestrio" : "Configurer un nouveau lumestrio" }}</h2>
      <p class="mandatory-hint">* Champ obligatoire</p>
      <form class="create-device-form" @submit.prevent="submitDeviceForm">
        <label v-if="editingDeviceId">
          Nom de série
          <input :value="deviceForm.device_id" disabled />
        </label>
        <label>
          Nom sur le projet <span class="mandatory">*</span>
          <input v-model="deviceForm.device_name" required />
        </label>
        <label>
          Type d'appareil <span class="mandatory">*</span>
          <select v-model="deviceForm.device_type" required>
            <option v-for="type in deviceTypes" :key="type" :value="type">
              {{ type }}
            </option>
          </select>
        </label>
        <label v-if="!editingDeviceId">
          Numéro <span class="mandatory">*</span>
          <select v-model.number="deviceForm.device_number" required>
            <option v-if="availableDeviceNumbers.length === 0" :value="null" disabled>
              Aucun numéro disponible
            </option>
            <option v-for="number in availableDeviceNumbers" :key="number" :value="number">
              {{ number }}
            </option>
          </select>
        </label>
        <label v-if="!deviceForm.is_master" class="checkbox-label">
          <input type="checkbox" v-model="deviceForm.active" />
          Actif
        </label>
        <p v-else class="hint">Le maître est toujours actif.</p>
        <label class="checkbox-label">
          <input type="checkbox" v-model="deviceForm.is_master" />
          Maître
        </label>
        <template v-if="deviceForm.device_type === 'lumestrio'">
          <label class="checkbox-label">
            <input type="checkbox" v-model="deviceForm.handles_audio" />
            Gère l'audio
          </label>
          <label class="checkbox-label">
            <input type="checkbox" v-model="deviceForm.handles_dmx" />
            Gère le DMX
          </label>
        </template>
        <p v-if="deviceForm.is_master && existingMaster" class="master-warning">
          Un maître existe déjà : appareil
          <a href="#" class="item-link" @click.prevent="openMasterDetailFromForm(existingMaster.device_id)">
            {{ existingMaster.device_name }}
          </a>
        </p>
        <label>
          Groupe
          <select v-model="deviceForm.group_id" :disabled="deviceForm.is_master">
            <option value="">—</option>
            <option v-for="group in groups" :key="group.uuid" :value="group.uuid">
              {{ group.label }}
            </option>
          </select>
          <span v-if="deviceForm.is_master" class="hint">
            Le maître ne peut pas être associé à un groupe.
          </span>
        </label>
        <label>
          IP
          <input v-model="deviceForm.ip" />
        </label>
        <label>
          IP du master
          <input v-model="deviceForm.master_ip" />
        </label>
        <label>
          Fichier audio
          <input v-model="deviceForm.audiofile" />
        </label>
        <p v-if="formError" class="error">{{ formError }}</p>
        <div class="modal-actions">
          <button type="button" @click="closeFormModal">Annuler</button>
          <button type="submit">{{ editingDeviceId ? "Mettre à jour" : "Enregistrer" }}</button>
        </div>
      </form>
    </div>
  </div>

  <GroupDetailModal
    v-if="groupDetailModalOpen && groupDetail"
    :group="groupDetail"
    :calendar-label="groupDetailCalendar?.label ?? null"
    @close="closeGroupDetailModal"
    @open-calendar="openCalendarFromGroup"
  />

  <CalendarDetailModal
    v-if="calendarDetailModalOpen && calendarDetail"
    :calendar="calendarDetail"
    @close="closeCalendarDetailModal"
  />
</template>

<style scoped>
.bulk-actions {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

.clear-selection:disabled {
  color: var(--color-disabled-text);
}

table {
  border-collapse: collapse;
  width: 100%;
}

.status-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
}

.reachable-cell {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  white-space: nowrap;
}

.reachable-dot {
  font-size: 0.8rem;
  line-height: 1;
}

.reachable-yes {
  color: #2e9e3e;
}

.reachable-no {
  color: var(--color-muted);
}

.bulb {
  font-size: 1.1rem;
  line-height: 1;
}

.bulb-on {
  filter: drop-shadow(0 0 4px gold);
}

.bulb-off {
  filter: grayscale(1) brightness(0.65);
  opacity: 0.6;
}

th,
td {
  text-align: left;
  padding: 0.5rem;
  border-bottom: 1px solid var(--color-border);
}

.error {
  color: red;
}

.item-link {
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-backdrop);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal {
  position: relative;
  background: var(--color-surface);
  color: var(--color-text);
  padding: 1.5rem;
  border-radius: 6px;
  min-width: 320px;
}

.modal-close {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: none;
  border: none;
  color: var(--color-close-icon);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.25rem;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}

.mandatory-hint {
  color: var(--color-muted);
  font-size: 0.85rem;
  font-style: italic;
  margin-top: -0.5rem;
}

.mandatory {
  color: #c00;
}

.master-warning {
  background: var(--color-warning-bg);
  border: 1px solid var(--color-warning-border);
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
  margin: -0.25rem 0 0;
  font-size: 0.85rem;
}

.hint {
  color: var(--color-muted);
  font-size: 0.85rem;
}

.create-device-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 320px;
}

.create-device-form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.create-device-form .checkbox-label {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}

.detail-list {
  max-width: 480px;
}

.detail-list dt {
  font-weight: bold;
  margin-top: 0.75rem;
}

.detail-list dd {
  margin: 0.25rem 0 0;
}

.options-row {
  display: flex;
  gap: 1.25rem;
}

.option-status {
  display: flex;
  align-items: center;
  gap: 0.35rem;
}
</style>
