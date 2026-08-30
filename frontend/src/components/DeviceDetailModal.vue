<script setup lang="ts">
import type { DevicePublic } from "@/api/types";

defineProps<{
  device: DevicePublic;
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
      <h2>{{ device.device_name }}</h2>
      <dl class="detail-list">
        <dt>Nom de série</dt>
        <dd>{{ device.device_id }}</dd>
        <dt>Type d'appareil</dt>
        <dd>{{ device.device_type }}</dd>
        <dt>UUID</dt>
        <dd>{{ device.uuid }}</dd>
        <dt>Actif</dt>
        <dd>{{ device.active ? "ON" : "OFF" }}</dd>
        <dt>Maître</dt>
        <dd>{{ device.is_master ? "Oui" : "Non" }}</dd>
        <template v-if="device.device_type === 'lumestrio'">
          <dt>Options</dt>
          <dd class="options-row">
            <span class="option-status">
              <span :class="device.handles_audio ? 'icon-ok' : 'icon-ko'">
                {{ device.handles_audio ? "✓" : "✗" }}
              </span>
              Audio
            </span>
            <span class="option-status">
              <span :class="device.handles_dmx ? 'icon-ok' : 'icon-ko'">
                {{ device.handles_dmx ? "✓" : "✗" }}
              </span>
              DMX
            </span>
          </dd>
        </template>
        <dt>Calendrier</dt>
        <dd>
          <a
            v-if="device.calendar"
            href="#"
            class="item-link"
            @click.prevent="emit('open-calendar')"
          >
            {{ device.calendar.label }}
          </a>
          <span v-else>—</span>
        </dd>
        <dt>IP</dt>
        <dd>{{ device.ip ?? "—" }}</dd>
        <dt>IP du master</dt>
        <dd>{{ device.master_ip ?? "—" }}</dd>
        <dt>Fichier audio</dt>
        <dd>{{ device.audiofile ?? "—" }}</dd>
        <dt>Dernière modification</dt>
        <dd>{{ device.updated_at }}</dd>
      </dl>
    </div>
  </div>
</template>
