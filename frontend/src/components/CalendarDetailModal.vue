<script setup lang="ts">
import type { CalendarPublic } from "@/api/types";
import { weekdayLabels } from "@/utils/weekdays";

defineProps<{
  calendar: CalendarPublic;
}>();

const emit = defineEmits<{
  close: [];
}>();
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal">
      <button type="button" class="modal-close" aria-label="Fermer" @click="emit('close')">
        ✕
      </button>
      <h2>{{ calendar.label }}</h2>
      <dl class="detail-list">
        <dt>UUID</dt>
        <dd>{{ calendar.uuid }}</dd>
        <dt>Jours d'application</dt>
        <dd>{{ weekdayLabels(calendar.weekdays) }}</dd>
        <dt>Allumages</dt>
        <dd>
          <span v-if="calendar.ignition_presets.length === 0">—</span>
          <ul v-else class="preset-list">
            <li v-for="preset in calendar.ignition_presets" :key="preset.uuid">
              {{ preset.name }} ({{ preset.start_date }} → {{ preset.stop_date }},
              {{ preset.start_time }}-{{ preset.stop_time }})
            </li>
          </ul>
        </dd>
        <dt>Dernière modification</dt>
        <dd>{{ calendar.updated_at }}</dd>
      </dl>
    </div>
  </div>
</template>

<style scoped>
.preset-list {
  margin: 0;
  padding-left: 1.25rem;
}
</style>
