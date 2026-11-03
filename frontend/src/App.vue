<script setup lang="ts">
import { computed, onMounted } from "vue";

import { useTheme } from "@/composables/useTheme";
import { useAudioStore } from "@/stores/audio";
import { useDmxStore } from "@/stores/dmx";
import { useWhoAmIStore } from "@/stores/whoami";

const whoami = useWhoAmIStore();
const audio = useAudioStore();
const dmx = useDmxStore();
onMounted(() => {
  whoami.load();
  audio.load();
  dmx.load();
});

const navLinks = computed(() => [
  { to: "/", label: "Inauguration" },
  ...(whoami.isMaster ? [{ to: "/configuration", label: "Configuration" }] : []),
  ...(audio.handlesAudio ? [{ to: "/audio", label: "Audio" }] : []),
]);

// QLC+ (`compose.dmx.yml`, only started on devices that actually have a
// DMX interface) is reached directly on its own port, same way
// lora-daemon's own hardware test console sits directly on 8765 --
// nothing in this app proxies or embeds it, just a link to a new tab.
const qlcplusUrl = `http://${window.location.hostname}:9999`;

const { theme, toggleTheme } = useTheme();
</script>

<template>
  <nav class="nav">
    <div class="nav-links">
      <RouterLink v-for="link in navLinks" :key="link.to" :to="link.to">
        {{ link.label }}
      </RouterLink>
      <a v-if="dmx.handlesDmx" :href="qlcplusUrl" target="_blank" rel="noopener">
        QLC+
      </a>
    </div>
    <button
      type="button"
      class="theme-toggle"
      :aria-label="theme === 'dark' ? 'Passer au thème clair' : 'Passer au thème sombre'"
      @click="toggleTheme"
    >
      {{ theme === "dark" ? "☀️ Clair" : "🌙 Sombre" }}
    </button>
  </nav>
  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 1rem;
}

.nav-links {
  display: flex;
  gap: 0.5rem;
}

.nav a {
  padding: 0.5rem 1rem;
  border-radius: 999px;
  text-decoration: none;
  font-weight: bold;
}

.theme-toggle {
  padding: 0.5rem 1rem;
  border-radius: 999px;
  border: 1px solid var(--color-border);
  background: var(--color-surface-alt);
  color: var(--color-text);
  font-weight: bold;
  cursor: pointer;
}

main {
  padding: 1rem;
}
</style>
