<script setup lang="ts">
const tabs = [
  { to: { name: "configuration-devices" }, label: "Appareils" },
  { to: { name: "configuration-groups" }, label: "Groupes" },
  { to: { name: "configuration-calendars" }, label: "Calendriers" },
  { to: { name: "configuration-clocks" }, label: "Horloges" },
];
</script>

<template>
  <h1>Configuration</h1>
  <nav class="tabs">
    <RouterLink
      v-for="tab in tabs"
      :key="tab.label"
      :to="tab.to"
      class="tab"
      active-class="tab-active"
    >
      {{ tab.label }}
    </RouterLink>
  </nav>
  <div class="tab-content">
    <RouterView />
  </div>
</template>

<style scoped>
.tabs {
  display: flex;
  flex-direction: row;
  gap: 0.5rem;
  border-bottom: 1px solid var(--color-border);
  margin-bottom: 1rem;
}

.tab {
  padding: 0.5rem 1rem;
  text-decoration: none;
  font-weight: bold;
  color: var(--color-text);
  border-bottom: 2px solid transparent;
}

.tab-active {
  border-bottom-color: var(--color-text);
}
</style>
