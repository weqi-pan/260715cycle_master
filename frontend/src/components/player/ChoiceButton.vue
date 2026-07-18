<!-- frontend/src/components/player/ChoiceButton.vue -->
<template>
  <button
    class="choice-button"
    :class="{ locked: !choice.available, warp: choice.source === 'special_warp' }"
    :disabled="!choice.available"
    @click="$emit('select', choice.id)"
  >
    <span class="choice-text">{{ choice.text }}</span>
    <span v-if="!choice.available && choice.reason" class="choice-reason">{{ choice.reason }}</span>
  </button>
</template>

<script setup lang="ts">
import type { ChoiceResult } from '@/types'

defineProps<{ choice: ChoiceResult }>()
defineEmits<{ select: [id: string] }>()
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.choice-button {
  display: block;
  width: 100%;
  padding: 0.8rem 1.2rem;
  margin-bottom: 0.6rem;
  background: $bg-panel;
  border: 1px solid rgba($accent-gold, 0.3);
  border-radius: 4px;
  color: $text-primary;
  font-family: inherit;
  font-size: 1rem;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;

  &:hover:not(.locked) {
    border-color: $accent-gold;
    background: lighten($bg-panel, 5%);
  }

  &.locked {
    opacity: 0.4;
    cursor: not-allowed;
  }

  &.warp {
    border-color: rgba($accent-red, 0.5);
    border-style: dashed;
  }
}

.choice-reason {
  display: block;
  font-size: 0.8rem;
  color: $text-secondary;
  margin-top: 0.3rem;
}
</style>
