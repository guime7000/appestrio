import { defineStore } from "pinia";
import { ref } from "vue";

import { dmxApi } from "@/api/dmx";

// Same shape as useAudioStore/useWhoAmIStore: App.vue needs to know
// whether to show the "QLC+" nav link before the page itself is ever
// visited. `handles_dmx` is this device's own local config, same as
// `handles_audio`, so it comes from a dedicated status endpoint rather
// than `/whoami` (a network-wide role, not a per-device capability).
export const useDmxStore = defineStore("dmx", () => {
  const handlesDmx = ref(false);
  const loaded = ref(false);

  async function load(): Promise<void> {
    const { handles_dmx } = await dmxApi.status();
    handlesDmx.value = handles_dmx;
    loaded.value = true;
  }

  return { handlesDmx, loaded, load };
});
