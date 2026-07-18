<!-- NarrativeText.vue — text content with Markdown rendering -->
<template>
  <div class="narrative-text" v-html="rendered"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ content: string }>()

const rendered = computed(() => {
  let text = props.content
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>')
  text = text.replace(/---/g, '<span class="scene-break">· · ·</span>')
  text = text.replace(/\n\n/g, '</p><p>')
  return `<p>${text}</p>`
})
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.narrative-text {
  font-size: 1rem;
  line-height: 1.85;
  letter-spacing: 0.02em;
  flex: 1;
  overflow-y: auto;
  min-height: 0;

  :deep(p) {
    margin-bottom: 0.8rem;
    text-indent: 2em;
    &:first-child { text-indent: 0; }
  }
  :deep(strong) { color: $accent-gold; font-weight: 700; }
  :deep(em) { color: $text-secondary; font-style: italic; }
  :deep(.scene-break) {
    display: block;
    text-align: center;
    color: $accent-red;
    margin: 1.5rem 0;
    font-family: $font-display;
    letter-spacing: 0.8em;
    font-size: 1rem;
  }
}
</style>
