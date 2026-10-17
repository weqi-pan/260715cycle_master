<template>
  <main class="home">
    <section>
      <p class="eyebrow">Cycle Master v2</p>
      <h1>循环之环</h1>
      <p>这是全栈 TypeScript 重构版。进度只保存在明确的手动存档中，刷新或重启后不会自动恢复。</p>
      <div class="actions">
        <button type="button" :disabled="busy" @click="startGame">开始新游戏</button>
        <button type="button" :disabled="busy" @click="store.refreshSaves()">刷新存档</button>
      </div>
      <p v-if="error" class="error">{{ error }}</p>
      <div class="saves">
        <h2>手动存档</h2>
        <p v-if="!saves.length">暂无存档。</p>
        <ul>
          <li v-for="save in saves" :key="save.id" :class="{ incompatible: !save.compatible }">
            <div>
              <strong>{{ save.name }}</strong>
              <small>{{ save.compatible ? `第 ${save.cycleCount + 1} 循环 · ${save.currentNodeId}` : '与当前剧情不兼容' }}</small>
            </div>
            <button type="button" :disabled="!save.compatible || busy" @click="load(save.id)">读取</button>
          </li>
        </ul>
      </div>
    </section>
  </main>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useGameStore } from '../stores/gameStore'

const router = useRouter()
const store = useGameStore()
const { busy, error, saves } = storeToRefs(store)

onMounted(() => {
  store.refreshSaves()
})

function startGame(): void {
  void store.start().then(() => { if (store.frame) router.push('/play') })
}

function load(saveId: string): void {
  void store.resume(saveId).then(() => { if (store.frame) router.push('/play') })
}
</script>

<style scoped>
.home { min-height: 100vh; display: grid; place-items: center; background: radial-gradient(circle at center, #181411, #070605); color: #efe6d3; }
section { width: min(760px, 92vw); }
.eyebrow { color: #b8943e; text-transform: uppercase; letter-spacing: .18em; font-size: 12px; }
h1 { font-size: clamp(40px, 7vw, 72px); margin: 8px 0 14px; }
p { color: #b3a996; line-height: 1.7; }
.actions { display: flex; gap: 12px; margin: 28px 0 38px; }
button { padding: 12px 20px; border: 1px solid rgba(184,148,62,.24); background: transparent; color: #b8943e; cursor: pointer; }
button:disabled { opacity: .4; cursor: not-allowed; }
h2 { color: #b8943e; font-size: 18px; }
ul { list-style: none; padding: 0; display: grid; gap: 10px; }
li { display: flex; justify-content: space-between; align-items: center; padding: 12px; border: 1px solid rgba(184,148,62,.11); }
li small { color: #9d9284; display: block; }
li.incompatible { border-color: rgba(193,74,49,.3); }
.error { color: #e6a68f; }
</style>
