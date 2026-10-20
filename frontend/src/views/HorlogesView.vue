<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from "vue";

import { loraSettingsApi } from "@/api/loraSettings";

const now = ref(new Date());
let timer: ReturnType<typeof setInterval> | undefined;

const formatter = new Intl.DateTimeFormat("fr-FR", {
  dateStyle: "long",
  timeStyle: "medium",
});

onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date();
  }, 1000);
});

onBeforeUnmount(() => {
  clearInterval(timer);
});

const busy = ref(false);

async function syncClocksNow() {
  if (busy.value) return;
  busy.value = true;
  try {
    await loraSettingsApi.syncClocksNow();
  } finally {
    busy.value = false;
  }
}
</script>

<template>
  <div class="clock-panel">
    <p class="clock-label">Date et heure actuelles de l'hôte</p>
    <p class="clock-value">{{ formatter.format(now) }}</p>
    <button
      type="button"
      class="sync-button"
      :disabled="busy"
      @click="syncClocksNow"
    >
      Synchroniser les horloges
    </button>
  </div>
</template>

<style scoped>
.clock-panel {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.75rem;
}

.clock-label {
  margin: 0;
  color: var(--color-muted);
  font-size: 0.9rem;
}

.clock-value {
  margin: 0;
  font-size: 1.5rem;
  font-weight: bold;
}

.sync-button {
  margin-top: 0.5rem;
  padding: 0.5rem 1rem;
}
</style>
