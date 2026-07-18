<!-- frontend/src/components/player/NarrativePanel.vue -->
<template>
  <div class="narrative-panel">
    <div v-if="speaker" class="speaker-tag">{{ speaker }}</div>
    <div class="narrative-text" v-html="renderedContent"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  content: string
  speaker?: string | null
}>()

const renderedContent = computed(() => {
  let text = props.content
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>')
  text = text.replace(/---/g, '<span class="scene-break">· · ·</span>')
  text = text.replace(/\n\n/g, '</p><p>')
  text = `<p>${text}</p>`
  return text
})
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.narrative-panel {
  padding: 2rem;
  max-width: 720px;
  margin: 0 auto;
}

.speaker-tag {
  color: $accent-gold;
  font-weight: bold;
  margin-bottom: 0.5rem;
  font-size: 1.1em;
}

.narrative-text {
  :deep(p) {
    margin-bottom: 1.2rem;
  }
  :deep(strong) {
    color: $accent-gold;
  }
  :deep(em) {
    color: $text-secondary;
  }
  :deep(.scene-break) {
    display: block;
    text-align: center;
    color: $accent-red;
    margin: 2rem 0;
    letter-spacing: 0.5em;
  }
}
</style>
