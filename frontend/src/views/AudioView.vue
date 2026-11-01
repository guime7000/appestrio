<script setup lang="ts">
import { onMounted, ref } from "vue";

import { audioApi } from "@/api/audio";
import type { AudioStatusPublic } from "@/api/types";

const loaded = ref(false);
const handlesAudio = ref(false);
const audiofile = ref<string | null>(null);
const testAudiofile = ref<string | null>(null);
const volume = ref(100);
const loop = ref(false);
const playing = ref(false);
const busy = ref(false);
const uploading = ref(false);
const uploadingTest = ref(false);
const error = ref<string | null>(null);

function applyStatus(status: AudioStatusPublic) {
  handlesAudio.value = status.handles_audio;
  audiofile.value = status.audiofile;
  testAudiofile.value = status.test_audiofile;
  volume.value = status.volume;
  loop.value = status.loop;
  playing.value = status.playing;
}

onMounted(async () => {
  try {
    applyStatus(await audioApi.status());
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loaded.value = true;
  }
});

async function play() {
  if (busy.value) return;
  busy.value = true;
  error.value = null;
  try {
    applyStatus(await audioApi.play());
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    busy.value = false;
  }
}

async function playTest() {
  if (busy.value) return;
  busy.value = true;
  error.value = null;
  try {
    applyStatus(await audioApi.playTest());
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    busy.value = false;
  }
}

async function stop() {
  if (busy.value) return;
  busy.value = true;
  error.value = null;
  try {
    applyStatus(await audioApi.stop());
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    busy.value = false;
  }
}

// Live-updates the slider locally for a responsive feel, but the actual
// persisted/applied value is always whatever the backend echoes back.
async function onVolumeChange() {
  error.value = null;
  try {
    applyStatus(await audioApi.setVolume(volume.value));
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  }
}

async function onLoopChange() {
  error.value = null;
  try {
    applyStatus(await audioApi.setLoop(loop.value));
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  }
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploading.value = true;
  error.value = null;
  try {
    applyStatus(await audioApi.upload(file));
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    uploading.value = false;
    input.value = "";
  }
}

async function onTestFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploadingTest.value = true;
  error.value = null;
  try {
    applyStatus(await audioApi.uploadTest(file));
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    uploadingTest.value = false;
    input.value = "";
  }
}
</script>

<template>
  <div v-if="loaded" class="audio">
    <p class="warning">
      Page de configuration/test du lecteur audio de cet appareil — à
      utiliser lorsque l'appareil est éteint manuellement. Le volume
      réglé ici est mémorisé pour les prochaines lectures.
    </p>

    <p v-if="!handlesAudio" class="error">
      Cet appareil ne gère pas la lecture audio.
    </p>

    <template v-else>
      <section class="upload-section">
        <h2>Fichier audio</h2>
        <p v-if="audiofile">Fichier actuel : <strong>{{ audiofile }}</strong></p>
        <p v-else>Aucun fichier envoyé pour le moment.</p>
        <label class="upload-button">
          {{ uploading ? "Envoi en cours…" : "Envoyer un fichier" }}
          <input
            type="file"
            accept=".mp3,.wav,.ogg,.flac,.m4a"
            :disabled="uploading"
            @change="onFileSelected"
          />
        </label>
      </section>

      <section class="upload-section">
        <h2>Son test</h2>
        <p v-if="testAudiofile">Son test actuel : <strong>{{ testAudiofile }}</strong></p>
        <p v-else>Aucun son test envoyé pour le moment.</p>
        <label class="upload-button">
          {{ uploadingTest ? "Envoi en cours…" : "Envoyer un son test" }}
          <input
            type="file"
            accept=".mp3,.wav,.ogg,.flac,.m4a"
            :disabled="uploadingTest"
            @change="onTestFileSelected"
          />
        </label>
      </section>

      <section class="playback-section">
        <h2>Lecture</h2>
        <div class="playback-controls">
          <button type="button" :disabled="busy || !audiofile" @click="play">
            ▶ Lecture
          </button>
          <button type="button" :disabled="busy || !testAudiofile" @click="playTest">
            ▶ Son test
          </button>
          <button type="button" :disabled="busy || !playing" @click="stop">
            ⏹ Stop
          </button>
          <span class="playback-status">{{ playing ? "En cours de lecture" : "Arrêté" }}</span>
        </div>

        <label class="volume-control">
          Volume ({{ volume }})
          <input
            v-model.number="volume"
            type="range"
            min="0"
            max="100"
            @change="onVolumeChange"
          />
        </label>

        <label class="option-status">
          <input v-model="loop" type="checkbox" @change="onLoopChange" />
          Lire en boucle
        </label>
      </section>
    </template>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.audio {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
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

.upload-section,
.playback-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.upload-button {
  display: inline-block;
  width: fit-content;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: var(--color-surface-alt);
  cursor: pointer;
}

.upload-button input[type="file"] {
  display: none;
}

.playback-controls {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.playback-status {
  color: var(--color-muted);
  font-size: 0.9rem;
}

.volume-control {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.error {
  color: red;
}
</style>
