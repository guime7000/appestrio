<script setup lang="ts">
import { useTheme } from "@/composables/useTheme";

const navLinks = [
  { to: "/", label: "Accueil" },
  { to: "/devices", label: "Lumestrio" },
  { to: "/groups", label: "Groupes" },
  { to: "/calendars", label: "Calendriers" },
];

const { theme, toggleTheme } = useTheme();
</script>

<template>
  <nav class="nav">
    <div class="nav-links">
      <RouterLink v-for="link in navLinks" :key="link.to" :to="link.to">
        {{ link.label }}
      </RouterLink>
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
