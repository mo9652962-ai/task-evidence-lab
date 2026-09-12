<script setup lang="ts">
defineProps<{ status: string; label: string }>()
</script>

<template>
  <span class="status-badge" :class="`status-${status}`">{{ label }}</span>
</template>
