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
  padding: 2.5rem 2rem 1rem;
  max-width: $narrative-max-width;
  margin: 0 auto;
}

.speaker-tag {
  display: inline-block;
  color: $accent-gold;
  font-weight: 600;
  font-family: $font-display;
  font-size: 1.05rem;
  margin-bottom: 0.8rem;
  padding: 0.2rem 0.8rem;
  border-left: 2px solid $accent-gold;
  background: rgba($accent-gold, 0.05);
}

.narrative-text {
  font-size: 1.02rem;

  :deep(p) {
    margin-bottom: 1.1rem;
    text-indent: 2em;
    &:first-child { text-indent: 0; }
  }
  :deep(strong) {
    color: $accent-gold;
    font-weight: 700;
  }
  :deep(em) {
    color: $text-secondary;
    font-style: italic;
  }
  :deep(.scene-break) {
    display: block;
    text-align: center;
    color: $accent-red;
    margin: 2.5rem 0;
    font-family: $font-display;
    letter-spacing: 0.8em;
    font-size: 1.1rem;
  }
}
</style>
