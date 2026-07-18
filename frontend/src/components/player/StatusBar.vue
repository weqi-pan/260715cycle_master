<!-- frontend/src/components/player/StatusBar.vue -->
<template>
  <div class="status-bar">
    <div class="status-left">
      <div class="status-item cycle-item">
        <span class="cycle-num">{{ cycle }}</span>
        <span class="cycle-label">次循环</span>
        <span v-if="halfCycle > 0" class="half-badge">半{{ halfCycle }}</span>
      </div>
      <div class="status-divider" />
      <div class="status-item" v-for="(val, key) in attrs" :key="key">
        <span class="attr-label">{{ labelFor(key) }}</span>
        <span class="attr-value" :class="{ warn: isWarn(key, val), critical: isCritical(key, val) }">{{ val }}</span>
      </div>
    </div>

    <div class="status-right">
      <div class="inventory-area" v-if="inventory.length > 0">
        <span class="inv-label">背包</span>
        <div class="inv-items">
          <span
            v-for="item in inventory"
            :key="item.id"
            class="inv-item"
            :class="{ cross: isCrossSurface(item) }"
            :title="item.name"
          >
            {{ item.name }}
            <span v-if="isCrossSurface(item)" class="cross-mark">↻</span>
          </span>
        </div>
      </div>
      <div class="node-name" v-if="nodeName">
        <span class="node-pin">📍</span>{{ nodeName }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ItemBrief } from '@/types'

const props = defineProps<{
  cycleCount: number
  halfCycleCount: number
  attributes: Record<string, number>
  inventory?: ItemBrief[]
  nodeName?: string
}>()

const cycle = computed(() => props.cycleCount)
const halfCycle = computed(() => props.halfCycleCount)
const attrs = computed(() => props.attributes)
const inventory = computed(() => props.inventory ?? [])

function labelFor(key: string): string {
  const labels: Record<string, string> = { sanity: '理智', courage: '勇气', insight: '灵感' }
  return labels[key] ?? key.toUpperCase()
}

function isWarn(key: string, val: number): boolean {
  if (key === 'sanity') return val <= 30
  if (key === 'courage') return val <= 3
  return false
}

function isCritical(key: string, val: number): boolean {
  if (key === 'sanity') return val <= 10
  if (key === 'courage') return val <= 1
  return false
}

function isCrossSurface(item: ItemBrief): boolean {
  // cross_surface items have a special flag — check by known IDs for now
  const crossItems = ['item_amulet', 'item_qing_coin', 'item_beads', 'item_porcelain_shard', 'item_denim_rag', 'item_jade_pendant']
  return crossItems.includes(item.id)
}
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.status-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1.5rem;
  background: linear-gradient(180deg, rgba(13,13,13,0.95) 0%, rgba(13,13,13,0.7) 100%);
  border-bottom: 1px solid rgba($accent-gold, 0.12);
  backdrop-filter: blur(8px);
  font-family: $font-ui;
  font-size: 0.82rem;
  z-index: 10;
}

.status-left {
  display: flex;
  align-items: center;
  gap: 0.8rem;
}

.status-right {
  display: flex;
  align-items: center;
  gap: 1.5rem;
}

.status-divider {
  width: 1px;
  height: 20px;
  background: rgba($accent-gold, 0.15);
}

.cycle-item {
  display: flex;
  align-items: baseline;
  gap: 0.25rem;
}

.cycle-num {
  font-family: $font-display;
  font-size: 1.2rem;
  font-weight: 700;
  color: $accent-gold;
}

.cycle-label {
  color: $text-secondary;
  font-size: 0.75rem;
}

.half-badge {
  font-size: 0.65rem;
  color: $accent-ghost;
  background: rgba($accent-ghost, 0.15);
  padding: 0.1rem 0.35rem;
  border-radius: 2px;
}

.attr-label {
  color: $text-dim;
  margin-right: 0.2rem;
  font-size: 0.75rem;
}

.attr-value {
  color: $text-primary;
  font-weight: 600;
  font-family: $font-ui;

  &.warn { color: $accent-red-glow; }
  &.critical { color: $accent-red; animation: attr-pulse 2s ease-in-out infinite; }
}

@keyframes attr-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

// ── Inventory ──
.inventory-area {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.inv-label {
  color: $text-dim;
  font-size: 0.7rem;
  white-space: nowrap;
}

.inv-items {
  display: flex;
  gap: 0.3rem;
  flex-wrap: wrap;
  max-width: 300px;
}

.inv-item {
  font-size: 0.7rem;
  color: $text-secondary;
  background: rgba($accent-gold, 0.08);
  border: 1px solid rgba($accent-gold, 0.12);
  padding: 0.1rem 0.4rem;
  border-radius: 2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100px;
  cursor: default;

  &.cross {
    border-color: rgba($accent-red, 0.25);
    background: rgba($accent-red, 0.06);
  }
}

.cross-mark {
  color: $accent-red-glow;
  margin-left: 0.15rem;
  font-size: 0.65rem;
}

// ── Node name ──
.node-name {
  color: $text-dim;
  font-size: 0.75rem;
  white-space: nowrap;
}

.node-pin {
  margin-right: 0.2rem;
}
</style>
