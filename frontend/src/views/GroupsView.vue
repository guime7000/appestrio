<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import { calendarsApi } from "@/api/calendars";
import { devicesApi } from "@/api/devices";
import { groupsApi } from "@/api/groups";
import type { DevicePublic, GroupPublic } from "@/api/types";

const route = useRoute();

const groups = ref<GroupPublic[]>([]);
const allDevices = ref<DevicePublic[]>([]);
const calendarLabels = ref<Record<string, string>>({});
const newGroupLabel = ref("");
const editingGroupUuid = ref<string | null>(null);
const selectedDeviceUuids = ref<Set<string>>(new Set());
const selectedGroupUuids = ref<Set<string>>(new Set());

const detailModalOpen = ref(false);
const detailGroup = ref<GroupPublic | null>(null);
const expandedGroupUuids = ref<Set<string>>(new Set());

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
    <button :disabled="selectedGroupUuids.size === 0" @click="removeSelectedGroups">
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
          <td>
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
          <td>{{ calendarLabel(group) }}</td>
          <td>
            <button @click="openDevicePicker(group)">Associer des appareils</button>
          </td>
        </tr>
        <tr v-if="expandedGroupUuids.has(group.uuid)" class="expanded-row">
          <td></td>
          <td colspan="4">
            <ul class="device-list">
              <li v-for="device in group.devices" :key="device.uuid">
                {{ device.device_name }}
              </li>
            </ul>
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
        <dd>{{ (detailGroup.calendar_id && calendarLabels[detailGroup.calendar_id]) || "—" }}</dd>
        <dt>Appareils</dt>
        <dd>
          <span v-if="detailGroup.devices.length === 0">—</span>
          <ul v-else>
            <li v-for="device in detailGroup.devices" :key="device.uuid">
              {{ device.device_name }}
            </li>
          </ul>
        </dd>
      </dl>
    </div>
  </div>
</template>

<style scoped>
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
  border-bottom: 1px solid #ccc;
}

.picker {
  margin-top: 1rem;
  padding: 1rem;
  border: 1px solid #ccc;
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
  background: #fafafa;
  padding-top: 0;
}

.device-list {
  margin: 0;
  padding-left: 2.5rem;
  list-style: disc;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal {
  position: relative;
  background: white;
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
</style>
