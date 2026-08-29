<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import { calendarsApi } from "@/api/calendars";
import type { CalendarPublic } from "@/api/types";

const calendars = ref<CalendarPublic[]>([]);
const newCalendarLabel = ref("");
const selectedUuids = ref<Set<string>>(new Set());

const duplicateModalOpen = ref(false);
const duplicateSourceUuid = ref("");
const duplicateLabel = ref("");

const detailModalOpen = ref(false);
const detailCalendar = ref<CalendarPublic | null>(null);

const allSelected = computed(
  () => calendars.value.length > 0 && selectedUuids.value.size === calendars.value.length,
);

async function loadCalendars() {
  const result = await calendarsApi.list();
  calendars.value = result.data;
  selectedUuids.value = new Set(
    [...selectedUuids.value].filter((uuid) => calendars.value.some((c) => c.uuid === uuid)),
  );
}

async function createCalendar() {
  await calendarsApi.create({ label: newCalendarLabel.value, presets: {}, days: {} });
  newCalendarLabel.value = "";
  await loadCalendars();
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
    : new Set(calendars.value.map((c) => c.uuid));
}

async function removeSelectedCalendars() {
  await calendarsApi.delete([...selectedUuids.value]);
  await loadCalendars();
}

async function openDetailModal(uuid: string) {
  detailCalendar.value = await calendarsApi.get(uuid);
  detailModalOpen.value = true;
}

function closeDetailModal() {
  detailModalOpen.value = false;
}

function openDuplicateModal(calendar: CalendarPublic) {
  duplicateSourceUuid.value = calendar.uuid;
  duplicateLabel.value = `${calendar.label} copy`;
  duplicateModalOpen.value = true;
}

function closeDuplicateModal() {
  duplicateModalOpen.value = false;
}

async function confirmDuplicate() {
  const duplicated = await calendarsApi.duplicate(duplicateSourceUuid.value);
  await calendarsApi.update(duplicated.uuid, { label: duplicateLabel.value });
  duplicateModalOpen.value = false;
  await loadCalendars();
}

onMounted(loadCalendars);
</script>

<template>
  <h1>Je gère les calendriers</h1>

  <form class="create-form" @submit.prevent="createCalendar">
    <input v-model="newCalendarLabel" placeholder="Nom du calendrier" required />
    <button type="submit">Créer un calendrier</button>
  </form>

  <div class="bulk-actions">
    <button class="clear-selection" :disabled="selectedUuids.size === 0" @click="removeSelectedCalendars">
      Effacer la sélection ({{ selectedUuids.size }})
    </button>
  </div>

  <table>
    <thead>
      <tr>
        <th>
          <input type="checkbox" :checked="allSelected" @change="toggleSelectAll" />
        </th>
        <th>Nom du calendrier</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="calendar in calendars" :key="calendar.uuid">
        <td>
          <input
            type="checkbox"
            :checked="selectedUuids.has(calendar.uuid)"
            @change="toggleSelection(calendar.uuid)"
          />
        </td>
        <td>
          <a href="#" class="item-link" @click.prevent="openDetailModal(calendar.uuid)">
            {{ calendar.label }}
          </a>
        </td>
        <td>
          <button @click="openDuplicateModal(calendar)">Dupliquer</button>
        </td>
      </tr>
    </tbody>
  </table>

  <p class="note">
    L'édition des jours type / exceptions / plages horaires arrivera dans une
    prochaine itération.
  </p>

  <div v-if="duplicateModalOpen" class="modal-backdrop" @click.self="closeDuplicateModal">
    <div class="modal">
      <h2>Dupliquer le calendrier</h2>
      <form @submit.prevent="confirmDuplicate">
        <input v-model="duplicateLabel" placeholder="Nom du calendrier" required />
        <div class="modal-actions">
          <button type="button" @click="closeDuplicateModal">Annuler</button>
          <button type="submit">Mettre à jour</button>
        </div>
      </form>
    </div>
  </div>

  <div v-if="detailModalOpen" class="modal-backdrop" @click.self="closeDetailModal">
    <div class="modal" v-if="detailCalendar">
      <button type="button" class="modal-close" aria-label="Fermer" @click="closeDetailModal">
        ✕
      </button>
      <h2>{{ detailCalendar.label }}</h2>
      <dl class="detail-list">
        <dt>UUID</dt>
        <dd>{{ detailCalendar.uuid }}</dd>
        <dt>Dernière modification</dt>
        <dd>{{ detailCalendar.updated_at }}</dd>
        <dt>Jours type</dt>
        <dd><pre>{{ JSON.stringify(detailCalendar.days, null, 2) }}</pre></dd>
        <dt>Presets</dt>
        <dd><pre>{{ JSON.stringify(detailCalendar.presets, null, 2) }}</pre></dd>
      </dl>
    </div>
  </div>
</template>

<style scoped>
.clear-selection:disabled {
  color: var(--color-disabled-text);
}

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
  border-bottom: 1px solid var(--color-border);
}

.note {
  color: var(--color-muted);
  font-style: italic;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: var(--color-backdrop);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal {
  position: relative;
  background: var(--color-surface);
  color: var(--color-text);
  padding: 1.5rem;
  border-radius: 6px;
  min-width: 320px;
}

.modal-close {
  position: absolute;
  top: 0.5rem;
  right: 0.5rem;
  background: none;
  border: none;
  color: var(--color-close-icon);
  font-size: 1.1rem;
  line-height: 1;
  cursor: pointer;
  padding: 0.25rem;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}

.item-link {
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
}

.detail-list {
  max-width: 480px;
}

.detail-list dt {
  font-weight: bold;
  margin-top: 0.75rem;
}

.detail-list dd {
  margin: 0.25rem 0 0;
}

.detail-list pre {
  background: var(--color-surface-alt);
  padding: 0.5rem;
  border-radius: 4px;
  overflow-x: auto;
}
</style>
