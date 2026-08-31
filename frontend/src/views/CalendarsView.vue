<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";

import { calendarsApi } from "@/api/calendars";
import { ignitionPresetsApi } from "@/api/ignitionPresets";
import type {
  CalendarPublic,
  CalendarSummaryPublic,
  IgnitionPresetPublic,
  Weekday,
} from "@/api/types";

const WEEKDAY_OPTIONS: { value: Weekday; label: string }[] = [
  { value: 1, label: "Lundi" },
  { value: 2, label: "Mardi" },
  { value: 3, label: "Mercredi" },
  { value: 4, label: "Jeudi" },
  { value: 5, label: "Vendredi" },
  { value: 6, label: "Samedi" },
  { value: 7, label: "Dimanche" },
];

const DATE_PATTERN = /^\d{2}\/\d{2}\/\d{4}$/;
const TIME_PATTERN = /^\d{2}:\d{2}$/;

// Native <input type="date"> always works in ISO (YYYY-MM-DD), but the
// backend stores/expects DD/MM/YYYY -- these convert at the form boundary.
function toIsoDate(ddMmYyyy: string): string {
  const [day, month, year] = ddMmYyyy.split("/");
  return day && month && year ? `${year}-${month}-${day}` : "";
}

function fromIsoDate(isoDate: string): string {
  const [year, month, day] = isoDate.split("-");
  return day && month && year ? `${day}/${month}/${year}` : "";
}

const calendars = ref<CalendarSummaryPublic[]>([]);
const selectedCalendarUuids = ref<Set<string>>(new Set());
const activeCalendarUuid = ref<string | null>(null);
const activeCalendar = ref<CalendarPublic | null>(null);

const allSelected = computed(
  () =>
    calendars.value.length > 0 && selectedCalendarUuids.value.size === calendars.value.length,
);

async function loadCalendars() {
  const result = await calendarsApi.list();
  calendars.value = result.data;
  selectedCalendarUuids.value = new Set(
    [...selectedCalendarUuids.value].filter((uuid) =>
      calendars.value.some((c) => c.uuid === uuid),
    ),
  );
  if (
    activeCalendarUuid.value &&
    !calendars.value.some((c) => c.uuid === activeCalendarUuid.value)
  ) {
    activeCalendarUuid.value = null;
    activeCalendar.value = null;
  }
}

async function selectCalendar(uuid: string) {
  activeCalendarUuid.value = uuid;
  activeCalendar.value = await calendarsApi.get(uuid);
}

async function refreshActiveCalendar() {
  if (activeCalendarUuid.value) {
    activeCalendar.value = await calendarsApi.get(activeCalendarUuid.value);
  }
}

function weekdayLabels(weekdays: Weekday[]): string {
  if (weekdays.length === 0) return "—";
  return WEEKDAY_OPTIONS.filter((option) => weekdays.includes(option.value))
    .map((option) => option.label)
    .join(", ");
}

function toggleCalendarSelection(uuid: string) {
  if (selectedCalendarUuids.value.has(uuid)) {
    selectedCalendarUuids.value.delete(uuid);
  } else {
    selectedCalendarUuids.value.add(uuid);
  }
}

function toggleSelectAllCalendars() {
  selectedCalendarUuids.value = allSelected.value
    ? new Set()
    : new Set(calendars.value.map((c) => c.uuid));
}

async function removeSelectedCalendars() {
  await calendarsApi.delete([...selectedCalendarUuids.value]);
  await loadCalendars();
}

// --- Calendar create/edit ---
const calendarFormModalOpen = ref(false);
const calendarFormError = ref<string | null>(null);
const editingCalendarUuid = ref<string | null>(null);
const calendarForm = reactive({
  label: "",
  weekdays: [] as Weekday[],
});

function toggleWeekday(value: Weekday) {
  const index = calendarForm.weekdays.indexOf(value);
  if (index === -1) {
    calendarForm.weekdays.push(value);
  } else {
    calendarForm.weekdays.splice(index, 1);
  }
}

function openCreateCalendarModal() {
  calendarFormError.value = null;
  editingCalendarUuid.value = null;
  calendarForm.label = "";
  calendarForm.weekdays = [];
  calendarFormModalOpen.value = true;
}

