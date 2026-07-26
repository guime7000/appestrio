<script setup lang="ts">
const cards = [
  { to: "/devices", label: "Je gère les LUMESTRIO" },
  { to: "/groups", label: "Je gère les GROUPES" },
  { to: "/calendars", label: "Je gère les CALENDRIERS" },
];
</script>

<template>
  <h1>Installation</h1>
  <div class="cards">
    <RouterLink v-for="card in cards" :key="card.to" :to="card.to" class="card">
      {{ card.label }}
    </RouterLink>
  </div>
</template>

<style scoped>
.cards {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

.card {
  padding: 2rem;
  border-radius: 999px;
  text-decoration: none;
  font-weight: bold;
  text-align: center;
  min-width: 10rem;
}
</style>
