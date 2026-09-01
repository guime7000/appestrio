<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import CalendarDetailModal from "@/components/CalendarDetailModal.vue";
import GroupDetailModal from "@/components/GroupDetailModal.vue";
import { devicesApi } from "@/api/devices";
import { groupsApi } from "@/api/groups";
import type { CalendarPublic, DevicePublic, DeviceType, GroupPublic } from "@/api/types";

const deviceTypes: DeviceType[] = ["lumestrio", "relaystrio"];

const devices = ref<DevicePublic[]>([]);
const groups = ref<GroupPublic[]>([]);
const selectedUuids = ref<Set<string>>(new Set());

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
const editingUuid = ref<string | null>(null);
const deviceForm = reactive({
  device_id: "",
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

const allSelected = computed(
  () => devices.value.length > 0 && selectedUuids.value.size === devices.value.length,
);

const existingMaster = computed(
  () => devices.value.find((d) => d.is_master && d.uuid !== editingUuid.value) ?? null,
);

async function loadDevices() {
  const [devicesResult, groupsResult] = await Promise.all([devicesApi.list(), groupsApi.list()]);
  devices.value = devicesResult.data;
  groups.value = groupsResult.data;
  selectedUuids.value = new Set(
    [...selectedUuids.value].filter((uuid) => devices.value.some((d) => d.uuid === uuid)),
  );
}

function openCreateModal() {
  formError.value = null;
  editingUuid.value = null;
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
  formModalOpen.value = true;
}

function openEditModal(device: DevicePublic) {
  formError.value = null;
  editingUuid.value = device.uuid;
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
  if (!deviceForm.device_id.trim() || !deviceForm.device_name.trim()) {
    formError.value = "Le nom de série et le nom sur le projet sont obligatoires.";
    return;
  }
  const payload = {
    device_id: deviceForm.device_id.trim(),
    device_name: deviceForm.device_name.trim(),
    device_type: deviceForm.device_type,
    active: deviceForm.active,
    is_master: deviceForm.is_master,
    handles_audio: deviceForm.device_type === "lumestrio" ? deviceForm.handles_audio : false,
    handles_dmx: deviceForm.device_type === "lumestrio" ? deviceForm.handles_dmx : false,
    ip: deviceForm.ip.trim() || null,
    master_ip: deviceForm.master_ip.trim() || null,
    audiofile: deviceForm.audiofile.trim() || null,
    group_id: deviceForm.group_id || null,
  };
  try {
    if (editingUuid.value) {
      await devicesApi.update(editingUuid.value, payload);
    } else {
      await devicesApi.create(payload);
    }
    formModalOpen.value = false;
    await loadDevices();
  } catch (err) {
    formError.value = err instanceof Error ? err.message : String(err);
  }
}

async function openDetailModal(uuid: string) {
  detailDevice.value = await devicesApi.get(uuid);
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

async function openMasterDetailFromForm(uuid: string) {
  closeFormModal();
  await openDetailModal(uuid);
}

async function unsetMaster(uuid: string) {
  await devicesApi.update(uuid, { is_master: false });
  await loadDevices();
  detailDevice.value = await devicesApi.get(uuid);
}

async function toggleActive(device: DevicePublic) {
  await devicesApi.update(device.uuid, { active: !device.active });
  await loadDevices();
}

function toggleSelection(uuid: string) {
  if (selectedUuids.value.has(uuid)) {
    selectedUuids.value.delete(uuid);
  } else {
    selectedUuids.value.add(uuid);
  }
}

function toggleSelectAll() {
  selectedUuids.value = allSelected.value
    ? new Set()
    : new Set(devices.value.map((d) => d.uuid));
}

async function removeSelectedDevices() {
  await devicesApi.delete([...selectedUuids.value]);
  await loadDevices();
}

onMounted(loadDevices);
</script>

<template>
  <div class="bulk-actions">
    <button type="button" @click="openCreateModal">Créer un appareil</button>
    <button class="clear-selection" :disabled="selectedUuids.size === 0" @click="removeSelectedDevices">
      Effacer la sélection ({{ selectedUuids.size }})
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
        <th>Status</th>
        <th>Groupe</th>
        <th>Calendrier</th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="device in devices" :key="device.uuid">
        <td>
          <input
            type="checkbox"
            :checked="selectedUuids.has(device.uuid)"
            @change="toggleSelection(device.uuid)"
          />
        </td>
        <td>{{ device.device_id }}</td>
        <td>
          <a href="#" class="item-link" @click.prevent="openDetailModal(device.uuid)">
            {{ device.device_name }}
          </a>
        </td>
        <td class="status-cell">
          <span :class="device.active ? 'icon-ok' : 'icon-ko'">
            {{ device.active ? "✓" : "✗" }}
          </span>
          <button @click="toggleActive(device)">
            {{ device.active ? "Éteindre" : "Allumer" }}
          </button>
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
        <dt>UUID</dt>
        <dd>{{ detailDevice.uuid }}</dd>
        <dt>Actif</dt>
        <dd>{{ detailDevice.active ? "ON" : "OFF" }}</dd>
        <dt>Maître</dt>
        <dd>
          {{ detailDevice.is_master ? "Oui" : "Non" }}
          <button v-if="detailDevice.is_master" type="button" @click="unsetMaster(detailDevice.uuid)">
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
      <h2>{{ editingUuid ? "Modifier le lumestrio" : "Configurer un nouveau lumestrio" }}</h2>
      <p class="mandatory-hint">* Champ obligatoire</p>
      <form class="create-device-form" @submit.prevent="submitDeviceForm">
        <label>
          Nom de série <span class="mandatory">*</span>
          <input v-model="deviceForm.device_id" required />
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
        <label class="checkbox-label">
          <input type="checkbox" v-model="deviceForm.active" />
          Actif
        </label>
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
          <a href="#" class="item-link" @click.prevent="openMasterDetailFromForm(existingMaster.uuid)">
            {{ existingMaster.device_name }}
          </a>
        </p>
        <label>
          Groupe
          <select v-model="deviceForm.group_id">
            <option value="">—</option>
            <option v-for="group in groups" :key="group.uuid" :value="group.uuid">
              {{ group.label }}
            </option>
          </select>
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
          <button type="submit">{{ editingUuid ? "Mettre à jour" : "Enregistrer" }}</button>
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

.icon-ok {
  color: #2e7d32;
  font-weight: bold;
}

.icon-ko {
  color: #c62828;
  font-weight: bold;
}
</style>
