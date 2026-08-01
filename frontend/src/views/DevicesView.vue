<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { devicesApi } from "@/api/devices";
import { groupsApi } from "@/api/groups";
import type { DevicePublic, GroupPublic } from "@/api/types";

const devices = ref<DevicePublic[]>([]);
const groups = ref<GroupPublic[]>([]);
const selectedUuids = ref<Set<string>>(new Set());

const detailModalOpen = ref(false);
const detailDevice = ref<DevicePublic | null>(null);

const createModalOpen = ref(false);
const createError = ref<string | null>(null);
const createForm = reactive({
  device_id: "",
  device_name: "",
  active: true,
  ip: "",
  master_ip: "",
  audiofile: "",
  group_id: "",
});

const allSelected = computed(
  () => devices.value.length > 0 && selectedUuids.value.size === devices.value.length,
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
  createError.value = null;
  createForm.device_id = "";
  createForm.device_name = "";
  createForm.active = true;
  createForm.ip = "";
  createForm.master_ip = "";
  createForm.audiofile = "";
  createForm.group_id = "";
  createModalOpen.value = true;
}

function closeCreateModal() {
  createModalOpen.value = false;
}

async function submitCreateDevice() {
  createError.value = null;
  if (!createForm.device_id.trim() || !createForm.device_name.trim()) {
    createError.value = "Le nom de série et le nom sur le projet sont obligatoires.";
    return;
  }
  try {
    await devicesApi.create({
      device_id: createForm.device_id.trim(),
      device_name: createForm.device_name.trim(),
      active: createForm.active,
      ip: createForm.ip.trim() || null,
      master_ip: createForm.master_ip.trim() || null,
      audiofile: createForm.audiofile.trim() || null,
      group_id: createForm.group_id || null,
    });
    createModalOpen.value = false;
    await loadDevices();
  } catch (err) {
    createError.value = err instanceof Error ? err.message : String(err);
  }
}

async function openDetailModal(uuid: string) {
  detailDevice.value = await devicesApi.get(uuid);
  detailModalOpen.value = true;
}

function closeDetailModal() {
  detailModalOpen.value = false;
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
  <h1>Je gère les APPAREILS</h1>

  <div class="bulk-actions">
    <button :disabled="selectedUuids.size === 0" @click="removeSelectedDevices">
      Effacer la sélection ({{ selectedUuids.size }})
    </button>
    <button type="button" @click="openCreateModal">Créer un appareil</button>
  </div>

  <table>
    <thead>
      <tr>
        <th>
          <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" />
        </th>
        <th>Nom de série</th>
        <th>Nom sur le projet</th>
        <th>Actif</th>
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
        <td>
          <button @click="toggleActive(device)">
            {{ device.active ? "ON" : "OFF" }}
          </button>
        </td>
        <td>
          <RouterLink v-if="device.group_id" :to="{ name: 'groups', query: { uuid: device.group_id } }">
            {{ device.group }}
          </RouterLink>
          <span v-else>—</span>
        </td>
        <td>{{ device.calendar?.label ?? "—" }}</td>
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
        <dt>UUID</dt>
        <dd>{{ detailDevice.uuid }}</dd>
        <dt>Actif</dt>
        <dd>{{ detailDevice.active ? "ON" : "OFF" }}</dd>
        <dt>Groupe</dt>
        <dd>{{ detailDevice.group ?? "—" }}</dd>
        <dt>Calendrier</dt>
        <dd>{{ detailDevice.calendar?.label ?? "—" }}</dd>
        <dt>IP</dt>
        <dd>{{ detailDevice.ip ?? "—" }}</dd>
        <dt>IP du master</dt>
        <dd>{{ detailDevice.master_ip ?? "—" }}</dd>
        <dt>Fichier audio</dt>
        <dd>{{ detailDevice.audiofile ?? "—" }}</dd>
        <dt>Dernière modification</dt>
        <dd>{{ detailDevice.updated_at }}</dd>
      </dl>
    </div>
  </div>

  <div v-if="createModalOpen" class="modal-backdrop" @click.self="closeCreateModal">
    <div class="modal">
      <button type="button" class="modal-close" aria-label="Fermer" @click="closeCreateModal">
        ✕
      </button>
      <h2>Configurer un nouveau lumestrio</h2>
      <p class="mandatory-hint">* Champ obligatoire</p>
      <form class="create-device-form" @submit.prevent="submitCreateDevice">
        <label>
          Nom de série <span class="mandatory">*</span>
          <input v-model="createForm.device_id" required />
        </label>
        <label>
          Nom sur le projet <span class="mandatory">*</span>
          <input v-model="createForm.device_name" required />
        </label>
        <label class="checkbox-label">
          <input type="checkbox" v-model="createForm.active" />
          Actif
        </label>
        <label>
          Groupe
          <select v-model="createForm.group_id">
            <option value="">—</option>
            <option v-for="group in groups" :key="group.uuid" :value="group.uuid">
              {{ group.label }}
            </option>
          </select>
        </label>
        <label>
          IP
          <input v-model="createForm.ip" />
        </label>
        <label>
          IP du master
          <input v-model="createForm.master_ip" />
        </label>
        <label>
          Fichier audio
          <input v-model="createForm.audiofile" />
        </label>
        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="modal-actions">
          <button type="button" @click="closeCreateModal">Annuler</button>
          <button type="submit">Enregistrer</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
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

.mandatory-hint {
  color: #666;
  font-size: 0.85rem;
  font-style: italic;
  margin-top: -0.5rem;
}

.mandatory {
  color: #c00;
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
</style>