function openEditCalendarModal(calendar: CalendarPublic) {
  calendarFormError.value = null;
  editingCalendarUuid.value = calendar.uuid;
  calendarForm.label = calendar.label;
  calendarForm.weekdays = [...calendar.weekdays];
  calendarFormModalOpen.value = true;
}

async function editCalendar(uuid: string) {
  openEditCalendarModal(await calendarsApi.get(uuid));
}

function closeCalendarFormModal() {
  calendarFormModalOpen.value = false;
}

async function submitCalendarForm() {
  calendarFormError.value = null;
  if (!calendarForm.label.trim()) {
    calendarFormError.value = "Le nom du calendrier est obligatoire.";
    return;
  }
  const payload = {
    label: calendarForm.label.trim(),
    weekdays: calendarForm.weekdays,
  };
  try {
    if (editingCalendarUuid.value) {
      await calendarsApi.update(editingCalendarUuid.value, payload);
    } else {
      await calendarsApi.create(payload);
    }
    calendarFormModalOpen.value = false;
    await loadCalendars();
    await refreshActiveCalendar();
  } catch (err) {
    calendarFormError.value = err instanceof Error ? err.message : String(err);
  }
}

// --- Duplicate calendar ---
const duplicateModalOpen = ref(false);
const duplicateSourceUuid = ref("");
const duplicateLabel = ref("");

