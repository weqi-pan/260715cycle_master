<!-- StatusBar.vue — 顶部状态栏 + 操作按钮 -->
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
        <span class="attr-value" :class="{ warn: isWarn(key, val), critical: isCritical(key, val) }">{{ displayValue(key, val) }}</span>
      </div>
      <div class="status-divider" />
      <div class="status-actions">
        <button class="act-btn" @click="$emit('toggleBackpack')" title="背包">囊</button>
        <button class="act-btn" @click="$emit('save')" title="存档">存</button>
        <button class="act-btn" @click="$emit('load')" title="读档">读</button>
      </div>
    </div>

    <div class="status-right">
      <div class="inventory-inline" v-if="inventory.length > 0">
        <span v-for="item in inventory" :key="item.id"
          class="inv-chip" :class="{ cross: isCrossSurface(item) }" :title="item.name">
          {{ item.name }}<span v-if="isCrossSurface(item)" class="cross-mark">↻</span>
        </span>
      </div>
      <div class="node-name" v-if="nodeName" @click="$emit('toggleMap')" title="点击查看地图">
        <span class="node-pin">◇</span>{{ nodeName }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ItemBrief } from '@/types'

const props = defineProps<{ cycleCount: number; halfCycleCount: number; attributes: Record<string,number>; inventory?: ItemBrief[]; nodeName?: string }>()
defineEmits<{ toggleMap: []; toggleBackpack: []; save: []; load: [] }>()

const cycle = computed(() => props.cycleCount)
const halfCycle = computed(() => props.halfCycleCount)
const attrs = computed(() => Object.fromEntries(
  ['sanity','courage','insight']
    .filter(key => typeof props.attributes[key] === 'number')
    .map(key => [key, props.attributes[key]])
))
const inventory = computed(() => props.inventory ?? [])

const CROSS = new Set(['item_amulet','item_qing_coin','item_beads','item_porcelain_shard','item_denim_rag','item_jade_pendant'])
function isCrossSurface(item: ItemBrief) { return CROSS.has(item.id) }
function labelFor(k: string|number) { const key=String(k); const m: Record<string,string>={sanity:'理智',courage:'勇气',insight:'灵感'}; return m[key]??key.toUpperCase() }
function displayValue(k:string|number,v:number){return String(k)==='sanity'&&props.attributes.sanity_max!=null?`${v}/${props.attributes.sanity_max}`:v}
function isWarn(k: string|number, v: number) { const key=String(k); return (key==='sanity'&&v<=30)||(key==='courage'&&v<=3) }
function isCritical(k: string|number, v: number) { const key=String(k); return (key==='sanity'&&v<=10)||(key==='courage'&&v<=1) }
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.status-bar { display:flex; justify-content:space-between; align-items:center; min-height:46px; padding:0.4rem 1.2rem; background:linear-gradient(180deg, rgba(10,10,9,0.97), rgba(13,12,10,0.82)); border-bottom:1px solid rgba($accent-gold,0.16); box-shadow:0 8px 30px rgba(0,0,0,.24); backdrop-filter:blur(10px); font-family:$font-ui; font-size:0.78rem; z-index:100; }
.status-left, .status-right { display:flex; align-items:center; gap:0.6rem; }
.status-divider { width:1px; height:18px; background:rgba($accent-gold,0.12); }
.cycle-num { font-family:$font-display; font-size:1.1rem; font-weight:700; color:$accent-gold; }
.cycle-label { color:$text-dim; font-size:0.7rem; }
.half-badge { font-size:0.6rem; color:$accent-ghost; background:rgba($accent-ghost,0.15); padding:0.05rem 0.3rem; border-radius:2px; }
.attr-label { color:$text-dim; font-size:0.7rem; margin-right:0.15rem; }
.attr-value { color:$text-primary; font-weight:600;
  &.warn { color:$accent-red-glow; }
  &.critical { color:$accent-red; animation:pulse 2s infinite; }
}
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }

.status-actions { display:flex; gap:0.15rem; }
.act-btn { width:26px; height:26px; background:rgba($accent-gold,.025); border:1px solid rgba($accent-gold,0.14); color:rgba($accent-gold,0.55); font-family:$font-display; font-size:0.72rem; cursor:pointer; border-radius:1px; line-height:1;
  &:hover { border-color:rgba($accent-gold,0.3); color:$accent-gold; }
}

.inventory-inline { display:flex; gap:0.25rem; max-width:260px; overflow-x:auto; }
.inv-chip { font-size:0.65rem; color:$text-dim; background:rgba($accent-gold,0.06); border:1px solid rgba($accent-gold,0.08); padding:0.05rem 0.35rem; border-radius:2px; white-space:nowrap;
  &.cross { border-color:rgba($accent-red,0.2); background:rgba($accent-red,0.04); }
}
.cross-mark { color:$accent-red-glow; margin-left:0.1rem; font-size:0.6rem; }
.node-name { color:$text-dim; font-size:0.7rem; white-space:nowrap; cursor:pointer;
  &:hover { color:$accent-gold; }
}
.node-pin { margin-right:0.15rem; }

@media (max-width:760px){
  .status-bar{padding:.35rem .65rem;align-items:flex-start;gap:.4rem}
  .status-left{gap:.35rem;flex-wrap:wrap}
  .status-right{margin-left:auto}
  .inventory-inline{display:none}
  .status-divider{display:none}
  .node-name{max-width:110px;overflow:hidden;text-overflow:ellipsis}
}
</style>
