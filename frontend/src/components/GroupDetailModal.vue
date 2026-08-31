<script setup lang="ts">
import type { GroupPublic } from "@/api/types";

defineProps<{
  group: GroupPublic;
  calendarLabel: string | null;
}>();

const emit = defineEmits<{
  close: [];
  "open-calendar": [];
}>();
</script>

<template>
  <div class="modal-backdrop" @click.self="emit('close')">
    <div class="modal">
      <button type="button" class="modal-close" aria-label="Fermer" @click="emit('close')">
        ✕
      </button>
      <h2>{{ group.label }}</h2>
      <dl class="detail-list">
        <dt>UUID</dt>
        <dd>{{ group.uuid }}</dd>
        <dt>Calendrier</dt>
        <dd>
          <a
            v-if="group.calendar_id && calendarLabel"
            href="#"
            class="item-link"
            @click.prevent="emit('open-calendar')"
          >
            {{ calendarLabel }}
          </a>
          <span v-else>—</span>
        </dd>
        <dt>Appareils</dt>
        <dd>
          <span v-if="group.devices.length === 0">—</span>
          <ul v-else class="device-list">
            <li v-for="device in group.devices" :key="device.uuid">
              {{ device.device_name }}
            </li>
          </ul>
        </dd>
        <dt>Dernière modification</dt>
        <dd>{{ group.updated_at }}</dd>
      </dl>
    </div>
  </div>
</template>

<style scoped>
.device-list {
  margin: 0;
  padding-left: 1.25rem;
}
</style>
