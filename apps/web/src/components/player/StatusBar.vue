<template>
  <header class="status-bar">
    <div class="left">
      <div class="cycle">
        <strong>{{ cycleCount }}</strong>
        <span>次循环</span>
        <em v-if="halfCycleCount">半 {{ halfCycleCount }}</em>
      </div>
      <div v-for="(value, key) in attributes" :key="key" class="attribute">
        <span>{{ labelFor(key) }}</span>
        <strong>{{ value }}</strong>
      </div>
    </div>
    <div class="right">
      <div class="chips">
        <span v-for="item in inventory" :key="item.id" class="chip" :class="{ cross: item.crossSurface }" :title="item.name">
          {{ item.name }}<template v-if="item.count">×{{ item.count }}</template>
        </span>
      </div>
      <span class="node">◇ {{ nodeName }}</span>
      <button type="button" :disabled="busy" @click="$emit('toggleBackpack')">背包</button>
      <button type="button" :disabled="busy" @click="$emit('save')">存档</button>
      <button type="button" :disabled="busy" @click="$emit('openSaves')">读档</button>
    </div>
  </header>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ItemBrief } from '@cycle-master/api-contract'

const props = defineProps<{
  cycleCount: number
  halfCycleCount: number
  attributes: Record<string, number>
  inventory: ItemBrief[]
  nodeName: string
  busy: boolean
}>()

defineEmits<{ toggleBackpack: []; save: []; openSaves: [] }>()

const labels: Record<string, string> = { sanity: '理智', courage: '勇气', insight: '灵感' }
const inventory = computed(() => props.inventory)

function labelFor(key: string): string { return labels[key] ?? key.toUpperCase() }
</script>

<style scoped>
.status-bar {
  position: sticky; top: 0; z-index: 20; display: flex; justify-content: space-between; align-items: center;
  gap: 12px; padding: 10px 18px; color: #efe6d3; background: rgba(11, 10, 9, 0.94);
  border-bottom: 1px solid rgba(184, 148, 62, 0.18); backdrop-filter: blur(10px);
}
.left, .right { display: flex; align-items: center; gap: 10px; min-width: 0; }
.cycle strong { font-size: 18px; color: #b8943e; margin-right: 3px; }
.cycle span { font-size: 11px; color: #9d9284; }
.cycle em { font-size: 10px; padding: 1px 4px; border: 1px solid rgba(184,148,62,.25); border-radius: 3px; margin-left: 5px; }
.attribute { display: flex; gap: 4px; align-items: baseline; font-size: 12px; }
.attribute span { color: #9d9284; }
.chips { display: flex; gap: 5px; overflow: auto; max-width: 260px; }
.chip { font-size: 11px; color: #cfc4b0; background: rgba(184,148,62,.08); border: 1px solid rgba(184,148,62,.14); padding: 2px 6px; border-radius: 3px; white-space: nowrap; }
.chip.cross { border-color: rgba(193, 74, 49, .32); color: #e6a68f; }
button { height: 28px; padding: 0 9px; color: #b8943e; border: 1px solid rgba(184,148,62,.2); background: transparent; cursor: pointer; }
button:disabled { opacity: .4; cursor: not-allowed; }
.node { color: #9d9284; font-size: 11px; white-space: nowrap; }
</style>
