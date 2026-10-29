<script setup lang="ts">
import { ref } from "vue";
import { devicesApi } from "@/api/devices";

const props = defineProps<{
  count: number;
  deviceIds: string[];
}>();

const emit = defineEmits<{ synced: [] }>();

const busy = ref(false);
const result = ref<string | null>(null);

async function pushConfig() {
  if (busy.value) return;
  busy.value = true;
  result.value = null;
  try {
    const { message } = await devicesApi.syncConfig(props.deviceIds);
    result.value = message;
  } catch (err) {
    result.value = err instanceof Error ? err.message : String(err);
  } finally {
    busy.value = false;
    emit("synced");
  }
}
</script>

<template>
  <div v-if="count > 0" class="pending-sync-banner" role="alert">
    <div class="pending-sync-row">
      <span>
        Des appareils ont été modifiés : leur configuration doit être mise à jour
        sur les appareils concernés.
      </span>
      <button
        type="button"
        class="push-config-button"
        :disabled="busy"
        @click="pushConfig"
      >
        {{ busy ? "Mise à jour en cours…" : "Mettre à jour la configuration" }}
      </button>
    </div>
    <p v-if="result" class="push-config-result">{{ result }}</p>
  </div>
</template>

<style scoped>
.pending-sync-banner {
  background: var(--color-danger-bg);
  color: var(--color-danger-text);
  border: 1px solid var(--color-danger-border);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-weight: 600;
}

.pending-sync-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  flex-wrap: wrap;
}

.push-config-button {
  flex-shrink: 0;
}

.push-config-button:disabled {
  color: var(--color-disabled-text);
}

.push-config-result {
  margin: 0.5rem 0 0;
  font-weight: normal;
  font-size: 0.85rem;
}
</style>
