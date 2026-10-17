<template>
  <svg viewBox="-70 -70 140 140" width="180" height="180" aria-label="循环地图">
    <circle r="48" fill="none" stroke="rgba(184,148,62,.18)" stroke-width="1" />
    <path d="M-16 40 Q0 52 16 40" fill="none" stroke="rgba(193,74,49,.35)" stroke-width="1" stroke-dasharray="3 3" />
    <g v-for="node in nodes" :key="node.id">
      <circle :cx="node.x" :cy="node.y" r="4" :fill="fill(node.id)" :stroke="node.id === currentId ? '#b8943e' : 'rgba(184,148,62,.22)'" />
      <text :x="node.labelX" :y="node.labelY" text-anchor="middle" font-size="5" fill="rgba(184,148,62,.65)">{{ node.id }}</text>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{ currentId: string; visitedIds: string[] }>()
const positions: Record<string, number> = { A: -90, B: -45, C: 0, D: 45, E: 90, F: 135, G: 180, H: 225 }

const nodes = computed(() => Object.entries(positions).map(([id, angle]) => {
  const rad = angle * Math.PI / 180
  return { id, x: Math.cos(rad) * 48, y: Math.sin(rad) * 48, labelX: Math.cos(rad) * 61, labelY: Math.sin(rad) * 61 + 2 }
}))

function fill(id: string): string {
  if (id === props.currentId) return '#b8943e'
  if (props.visitedIds.includes(id)) return 'rgba(184,148,62,.45)'
  return 'rgba(184,148,62,.12)'
}
</script>

<style scoped>
svg { background: rgba(11,10,9,.92); border: 1px solid rgba(184,148,62,.14); border-radius: 10px; }
</style>
