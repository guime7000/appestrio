<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { devicesApi } from "@/api/devices";
import type { DevicePublic } from "@/api/types";

const devices = ref<DevicePublic[]>([]);
const newDeviceId = ref("");
const newDeviceName = ref("");
const error = ref<string | null>(null);
const selectedUuids = ref<Set<string>>(new Set());

const allSelected = computed(
  () => devices.value.length > 0 && selectedUuids.value.size === devices.value.length,
);

async function loadDevices() {
  const result = await devicesApi.list();
  devices.value = result.data;
  selectedUuids.value = new Set(
    [...selectedUuids.value].filter((uuid) => devices.value.some((d) => d.uuid === uuid)),
  );
}

async function createDevice() {
  error.value = null;
  try {
    await devicesApi.create({
      device_id: newDeviceId.value,
      device_name: newDeviceName.value,
    });
    newDeviceId.value = "";
    newDeviceName.value = "";
    await loadDevices();
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  }
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

  <form class="create-form" @submit.prevent="createDevice">
    <input v-model="newDeviceId" placeholder="Nom de série" required />
    <input v-model="newDeviceName" placeholder="Nom sur le projet" required />
    <button type="submit">Ajouter</button>
  </form>
  <p v-if="error" class="error">{{ error }}</p>

  <div class="bulk-actions">
    <button :disabled="selectedUuids.size === 0" @click="removeSelectedDevices">
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
        <td>{{ device.device_name }}</td>
        <td>
          <button @click="toggleActive(device)">
            {{ device.active ? "ON" : "OFF" }}
          </button>
        </td>
        <td>{{ device.group ?? "—" }}</td>
        <td>{{ device.calendar?.label ?? "—" }}</td>
      </tr>
    </tbody>
  </table>
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

.error {
  color: red;
}
</style>
