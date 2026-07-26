<script setup lang="ts">
import { onMounted, ref } from "vue";

import { devicesApi } from "@/api/devices";
import type { DevicePublic } from "@/api/types";

const devices = ref<DevicePublic[]>([]);
const newDeviceId = ref("");
const newDeviceName = ref("");
const error = ref<string | null>(null);

async function loadDevices() {
  const result = await devicesApi.list();
  devices.value = result.data;
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

async function removeDevice(uuid: string) {
  await devicesApi.delete(uuid);
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

  <table>
    <thead>
      <tr>
        <th>Nom de série</th>
        <th>Nom sur le projet</th>
        <th>Actif</th>
        <th>Groupe</th>
        <th>Calendrier</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="device in devices" :key="device.uuid">
        <td>{{ device.device_id }}</td>
        <td>{{ device.device_name }}</td>
        <td>
          <button @click="toggleActive(device)">
            {{ device.active ? "ON" : "OFF" }}
          </button>
        </td>
        <td>{{ device.group ?? "—" }}</td>
        <td>{{ device.calendar?.label ?? "—" }}</td>
        <td><button @click="removeDevice(device.uuid)">Effacer</button></td>
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
