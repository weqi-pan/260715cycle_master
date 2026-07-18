<!-- CycleMap.vue — Mobius strip ring minimap -->
<template>
  <div class="cycle-map" :class="{ expanded: show }">
    <button class="map-toggle" @click="show = !show" :title="show ? '收起' : '环形地图'">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
        <circle cx="12" cy="12" r="10" />
        <path d="M2 12c0-3 2-6 6-8" stroke-dasharray="3 2" />
        <circle cx="12" cy="12" r="2" fill="currentColor" />
      </svg>
    </button>
    <svg v-if="show" class="map-svg" viewBox="-60 -60 120 120" width="160" height="160">
      <!-- Ring -->
      <circle cx="0" cy="0" r="45" fill="none" stroke="rgba(180,150,100,0.15)" stroke-width="1" />
      <!-- Mobius twist hint -->
      <path d="M-15 38 Q0 50 15 38" fill="none" stroke="rgba(140,40,0,0.3)" stroke-width="0.8" stroke-dasharray="3 3" />
      <!-- Nodes -->
      <g v-for="n in nodes" :key="n.id">
        <circle
          :cx="n.x" :cy="n.y" r="3.5"
          :fill="n.id === currentId ? '#b8943e' : n.visited ? 'rgba(180,150,100,0.4)' : 'rgba(180,150,100,0.12)'"
          :stroke="n.id === currentId ? '#b8943e' : 'rgba(180,150,100,0.2)'"
          stroke-width="1"
        />
        <text :x="n.labelX" :y="n.labelY" text-anchor="middle" font-size="3.5" fill="rgba(180,150,100,0.5)">{{ n.id }}</text>
      </g>
      <!-- Special nodes -->
      <circle v-if="showK" cx="0" cy="0" r="5" fill="none" stroke="rgba(60,80,100,0.4)" stroke-width="0.6" stroke-dasharray="2 2" />
      <text v-if="showK" x="0" y="2" text-anchor="middle" font-size="2.5" fill="rgba(60,80,100,0.5)">K</text>
    </svg>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{
  currentId: string
  visitedIds: string[]
  hasWarpAccess?: boolean
}>()

const show = ref(false)

const nodePositions: Record<string, { angle: number; labelR: number }> = {
  A: { angle: -90,  labelR: 55 },  // top
  B: { angle: -45,  labelR: 55 },
  C: { angle: 0,    labelR: 55 },  // right
  D: { angle: 45,   labelR: 55 },
  E: { angle: 90,   labelR: 55 },  // bottom (mirror of A)
  F: { angle: 135,  labelR: 55 },
  G: { angle: 180,  labelR: 55 },  // left
  H: { angle: -135, labelR: 55 },
}

const nodes = computed(() => {
  return Object.entries(nodePositions).map(([id, pos]) => {
    const rad = (pos.angle * Math.PI) / 180
    const r = 45
    return {
      id,
      x: Math.cos(rad) * r,
      y: Math.sin(rad) * r,
      labelX: Math.cos(rad) * pos.labelR,
      labelY: Math.sin(rad) * pos.labelR + 1,
      visited: props.visitedIds.includes(id),
    }
  })
})

const showK = computed(() => props.hasWarpAccess ?? false)
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.cycle-map {
  position: fixed;
  bottom: 1rem;
  right: 1rem;
  z-index: 150;
}

.map-toggle {
  width: 32px; height: 32px;
  border-radius: 50%;
  background: rgba($bg-void, 0.7);
  border: 1px solid rgba($accent-gold, 0.2);
  color: rgba($accent-gold, 0.5);
  cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
  &:hover { border-color: $accent-gold; color: $accent-gold; }
}

.map-svg {
  display: block;
  margin-top: 0.5rem;
  background: rgba($bg-void, 0.8);
  border: 1px solid rgba($accent-gold, 0.12);
  border-radius: 8px;
}
</style>
