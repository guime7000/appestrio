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
      devices.map((device) => devicesApi.update(device.device_id, { active })),
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
/* No actual DOM overlap at any viewport width (confirmed 2026-11-04 by
   rendering this page headlessly from 320px to 1280px) -- but without
   `flex-wrap`/`flex-shrink: 0`, two fixed-size 12rem circles plus a
   3rem gap (432px total) don't fit a narrow/mobile screen, so the
   default flex-shrink squeezes them into ovals sitting close together.
   On a real touchscreen (this page's actual use case, at an event)
   that's a real mis-tap risk between adjacent large buttons -- almost
   certainly what was reported as "clicking Allumer also hits
   Eteindre." Fixed by never shrinking the circles and letting them
   wrap onto their own row instead when they don't both fit. */
.power-buttons {
  display: flex;
  flex-wrap: wrap;
  gap: 3rem;
  justify-content: center;
  align-items: center;
  margin-top: 3rem;
}

.power-button {
  width: 12rem;
  height: 12rem;
  flex-shrink: 0;
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
