<!-- BackgroundLayer.vue — z-0 background image + vignette -->
<template>
  <div class="bg-layer" :class="{ fading: isTransitioning }">
    <div
      class="bg-image"
      :style="bgStyle"
    />
    <div class="bg-vignette" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue'

const props = defineProps<{ background: string | null }>()

const current = ref<string | null>(null)
const previous = ref<string | null>(null)
const isTransitioning = ref(false)

const bgStyle = computed(() => {
  if (current.value) {
    return { backgroundImage: `url(${current.value})` }
  }
  return {}
})

watch(() => props.background, (newBg) => {
  if (newBg === current.value) return
  previous.value = current.value
  isTransitioning.value = true
  setTimeout(() => {
    current.value = newBg
    isTransitioning.value = false
  }, 400)
}, { immediate: true })
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.bg-layer {
  position: fixed;
  inset: 0;
  z-index: 0;
  background: $bg-void;
}

.bg-image {
  position: absolute;
  inset: 0;
  background-size: cover;
  background-position: center;
  background-repeat: no-repeat;
  opacity: 0.35;
  transition: opacity 0.8s ease;
}

.bg-vignette {
  position: absolute;
  inset: 0;
  background: radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.7) 100%);
  animation: breathe 8s ease-in-out infinite;
}

@keyframes breathe {
  0%, 100% { opacity: 0.7; }
  50% { opacity: 0.95; }
}
</style>
