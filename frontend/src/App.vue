<script setup lang="ts">
const navLinks = [
  { to: "/", label: "Accueil" },
  { to: "/devices", label: "Lumestrio" },
  { to: "/groups", label: "Groupes" },
  { to: "/calendars", label: "Calendriers" },
];
</script>

<template>
  <nav class="nav">
    <RouterLink v-for="link in navLinks" :key="link.to" :to="link.to">
      {{ link.label }}
    </RouterLink>
  </nav>
  <main>
    <RouterView />
  </main>
</template>

<style scoped>
.nav {
  display: flex;
  gap: 0.5rem;
  padding: 1rem;
}

.nav a {
  padding: 0.5rem 1rem;
  border-radius: 999px;
  text-decoration: none;
  font-weight: bold;
}

main {
  padding: 1rem;
}
</style>
