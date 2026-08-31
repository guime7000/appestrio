<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import CalendarDetailModal from "@/components/CalendarDetailModal.vue";
import DeviceDetailModal from "@/components/DeviceDetailModal.vue";
import { calendarsApi } from "@/api/calendars";
import { devicesApi } from "@/api/devices";
import { groupsApi } from "@/api/groups";
import type {
  CalendarPublic,
  CalendarSummaryPublic,
  DevicePublic,
  GroupDevicePublic,
  GroupPublic,
} from "@/api/types";

const route = useRoute();

const groups = ref<GroupPublic[]>([]);
const allDevices = ref<DevicePublic[]>([]);
const calendars = ref<CalendarSummaryPublic[]>([]);
const calendarLabels = ref<Record<string, string>>({});
const newGroupLabel = ref("");
const editingGroupUuid = ref<string | null>(null);
const selectedDeviceUuids = ref<Set<string>>(new Set());
const selectedGroupUuids = ref<Set<string>>(new Set());

const detailModalOpen = ref(false);
const detailGroup = ref<GroupPublic | null>(null);
const expandedGroupUuids = ref<Set<string>>(new Set());

const deviceDetailModalOpen = ref(false);
const deviceDetail = ref<DevicePublic | null>(null);

const calendarDetailModalOpen = ref(false);
const calendarDetail = ref<CalendarPublic | null>(null);

const groupFormModalOpen = ref(false);
const groupFormError = ref<string | null>(null);
const groupFormUuid = ref<string | null>(null);
const groupForm = reactive({
  label: "",
  calendar_id: "",
});

const allSelected = computed(
  () => groups.value.length > 0 && selectedGroupUuids.value.size === groups.value.length,
);

async function loadAll() {
  const [groupsResult, devicesResult, calendarsResult] = await Promise.all([
    groupsApi.list(),
    devicesApi.list(),
    calendarsApi.list(),
  ]);
  groups.value = groupsResult.data;
  allDevices.value = devicesResult.data;
  calendars.value = calendarsResult.data;
  calendarLabels.value = Object.fromEntries(
    calendarsResult.data.map((c) => [c.uuid, c.label]),
  );
  selectedGroupUuids.value = new Set(
    [...selectedGroupUuids.value].filter((uuid) => groups.value.some((g) => g.uuid === uuid)),
  );
}

function calendarLabel(group: GroupPublic): string {
  return (group.calendar_id && calendarLabels.value[group.calendar_id]) || "—";
}

function isGroupFullyActive(group: GroupPublic): boolean {
  return group.devices.length > 0 && group.devices.every((device) => device.active);
}

async function toggleDeviceActive(device: GroupDevicePublic) {
  await devicesApi.update(device.uuid, { active: !device.active });
  await loadAll();
}

async function toggleGroupDevicesActive(group: GroupPublic) {
  const nextActive = !isGroupFullyActive(group);
  await Promise.all(
    group.devices.map((device) => devicesApi.update(device.uuid, { active: nextActive })),
  );
  await loadAll();
}

async function createGroup() {
  await groupsApi.create({ label: newGroupLabel.value });
  newGroupLabel.value = "";
  await loadAll();
}

function toggleGroupSelection(uuid: string) {
  if (selectedGroupUuids.value.has(uuid)) {
    selectedGroupUuids.value.delete(uuid);
  } else {
    selectedGroupUuids.value.add(uuid);
  }
}

function toggleSelectAllGroups() {
  selectedGroupUuids.value = allSelected.value
    ? new Set()
    : new Set(groups.value.map((g) => g.uuid));
}

async function removeSelectedGroups() {
  await groupsApi.delete([...selectedGroupUuids.value]);
  await loadAll();
}

async function openDetailModal(uuid: string) {
  detailGroup.value = await groupsApi.get(uuid);
  detailModalOpen.value = true;
}

function closeDetailModal() {
  detailModalOpen.value = false;
}

async function openDeviceDetailModal(uuid: string) {
  deviceDetail.value = await devicesApi.get(uuid);
  deviceDetailModalOpen.value = true;
}

