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
  await calendarsApi.create({ label: newCalendarLabel.value });
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
    <button :disabled="selectedUuids.size === 0" @click="removeSelectedCalendars">
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
        <td>{{ calendar.label }}</td>
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

.note {
  color: #666;
  font-style: italic;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal {
  background: white;
  padding: 1.5rem;
  border-radius: 6px;
  min-width: 320px;
}

.modal-actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 1rem;
}
</style>
