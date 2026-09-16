<script setup lang="ts">
defineProps<{
  count: number;
}>();
</script>

<template>
  <div v-if="count > 0" class="pending-sync-banner" role="alert">
    Des appareils ont été modifiés : leur configuration doit être mise à jour
    sur les appareils concernés.
  </div>
</template>

<style scoped>
.pending-sync-banner {
  background: var(--color-danger-bg);
  color: var(--color-danger-text);
  border: 1px solid var(--color-danger-border);
  border-radius: 6px;
  padding: 0.75rem 1rem;
  margin-bottom: 1rem;
  font-weight: 600;
}
</style>
