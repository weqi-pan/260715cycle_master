<template>
  <div class="dialog-backdrop" @click.self="$emit('close')">
    <section class="dialog" aria-label="存档">
      <header><h2>存档与读档</h2><button type="button" @click="$emit('close')">关闭</button></header>
      <div class="new-save">
        <input v-model="name" type="text" placeholder="存档名称" :disabled="busy" />
        <button type="button" :disabled="busy" @click="$emit('save', saveName())">保存当前回合</button>
      </div>
      <p v-if="!saves.length">还没有手动存档。</p>
      <ul>
        <li v-for="save in saves" :key="save.id" :class="{ incompatible: !save.compatible }">
          <div>
            <strong>{{ save.name }}</strong>
            <small>{{ save.compatible ? `第 ${save.cycleCount + 1} 循环 · ${save.currentNodeId}` : '与当前剧情不兼容' }}</small>
          </div>
          <div>
            <button type="button" :disabled="!save.compatible || busy" @click="$emit('load', save.id)">读取</button>
            <button type="button" :disabled="busy" @click="$emit('remove', save.id)">删除</button>
          </div>
        </li>
      </ul>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { SaveSummary } from '@cycle-master/api-contract'

defineProps<{ saves: SaveSummary[]; busy: boolean }>()
const emit = defineEmits<{ close: []; load: [saveId: string]; save: [name: string]; remove: [saveId: string] }>()
const name = ref('')

function saveName(): string {
  const value = name.value.trim()
  name.value = ''
  return value
}
</script>

<style scoped>
.dialog-backdrop { position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; background: rgba(0,0,0,.68); }
.dialog { width: min(680px, 92vw); max-height: 82vh; overflow: auto; padding: 22px; background: #12100e; border: 1px solid rgba(184,148,62,.2); }
header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 18px; }
h2 { margin: 0; color: #b8943e; }
.new-save { display: flex; gap: 10px; margin-bottom: 20px; }
input { flex: 1; padding: 10px; background: #171412; border: 1px solid rgba(184,148,62,.16); color: #efe6d3; }
button { padding: 8px 12px; background: transparent; border: 1px solid rgba(184,148,62,.2); color: #b8943e; cursor: pointer; }
button:disabled { opacity: .4; cursor: not-allowed; }
ul { list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }
li { display: flex; justify-content: space-between; gap: 12px; padding: 12px; border: 1px solid rgba(184,148,62,.11); }
li small { display: block; color: #9d9284; }
li.incompatible { border-color: rgba(193,74,49,.3); }
</style>
