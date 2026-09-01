<script setup lang="ts">
import { ref } from "vue";

import { devicesApi } from "@/api/devices";

const busy = ref(false);

async function setAllDevicesActive(active: boolean) {
  if (busy.value) return;
  busy.value = true;
  try {
    const { data: devices } = await devicesApi.list();
    await Promise.all(
      devices.map((device) => devicesApi.update(device.uuid, { active })),
    );
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <h1>Inauguration</h1>

  <div class="power-buttons">
    <button
      type="button"
      class="power-button power-on"
      :disabled="busy"
      @click="setAllDevicesActive(true)"
    >
      Allumer
    </button>
    <button
      type="button"
      class="power-button power-off"
      :disabled="busy"
      @click="setAllDevicesActive(false)"
    >
      Eteindre
    </button>
  </div>
</template>

<style scoped>
.power-buttons {
  display: flex;
  gap: 3rem;
  justify-content: center;
  align-items: center;
  margin-top: 3rem;
}

.power-button {
  width: 12rem;
  height: 12rem;
  border-radius: 50%;
  border: none;
  font-size: 1.4rem;
  font-weight: bold;
  color: white;
  cursor: pointer;
}

.power-button:disabled {
  opacity: 0.6;
  cursor: default;
}

.power-on {
  background: #2e9e3e;
}

.power-off {
  background: #c0392b;
}
</style>
