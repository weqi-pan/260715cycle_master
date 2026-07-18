<!-- ContinueIndicator.vue — blinking "click to continue" -->
<template>
  <div v-if="show" class="continue-indicator" @click="$emit('continue')">
    <span class="arrow">▼</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{ show: boolean }>()
defineEmits<{ continue: [] }>()
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.continue-indicator {
  text-align: center;
  padding: 0.6rem 0;
  cursor: pointer;
  user-select: none;
}

.arrow {
  color: $accent-gold;
  font-size: 1.2rem;
  animation: blink 1.5s ease-in-out infinite;
}

@keyframes blink {
  0%, 100% { opacity: 0.3; }
  50% { opacity: 1; }
}
</style>
