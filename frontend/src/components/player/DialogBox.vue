<!-- DialogBox.vue — bottom dialog panel with narrative/choice modes -->
<template>
  <div class="dialog-box" :class="{ 'choice-mode': hasChoices }">
    <div class="dialog-gradient" />
    <div class="dialog-content">
      <SpeakerHeader
        :speaker="speaker"
        :avatar="speakerAvatar"
      />
      <NarrativeText :content="content" />
      <ContinueIndicator
        :show="!hasChoices"
        @continue="$emit('continue')"
      />
      <ChoicePanel
        v-if="hasChoices"
        :choices="choices"
        @select="$emit('select', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ChoiceResult } from '@/types'
import SpeakerHeader from './SpeakerHeader.vue'
import NarrativeText from './NarrativeText.vue'
import ContinueIndicator from './ContinueIndicator.vue'
import ChoicePanel from './ChoicePanel.vue'

const props = defineProps<{
  content: string
  speaker: string | null
  speakerAvatar: string | null
  choices: ChoiceResult[]
}>()

defineEmits<{
  continue: []
  select: [id: string]
}>()

const hasChoices = computed(() => props.choices.length > 0)
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.dialog-box {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  z-index: 20;
  max-height: 45%;
  transition: max-height 0.3s ease;

  &.choice-mode {
    max-height: 60%;
  }
}

.dialog-gradient {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    rgba($bg-void, 0.3) 0%,
    rgba($bg-void, 0.85) 15%,
    rgba($bg-void, 0.95) 100%
  );
  pointer-events: none;
}

.dialog-content {
  position: relative;
  padding: 1.5rem 2rem 1.5rem;
  max-width: $narrative-max-width;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  min-height: 120px;
}
</style>