function closeDeviceDetailModal() {
  deviceDetailModalOpen.value = false;
}

async function openCalendarDetailModal(calendarUuid: string) {
  calendarDetail.value = await calendarsApi.get(calendarUuid);
  calendarDetailModalOpen.value = true;
}

function closeCalendarDetailModal() {
  calendarDetailModalOpen.value = false;
}

function openCalendarFromDevice() {
  // Already the full object (device.calendar === device.group.calendar on the
  // backend), so no extra fetch needed here unlike the table/detail-modal
  // entry points, which only ever have the calendar's uuid on hand.
  if (deviceDetail.value?.calendar) {
    calendarDetail.value = deviceDetail.value.calendar;
    deviceDetailModalOpen.value = false;
    calendarDetailModalOpen.value = true;
  }
}

function openGroupFormModal(group: GroupPublic) {
  groupFormError.value = null;
  groupFormUuid.value = group.uuid;
  groupForm.label = group.label;
  groupForm.calendar_id = group.calendar_id ?? "";
  detailModalOpen.value = false;
  groupFormModalOpen.value = true;
}

function closeGroupFormModal() {
  groupFormModalOpen.value = false;
}

async function submitGroupForm() {
  groupFormError.value = null;
  if (!groupForm.label.trim()) {
    groupFormError.value = "Le nom du groupe est obligatoire.";
    return;
  }
  if (!groupFormUuid.value) return;
  try {
    await groupsApi.update(groupFormUuid.value, {
      label: groupForm.label.trim(),
      calendar_id: groupForm.calendar_id || null,
    });
    groupFormModalOpen.value = false;
    await loadAll();
  } catch (err) {
    groupFormError.value = err instanceof Error ? err.message : String(err);
  }
}

function toggleExpand(uuid: string) {
  if (expandedGroupUuids.value.has(uuid)) {
    expandedGroupUuids.value.delete(uuid);
  } else {
    expandedGroupUuids.value.add(uuid);
  }
}

function openDevicePicker(group: GroupPublic) {
  editingGroupUuid.value = group.uuid;
  selectedDeviceUuids.value = new Set(group.devices.map((d) => d.uuid));
}

function toggleDeviceSelection(uuid: string) {
  if (selectedDeviceUuids.value.has(uuid)) {
    selectedDeviceUuids.value.delete(uuid);
  } else {
    selectedDeviceUuids.value.add(uuid);
  }
}

async function saveDeviceSelection() {
  if (!editingGroupUuid.value) return;
  await groupsApi.setDevices(editingGroupUuid.value, [...selectedDeviceUuids.value]);
  editingGroupUuid.value = null;
  await loadAll();
}

// A device already in another group can still be picked here — assigning it
// moves it (one lumestrio belongs to at most one group).
function deviceLabel(device: DevicePublic): string {
  return device.group && device.group !== editingGroupLabel()
    ? `${device.device_name} (actuellement: ${device.group})`
    : device.device_name;
}

function editingGroupLabel(): string | undefined {
  return groups.value.find((g) => g.uuid === editingGroupUuid.value)?.label;
}

onMounted(async () => {
  await loadAll();
  const uuid = route.query.uuid;
  if (typeof uuid === "string") {
    await openDetailModal(uuid);
  }
});
</script>

