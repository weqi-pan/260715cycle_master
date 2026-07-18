<!-- frontend/src/components/player/ChoicePanel.vue -->
<template>
  <div class="choice-panel" v-if="choices.length > 0">
    <ChoiceButton
      v-for="choice in choices"
      :key="choice.id"
      :choice="choice"
      @select="$emit('select', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import type { ChoiceResult } from '@/types'
import ChoiceButton from './ChoiceButton.vue'

defineProps<{ choices: ChoiceResult[] }>()
defineEmits<{ select: [id: string] }>()
</script>

<style scoped lang="scss">
.choice-panel {
  padding: 1rem 2rem;
  max-width: 720px;
  margin: 0 auto;
}
</style>
