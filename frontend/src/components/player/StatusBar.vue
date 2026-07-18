<!-- frontend/src/components/player/StatusBar.vue -->
<template>
  <div class="status-bar">
    <div class="status-item">
      <span class="status-label">循环</span>
      <span class="status-value">{{ cycle }}</span>
      <span v-if="halfCycle > 0" class="status-half">(半:{{ halfCycle }})</span>
    </div>
    <div class="status-item" v-for="(val, key) in attrs" :key="key">
      <span class="status-label">{{ key.toUpperCase() }}</span>
      <span class="status-value" :class="{ warn: isWarn(key, val) }">{{ val }}</span>
    </div>
    <div class="status-item" v-if="nodeName">
      <span class="status-label">📍</span>
      <span class="status-value">{{ nodeName }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  cycleCount: number
  halfCycleCount: number
  attributes: Record<string, number>
  nodeName?: string
}>()

const cycle = computed(() => props.cycleCount)
const halfCycle = computed(() => props.halfCycleCount)
const attrs = computed(() => props.attributes)

function isWarn(key: string, val: number): boolean {
  if (key === 'sanity') return val <= 30
  if (key === 'courage') return val <= 3
  return false
}
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.status-bar {
  display: flex;
  gap: 2rem;
  padding: 0.6rem 2rem;
  background: rgba(0, 0, 0, 0.5);
  border-bottom: 1px solid rgba($accent-gold, 0.2);
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.status-label {
  color: $text-secondary;
  font-size: 0.85rem;
}

.status-value {
  color: $text-primary;
  font-weight: bold;

  &.warn { color: $accent-red; }
}

.status-half {
  color: $text-secondary;
  font-size: 0.75rem;
}
</style>
