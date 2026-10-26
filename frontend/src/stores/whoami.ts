import { defineStore } from "pinia";
import { ref } from "vue";

import { whoamiApi } from "@/api/whoami";

// First real use of Pinia in this app (see main.ts's comment) -- global
// UI-gating state (hide configuration pages unless this device is
// master), read from /whoami which itself reads straight from backend's
// Settings, no DB lookup -- so this resolves even on a device with no
// devices row yet.
export const useWhoAmIStore = defineStore("whoami", () => {
  // Defaults to false (not master) until the real answer comes back --
  // same fail-safe direction as backend's own IS_MASTER defaulting to
  // False: hide configuration rather than briefly show it to a device
  // that turns out not to be master.
  const isMaster = ref(false);
  const loaded = ref(false);

  async function load(): Promise<void> {
    const { is_master } = await whoamiApi.get();
    isMaster.value = is_master;
    loaded.value = true;
  }

  return { isMaster, loaded, load };
});
