import { defineStore } from "pinia";
import { ref } from "vue";

import { audioApi } from "@/api/audio";

// Same shape as useWhoAmIStore, for the same reason: App.vue needs to
// know whether to show the "Audio" nav link before the page itself is
// ever visited. Unlike IS_MASTER (a network-wide role), `handles_audio`
// is this device's own local config, so it comes from `/audio/status`
// rather than `/whoami`.
export const useAudioStore = defineStore("audio", () => {
  const handlesAudio = ref(false);
  const loaded = ref(false);

  async function load(): Promise<void> {
    const { handles_audio } = await audioApi.status();
    handlesAudio.value = handles_audio;
    loaded.value = true;
  }

  return { handlesAudio, loaded, load };
});