<template>
  <h1>Je gère les groupes</h1>

  <form class="create-form" @submit.prevent="createGroup">
    <input v-model="newGroupLabel" placeholder="Nom du groupe" required />
    <button type="submit">Créer un groupe</button>
  </form>

  <div class="bulk-actions">
    <button class="clear-selection" :disabled="selectedGroupUuids.size === 0" @click="removeSelectedGroups">
      Effacer la sélection ({{ selectedGroupUuids.size }})
    </button>
  </div>

  <table>
    <thead>
      <tr>
        <th>
          <input type="checkbox" :checked="allSelected" @change="toggleSelectAllGroups" />
        </th>
        <th>Nom du groupe</th>
        <th>Nombre de lumestrio</th>
        <th>Calendrier</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      <template v-for="group in groups" :key="group.uuid">
        <tr>
          <td>
            <input
              type="checkbox"
              :checked="selectedGroupUuids.has(group.uuid)"
              @change="toggleGroupSelection(group.uuid)"
            />
          </td>
          <td class="group-name-cell">
            <button
              type="button"
              :disabled="group.devices.length === 0"
              @click="toggleGroupDevicesActive(group)"
            >
              {{ isGroupFullyActive(group) ? "Tout éteindre" : "Tout allumer" }}
            </button>
            <a href="#" class="item-link" @click.prevent="openDetailModal(group.uuid)">
              {{ group.label }}
            </a>
            <button
              type="button"
              class="expand-toggle"
              :class="{ expanded: expandedGroupUuids.has(group.uuid) }"
              :disabled="group.devices.length === 0"
              @click="toggleExpand(group.uuid)"
            >
              ▶
            </button>
          </td>
          <td>{{ group.devices.length }}</td>
          <td>
            <a
              v-if="group.calendar_id"
              href="#"
              class="item-link"
              @click.prevent="openCalendarDetailModal(group.calendar_id)"
            >
              {{ calendarLabel(group) }}
            </a>
            <span v-else>—</span>
          </td>
          <td class="row-actions">
            <button @click="openDevicePicker(group)">Associer des appareils</button>
          </td>
        </tr>
        <tr v-if="expandedGroupUuids.has(group.uuid)" class="expanded-row">
          <td></td>
          <td colspan="4">
            <table v-if="group.devices.length > 0" class="device-subtable">
              <thead>
                <tr>
                  <th>Lumestrio</th>
                  <th>Audio</th>
                  <th>DMX</th>
                  <th>Statut</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="device in group.devices" :key="device.uuid">
                  <td>
                    <a
                      href="#"
                      class="item-link"
                      @click.prevent="openDeviceDetailModal(device.uuid)"
                    >
                      {{ device.device_name }}
                    </a>
                  </td>
                  <td>
                    <span :class="device.handles_audio ? 'icon-ok' : 'icon-ko'">
                      {{ device.handles_audio ? "✓" : "✗" }}
                    </span>
                  </td>
                  <td>
                    <span :class="device.handles_dmx ? 'icon-ok' : 'icon-ko'">
                      {{ device.handles_dmx ? "✓" : "✗" }}
                    </span>
                  </td>
                  <td class="status-cell">
                    <span :class="device.active ? 'icon-ok' : 'icon-ko'">
                      {{ device.active ? "✓" : "✗" }}
                    </span>
                    <button type="button" @click="toggleDeviceActive(device)">
                      {{ device.active ? "Éteindre" : "Allumer" }}
                    </button>
                  </td>
                </tr>
              </tbody>
            </table>
          </td>
        </tr>
      </template>
    </tbody>
  </table>

  <div v-if="editingGroupUuid" class="picker">
    <h2>Appareils du groupe</h2>
    <label v-for="device in allDevices" :key="device.uuid" class="picker-row">
      <input
        type="checkbox"
        :checked="selectedDeviceUuids.has(device.uuid)"
        @change="toggleDeviceSelection(device.uuid)"
      />
      {{ deviceLabel(device) }}
    </label>
    <div class="picker-actions">
      <button @click="saveDeviceSelection">Enregistrer</button>
      <button @click="editingGroupUuid = null">Annuler</button>
    </div>
  </div>

  <div v-if="detailModalOpen" class="modal-backdrop" @click.self="closeDetailModal">
    <div class="modal" v-if="detailGroup">
      <button type="button" class="modal-close" aria-label="Fermer" @click="closeDetailModal">
        ✕
      </button>
      <h2>{{ detailGroup.label }}</h2>
      <dl class="detail-list">
        <dt>UUID</dt>
        <dd>{{ detailGroup.uuid }}</dd>
        <dt>Dernière modification</dt>
        <dd>{{ detailGroup.updated_at }}</dd>
        <dt>Calendrier</dt>
        <dd>
          <a
            v-if="detailGroup.calendar_id"
            href="#"
            class="item-link"
            @click.prevent="openCalendarDetailModal(detailGroup.calendar_id)"
          >
            {{ calendarLabels[detailGroup.calendar_id] ?? "—" }}
          </a>
          <span v-else>—</span>
        </dd>
        <dt>Appareils</dt>
        <dd>
          <span v-if="detailGroup.devices.length === 0">—</span>
          <ul v-else>
            <li v-for="device in detailGroup.devices" :key="device.uuid">
              <a href="#" class="item-link" @click.prevent="openDeviceDetailModal(device.uuid)">
                {{ device.device_name }}
              </a>
            </li>
          </ul>
        </dd>
      </dl>
      <div class="modal-actions">
        <button type="button" @click="openGroupFormModal(detailGroup)">Mettre à jour</button>
      </div>
    </div>
  </div>

  <div v-if="groupFormModalOpen" class="modal-backdrop" @click.self="closeGroupFormModal">
    <div class="modal">
      <button type="button" class="modal-close" aria-label="Fermer" @click="closeGroupFormModal">
        ✕
      </button>
      <h2>Modifier le groupe</h2>
      <p class="mandatory-hint">* Champ obligatoire</p>
      <form class="group-edit-form" @submit.prevent="submitGroupForm">
        <label>
          Nom du groupe <span class="mandatory">*</span>
          <input v-model="groupForm.label" required />
        </label>
        <label>
          Calendrier
          <select v-model="groupForm.calendar_id">
            <option value="">—</option>
            <option v-for="calendar in calendars" :key="calendar.uuid" :value="calendar.uuid">
              {{ calendar.label }}
            </option>
          </select>
        </label>
        <p v-if="groupFormError" class="error">{{ groupFormError }}</p>
        <div class="modal-actions">
          <button type="button" @click="closeGroupFormModal">Annuler</button>
          <button type="submit">Mettre à jour</button>
        </div>
      </form>
    </div>
  </div>

  <DeviceDetailModal
    v-if="deviceDetailModalOpen && deviceDetail"
    :device="deviceDetail"
    @close="closeDeviceDetailModal"
    @open-calendar="openCalendarFromDevice"
  />

  <CalendarDetailModal
    v-if="calendarDetailModalOpen && calendarDetail"
    :calendar="calendarDetail"
    @close="closeCalendarDetailModal"
  />
