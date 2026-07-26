<script setup lang="ts">
import { onMounted, ref } from "vue";

import { calendarsApi } from "@/api/calendars";
import type { CalendarPublic } from "@/api/types";

const calendars = ref<CalendarPublic[]>([]);
const newCalendarLabel = ref("");

async function loadCalendars() {
  const result = await calendarsApi.list();
  calendars.value = result.data;
}

async function createCalendar() {
  await calendarsApi.create({ label: newCalendarLabel.value });
  newCalendarLabel.value = "";
  await loadCalendars();
}

async function removeCalendar(uuid: string) {
  await calendarsApi.delete(uuid);
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

  <table>
    <thead>
      <tr>
        <th>Nom du calendrier</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="calendar in calendars" :key="calendar.uuid">
        <td>{{ calendar.label }}</td>
        <td><button @click="removeCalendar(calendar.uuid)">Effacer</button></td>
      </tr>
    </tbody>
  </table>

  <p class="note">
    L'édition des jours type / exceptions / plages horaires arrivera dans une
    prochaine itération.
  </p>
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
</style>
