<template>
  <aside class="inventory" aria-label="背包">
    <h2>背包</h2>
    <p v-if="!items.length">背包为空。</p>
    <ul>
      <li v-for="item in items" :key="item.id">
        <div>
          <strong>{{ item.name }}</strong>
          <span v-if="item.count">×{{ item.count }}</span>
        </div>
        <button type="button" v-if="item.discardable" :disabled="busy" @click="$emit('discard', item.id)">丢弃</button>
      </li>
    </ul>
  </aside>
</template>

<script setup lang="ts">
import type { ItemBrief } from '@cycle-master/api-contract'

defineProps<{ items: ItemBrief[]; busy: boolean }>()
defineEmits<{ discard: [itemId: string] }>()
</script>

<style scoped>
.inventory { width: 260px; padding: 20px; border-left: 1px solid rgba(184,148,62,.15); background: rgba(11,10,9,.95); }
h2 { margin: 0 0 18px; font-size: 18px; color: #b8943e; }
p, li { color: #b3a996; font-size: 14px; }
ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
li { display: flex; justify-content: space-between; align-items: center; gap: 10px; padding: 10px; border: 1px solid rgba(184,148,62,.11); }
button { color: #e6a68f; border-color: rgba(193,74,49,.3); background: transparent; cursor: pointer; }
</style>