function openDuplicateModal(calendar: CalendarSummaryPublic) {
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

// --- Ignition preset (Allumage) create/edit/delete ---
const presetFormModalOpen = ref(false);
const presetFormError = ref<string | null>(null);
const editingPresetUuid = ref<string | null>(null);
const presetForm = reactive({
  name: "",
  description: "",
  start_date: "",
  stop_date: "",
  start_time: "",
  stop_time: "",
  calendar_id: "",
});

// Bound by the native date pickers in the template; presetForm.start_date/
// stop_date stay in DD/MM/YYYY, matching what the API sends and expects.
const presetStartDateIso = computed({
  get: () => toIsoDate(presetForm.start_date),
  set: (value: string) => {
    presetForm.start_date = fromIsoDate(value);
  },
});
const presetStopDateIso = computed({
  get: () => toIsoDate(presetForm.stop_date),
  set: (value: string) => {
    presetForm.stop_date = fromIsoDate(value);
  },
});

function openCreatePresetModal() {
  if (!activeCalendarUuid.value) return;
  presetFormError.value = null;
  editingPresetUuid.value = null;
  presetForm.name = "";
  presetForm.description = "";
  presetForm.start_date = "";
  presetForm.stop_date = "";
  presetForm.start_time = "";
  presetForm.stop_time = "";
  presetForm.calendar_id = activeCalendarUuid.value;
  presetFormModalOpen.value = true;
}

function openEditPresetModal(preset: IgnitionPresetPublic) {
  presetFormError.value = null;
  editingPresetUuid.value = preset.uuid;
  presetForm.name = preset.name;
  presetForm.description = preset.description ?? "";
  presetForm.start_date = preset.start_date;
  presetForm.stop_date = preset.stop_date;
  presetForm.start_time = preset.start_time;
  presetForm.stop_time = preset.stop_time;
  presetForm.calendar_id = preset.calendar_id;
  presetFormModalOpen.value = true;
}

function closePresetFormModal() {
  presetFormModalOpen.value = false;
}

async function submitPresetForm() {
  presetFormError.value = null;
  if (!presetForm.name.trim()) {
    presetFormError.value = "Le nom est obligatoire.";
    return;
  }
  if (!DATE_PATTERN.test(presetForm.start_date) || !DATE_PATTERN.test(presetForm.stop_date)) {
    presetFormError.value = "Les dates doivent être au format JJ/MM/AAAA.";
    return;
  }
  if (!TIME_PATTERN.test(presetForm.start_time) || !TIME_PATTERN.test(presetForm.stop_time)) {
    presetFormError.value = "Les heures doivent être au format HH:MM.";
    return;
  }
  const payload = {
    name: presetForm.name.trim(),
    description: presetForm.description.trim() || null,
    start_date: presetForm.start_date,
    stop_date: presetForm.stop_date,
    start_time: presetForm.start_time,
    stop_time: presetForm.stop_time,
    calendar_id: presetForm.calendar_id,
  };
  try {
    if (editingPresetUuid.value) {
      await ignitionPresetsApi.update(editingPresetUuid.value, payload);
    } else {
      await ignitionPresetsApi.create(payload);
    }
    presetFormModalOpen.value = false;
    await refreshActiveCalendar();
  } catch (err) {
    presetFormError.value = err instanceof Error ? err.message : String(err);
  }
}

async function deletePreset(uuid: string) {
  await ignitionPresetsApi.delete([uuid]);
  await refreshActiveCalendar();
}

onMounted(loadCalendars);
</script>

<template>
  <h1>Je gère les calendriers</h1>

  <div class="calendars-layout">
    <section class="calendars-panel">
      <h2>Calendriers</h2>
      <div class="bulk-actions">
        <button type="button" @click="openCreateCalendarModal">Créer un calendrier</button>
        <button
          class="clear-selection"
          :disabled="selectedCalendarUuids.size === 0"
          @click="removeSelectedCalendars"
        >
          Effacer la sélection ({{ selectedCalendarUuids.size }})
        </button>
      </div>

      <table>
        <thead>
          <tr>
            <th>
              <input type="checkbox" :checked="allSelected" @change="toggleSelectAllCalendars" />
            </th>
            <th>Nom du calendrier</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="calendar in calendars"
            :key="calendar.uuid"
            :class="{ 'active-row': calendar.uuid === activeCalendarUuid }"
          >
            <td>
              <input
                type="checkbox"
                :checked="selectedCalendarUuids.has(calendar.uuid)"
                @change="toggleCalendarSelection(calendar.uuid)"
              />
            </td>
            <td>
              <a href="#" class="item-link" @click.prevent="selectCalendar(calendar.uuid)">
                {{ calendar.label }}
              </a>
            </td>
            <td class="row-actions">
              <button type="button" @click="editCalendar(calendar.uuid)">Modifier</button>
              <button type="button" @click="openDuplicateModal(calendar)">Dupliquer</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="presets-panel">
      <template v-if="activeCalendar">
        <h2>Allumages — {{ activeCalendar.label }}</h2>
        <p class="note">Jours d'application : {{ weekdayLabels(activeCalendar.weekdays) }}</p>

        <div class="bulk-actions">
          <button type="button" @click="openCreatePresetModal">Créer un allumage</button>
        </div>

        <table>
          <thead>
            <tr>
              <th>Nom</th>
              <th>Début</th>
              <th>Fin</th>
              <th>Horaires</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="preset in activeCalendar.ignition_presets" :key="preset.uuid">
              <td>{{ preset.name }}</td>
              <td>{{ preset.start_date }}</td>
              <td>{{ preset.stop_date }}</td>
              <td>{{ preset.start_time }} - {{ preset.stop_time }}</td>
              <td class="row-actions">
                <button type="button" @click="openEditPresetModal(preset)">Modifier</button>
                <button type="button" @click="deletePreset(preset.uuid)">Supprimer</button>
              </td>
            </tr>
            <tr v-if="activeCalendar.ignition_presets.length === 0">
              <td colspan="5" class="note">Aucun allumage pour ce calendrier.</td>
            </tr>
          </tbody>
        </table>
      </template>
      <p v-else class="note">
        Sélectionnez un calendrier à gauche pour gérer ses allumages.
      </p>
    </section>
  </div>

  <div v-if="calendarFormModalOpen" class="modal-backdrop" @click.self="closeCalendarFormModal">
    <div class="modal">
      <button
        type="button"
        class="modal-close"
        aria-label="Fermer"
        @click="closeCalendarFormModal"
      >
        ✕
      </button>
      <h2>{{ editingCalendarUuid ? "Modifier le calendrier" : "Créer un calendrier" }}</h2>
      <p class="mandatory-hint">* Champ obligatoire</p>
      <form class="calendar-form" @submit.prevent="submitCalendarForm">
        <label>
          Nom du calendrier <span class="mandatory">*</span>
          <input v-model="calendarForm.label" required />
        </label>
        <fieldset class="weekday-fieldset">
          <legend>Jours d'application</legend>
          <label v-for="option in WEEKDAY_OPTIONS" :key="option.value" class="checkbox-label">
            <input
              type="checkbox"
              :checked="calendarForm.weekdays.includes(option.value)"
              @change="toggleWeekday(option.value)"
            />
            {{ option.label }}
          </label>
        </fieldset>
        <p v-if="calendarFormError" class="error">{{ calendarFormError }}</p>
        <div class="modal-actions">
          <button type="button" @click="closeCalendarFormModal">Annuler</button>
          <button type="submit">{{ editingCalendarUuid ? "Mettre à jour" : "Enregistrer" }}</button>
        </div>
      </form>
    </div>
  </div>

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

  <div v-if="presetFormModalOpen" class="modal-backdrop" @click.self="closePresetFormModal">
    <div class="modal">
      <button type="button" class="modal-close" aria-label="Fermer" @click="closePresetFormModal">
        ✕
      </button>
      <h2>{{ editingPresetUuid ? "Modifier l'allumage" : "Créer un allumage" }}</h2>
      <p class="mandatory-hint">* Champ obligatoire</p>
      <form class="preset-form" @submit.prevent="submitPresetForm">
        <label>
          Nom <span class="mandatory">*</span>
          <input v-model="presetForm.name" required />
        </label>
        <label>
          Description
          <input v-model="presetForm.description" />
        </label>
        <label>
          Date de début <span class="mandatory">*</span>
          <input type="date" v-model="presetStartDateIso" required />
        </label>
        <label>
          Date de fin <span class="mandatory">*</span>
          <input type="date" v-model="presetStopDateIso" required />
        </label>
        <label>
          Heure de début <span class="mandatory">*</span>
          <input type="time" v-model="presetForm.start_time" required />
        </label>
        <label>
          Heure de fin <span class="mandatory">*</span>
          <input type="time" v-model="presetForm.stop_time" required />
        </label>
        <label v-if="editingPresetUuid">
          Calendrier
          <select v-model="presetForm.calendar_id">
            <option v-for="calendar in calendars" :key="calendar.uuid" :value="calendar.uuid">
              {{ calendar.label }}
            </option>
          </select>
        </label>
        <p v-if="presetFormError" class="error">{{ presetFormError }}</p>
        <div class="modal-actions">
          <button type="button" @click="closePresetFormModal">Annuler</button>
          <button type="submit">{{ editingPresetUuid ? "Mettre à jour" : "Enregistrer" }}</button>
        </div>
      </form>
    </div>
  </div>
</template>

<style scoped>
.calendars-layout {
  display: flex;
  gap: 1.5rem;
  align-items: flex-start;
}

.calendars-panel {
  flex: 1 1 40%;
  min-width: 320px;
}

.presets-panel {
  flex: 1 1 60%;
  min-width: 320px;
}

@media (max-width: 900px) {
  .calendars-layout {
    flex-direction: column;
  }
}

.bulk-actions {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1rem;
  flex-wrap: wrap;
}

.clear-selection:disabled {
  color: var(--color-disabled-text);
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

.active-row {
  background: var(--color-surface-alt);
}

.row-actions {
  display: flex;
  gap: 0.5rem;
}

.note {
  color: var(--color-muted);
  font-style: italic;
}

.item-link {
  color: inherit;
  text-decoration: underline;
  cursor: pointer;
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

.mandatory-hint {
  color: var(--color-muted);
  font-size: 0.85rem;
  font-style: italic;
  margin-top: -0.5rem;
}

.mandatory {
  color: #c00;
}

.error {
  color: red;
}

.calendar-form,
.preset-form {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  min-width: 320px;
}

.calendar-form label,
.preset-form label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.weekday-fieldset {
  border: 1px solid var(--color-border);
  border-radius: 4px;
  padding: 0.5rem 0.75rem;
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
}

.weekday-fieldset legend {
  font-size: 0.85rem;
  padding: 0 0.25rem;
}

.checkbox-label {
  display: flex;
  flex-direction: row;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.9rem;
}

</style>
