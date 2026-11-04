<script setup lang="ts">
import { onMounted, ref } from "vue";

import { audioApi } from "@/api/audio";
import { dmxApi } from "@/api/dmx";
import type { AudioStatusPublic } from "@/api/types";

const loaded = ref(false);
const handlesAudio = ref(false);
const handlesDmx = ref(false);

const audiofile = ref<string | null>(null);
const testAudiofile = ref<string | null>(null);

const uploadingAudio = ref(false);
const uploadingTest = ref(false);
const uploadingQlc = ref(false);

const error = ref<string | null>(null);
const qlcMessage = ref<string | null>(null);

function applyAudioStatus(status: AudioStatusPublic) {
  handlesAudio.value = status.handles_audio;
  audiofile.value = status.audiofile;
  testAudiofile.value = status.test_audiofile;
}

onMounted(async () => {
  try {
    const [audioStatus, dmxStatus] = await Promise.all([
      audioApi.status(),
      dmxApi.status(),
    ]);
    applyAudioStatus(audioStatus);
    handlesDmx.value = dmxStatus.handles_dmx;
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    loaded.value = true;
  }
});

async function onAudioFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  uploadingAudio.value = true;
  error.value = null;
  try {
    applyAudioStatus(await audioApi.upload(file));
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    uploadingAudio.value = false;
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
    applyAudioStatus(await audioApi.uploadTest(file));
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    uploadingTest.value = false;
    input.value = "";
  }
}

async function onQlcFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const files = input.files ? Array.from(input.files) : [];
  if (files.length === 0) return;
  uploadingQlc.value = true;
  error.value = null;
  qlcMessage.value = null;
  try {
    const result = await dmxApi.upload(files);
    qlcMessage.value = result.message;
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err);
  } finally {
    uploadingQlc.value = false;
    input.value = "";
  }
}
</script>

<template>
  <div v-if="loaded" class="upload">
    <h1>Upload</h1>
    <p class="warning">
      Envoi des fichiers utilisés par cet appareil : fichier audio
      principal, son de test, et projet/fixtures QLC+.
    </p>

    <p v-if="!handlesAudio && !handlesDmx" class="error">
      Cet appareil ne gère ni l'audio ni le DMX — rien à envoyer ici.
    </p>

    <section v-if="handlesAudio" class="upload-section">
      <h2>Fichier audio</h2>
      <p v-if="audiofile">Fichier actuel : <strong>{{ audiofile }}</strong></p>
      <p v-else>Aucun fichier envoyé pour le moment.</p>
      <label class="upload-button">
        {{ uploadingAudio ? "Envoi en cours…" : "Envoyer un fichier" }}
        <input
          type="file"
          accept=".mp3,.wav,.ogg,.flac,.m4a"
          :disabled="uploadingAudio"
          @change="onAudioFileSelected"
        />
      </label>
    </section>

    <section v-if="handlesAudio" class="upload-section">
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

    <section v-if="handlesDmx" class="upload-section">
      <h2>Projet QLC+</h2>
      <p>
        Sélectionnez le fichier projet (.qxw) et/ou les fixtures
        personnalisées (.qxf) à envoyer — un nouveau projet remplace
        l'actuel. Les fixtures sont prises en compte au prochain
        redémarrage de QLC+.
      </p>
      <label class="upload-button">
        {{ uploadingQlc ? "Envoi en cours…" : "Envoyer projet / fixtures" }}
        <input
          type="file"
          accept=".qxw,.qxf"
          multiple
          :disabled="uploadingQlc"
          @change="onQlcFilesSelected"
        />
      </label>
      <p v-if="qlcMessage" class="success">{{ qlcMessage }}</p>
    </section>

    <p v-if="error" class="error">{{ error }}</p>
  </div>
</template>

<style scoped>
.upload {
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

.upload-section {
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

.error {
  color: red;
}

.success {
  color: var(--color-text);
  font-size: 0.9rem;
}
</style>