</template>

<style scoped>
.clear-selection:disabled {
  color: var(--color-disabled-text);
}

.create-form {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
}

table {
  border-collapse: collapse;
  width: 100%;
}

th,
td {
  text-align: left;
  padding: 0.5rem;
  border-bottom: 1px solid var(--color-border);
}

.picker {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid var(--color-border);
  border-radius: 0.5rem;
}

.picker-row {
  display: block;
  padding: 0.25rem 0;
}

.picker-actions {
  margin-top: 1rem;
  display: flex;
  gap: 0.5rem;
}

.item-link {
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.expand-toggle {
  background: none;
  border: none;
  color: var(--color-icon-strong);
  cursor: pointer;
  padding: 0;
  margin-left: 0.5rem;
  font-size: 0.7rem;
  display: inline-block;
  transition: transform 0.15s ease;
}

.expand-toggle:disabled {
  opacity: 0.25;
  cursor: default;
}

.expand-toggle.expanded {
  transform: rotate(90deg);
}

.expanded-row td {
  background: var(--color-surface-alt);
  padding-top: 0;
}

.row-actions {
  display: flex;
  gap: 0.5rem;
}

.group-name-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.device-subtable {
  width: auto;
  margin-left: 2.5rem;
}

.device-subtable th,
.device-subtable td {
  padding: 0.35rem 0.75rem;
}

.status-cell {
  display: flex;
  align-items: center;
  gap: 0.5rem;
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

.error {
  color: red;
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

.group-edit-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 320px;
}

.group-edit-form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}
</style>
