<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";

import { loraSettingsApi } from "@/api/loraSettings";
import type { LoraSettingsPublic } from "@/api/types";

// Index -> kbps, matching legacy's airDataRates (app/models/lora_settings.py).
const AIR_DATA_RATES_KBPS = [0.3, 1.2, 2.4, 4.8, 9.6, 19.2];

const loaded = ref(false);
const saving = ref(false);
const error = ref<string | null>(null);
const savedAt = ref<string | null>(null);

const form = reactive({
  is_active: false,
  channel: 0,
  speed: 0,
  fec: true,
  ping_interval_s: 5,
  clock_interval_s: 60,
  relaystrio_recurring_threshold_days: 2,
});

function applySettings(settings: LoraSettingsPublic) {
  form.is_active = settings.is_active;
  form.channel = settings.channel;
  form.speed = settings.speed;
  form.fec = settings.fec;
  form.ping_interval_s = settings.ping_interval_s;
  form.clock_interval_s = settings.clock_interval_s;
  form.relaystrio_recurring_threshold_days = settings.relaystrio_recurring_threshold_days;
}

onMounted(async () => {
  try {
    applySettings(await loraSettingsApi.get());
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loaded.value = true;
  }
});

async function save() {
  error.value = null;
  savedAt.value = null;
  saving.value = true;
  try {
    const updated = await loraSettingsApi.update({ ...form });
    applySettings(updated);
    savedAt.value = updated.updated_at;
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    saving.value = false;
  }
}
</script>

<template>
  <div v-if="loaded" class="lora-settings">
    <p class="warning">
      Ces réglages radio (canal, vitesse, FEC) doivent être identiques sur
      <strong>tous les appareils</strong> du réseau (master et chaque
      lumestrio) pour qu'ils puissent s'entendre entre eux — ils ne sont
      pas synchronisés automatiquement via LoRa. Les autres réglages
      (activité, intervalles, seuil relaystrio) ne concernent que cet
      appareil master.
    </p>
    <form class="settings-form" @submit.prevent="save">
      <label class="option-status">
        <input v-model="form.is_active" type="checkbox" />
        Réseau LoRa actif (envoi des PING / synchronisation d'horloge)
      </label>

      <label>
        Canal radio
        <input v-model.number="form.channel" type="number" min="0" max="54" required />
      </label>

      <label>
        Vitesse radio
        <select v-model.number="form.speed">
          <option v-for="(kbps, index) in AIR_DATA_RATES_KBPS" :key="index" :value="index">
            {{ kbps }} kbps
          </option>
        </select>
      </label>

      <label class="option-status">
        <input v-model="form.fec" type="checkbox" />
        FEC (correction d'erreur)
      </label>

      <label>
        Intervalle de ping (secondes)
        <input v-model.number="form.ping_interval_s" type="number" min="1" required />
      </label>

      <label>
        Intervalle de synchronisation d'horloge (secondes)
        <input v-model.number="form.clock_interval_s" type="number" min="1" required />
      </label>

      <label>
        Seuil "récurrent" pour les presets relaystrio (jours)
        <input
          v-model.number="form.relaystrio_recurring_threshold_days"
          type="number"
          min="1"
          required
        />
      </label>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="savedAt" class="saved-hint">Enregistré ({{ savedAt }}).</p>

      <div class="form-actions">
        <button type="submit" :disabled="saving">Enregistrer</button>
      </div>
    </form>
  </div>
</template>

<style scoped>
.lora-settings {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  max-width: 480px;
}

.warning {
  background: var(--color-warning-bg);
  border: 1px solid var(--color-warning-border);
  border-radius: 4px;
  padding: 0.75rem 1rem;
  margin: 0;
  font-size: 0.9rem;
}

.settings-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.settings-form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.settings-form label.option-status {
  flex-direction: row;
  align-items: center;
}

.error {
  color: red;
}

.saved-hint {
  color: var(--color-muted);
  font-size: 0.85rem;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
}
</style>
