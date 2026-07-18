<!-- GamePlay.vue -->
<template>
  <div class="game-play" @click="onBgClick">
    <div class="bg-layer" :style="bgTintStyle"><div class="bg-vignette" /></div>

    <StatusBar v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count" :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes" :inventory="store.currentState.inventory"
      :node-name="store.currentNode?.name" @toggle-map="showMap = !showMap" />

    <div class="game-main" ref="mainRef">
      <div v-if="store.loading && !store.currentNode" class="loading"><span class="dot">·</span></div>
      <div v-else-if="store.error" class="error"><p>{{ store.error }}</p><button @click="store.init()">重试</button></div>

      <template v-else-if="store.currentNode">
        <div class="content-wrapper">
          <div v-if="store.currentNode.time_label" class="time-label">◈ {{ store.currentNode.time_label }}</div>
          <div v-if="store.currentNode.speaker" class="speaker-row">
            <div class="speaker-avatar">{{ store.currentNode.speaker[0] }}</div>
            <span class="speaker-name">{{ store.currentNode.speaker }}</span>
          </div>

          <!-- Narrative text (only show once per node) -->
          <div class="narrative-box" v-if="!isTyping || displayedText">
            <div class="narrative-text" v-html="displayedText || renderedContent" />
          </div>

          <!-- Accumulated transitions (inline narratives from chosen options) -->
          <div v-for="(t, i) in transitions" :key="'t'+i" class="transition-inline">
            <div class="chosen-label">{{ t.label }}</div>
            <div class="transition-text" v-html="t.text" />
          </div>

          <!-- Current choices -->
          <div v-if="store.choices.length && !isTyping" class="choice-area">
            <button v-for="c in store.choices" :key="c.id"
              class="choice-btn"
              :class="{
                warp: c.source === 'special_warp',
                chosen: chosenIds.has(c.id),
                'scene-transition': isSceneTransition(c),
              }"
              :disabled="chosenIds.has(c.id)"
              @click="handleChoice(c)"
            >
              <span class="choice-text">{{ c.text }}</span>
              <span v-if="chosenIds.has(c.id)" class="chosen-mark">✓</span>
              <span v-if="c.source === 'special_warp'" class="warp-tag">跃迁</span>
              <span v-if="isSceneTransition(c)" class="transition-icon">→</span>
            </button>
          </div>
        </div>

        <!-- Action bar -->
        <div class="save-bar">
          <button class="save-btn" @click="showBackpack = !showBackpack">🎒 背包</button>
          <button class="save-btn" @click="doSave">💾 存档</button>
          <button class="save-btn" @click="showLoadPanel = !showLoadPanel">📂 读档</button>
        </div>
        <div v-if="showBackpack" class="load-panel">
          <div v-if="!store.currentState || store.currentState.inventory.length === 0" class="load-empty">背包空空如也</div>
          <div v-for="(item, idx) in (store.currentState?.inventory ?? [])" :key="idx" class="load-row">
            <span class="load-name">{{ item.name }}</span>
            <button v-if="isDiscardable(item)" @click="discardItem(idx)" class="del">丢弃</button>
          </div>
          <button class="close-btn" @click="showBackpack = false">关闭</button>
        </div>
        <div v-if="showLoadPanel" class="load-panel">...同上...</div>
      </template>

      <div v-else class="start-screen">
        <div class="start-content">
          <h1>荔湾<span class="divider">·</span>四日轮回</h1>
          <p>荔湾广场之下，时间如莫比乌斯环般扭曲</p>
          <button class="start-btn" @click="store.init()">踏入循环</button>
        </div>
      </div>
    </div>

    <CycleMap v-if="showMap && store.currentState"
      :current-id="store.currentNode?.id ?? 'A'" :visited-ids="store.currentState.visited_nodes"
      :has-warp-access="store.currentState.flags?.taoist_chant === true" />

    <div v-if="sceneEffect === 'notify' && notifyText" class="scene-notify">{{ notifyText }}</div>
    <div v-if="store.cycleEvent" class="cycle-toast">
      <span class="cycle-icon">⟳</span> 第 {{ store.cycleEvent.cycle_count }} 次循环完成
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch, nextTick } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import StatusBar from '@/components/player/StatusBar.vue'
import CycleMap from '@/components/player/CycleMap.vue'
import axios from 'axios'

const store = useGameStore()
const mainRef = ref<HTMLElement | null>(null)
onMounted(() => { store.init() })

// ── Transitions — accumulate selected choice narratives ──
const transitions = ref<Array<{ label: string; text: string }>>([])
const chosenIds = ref<Set<string>>(new Set())
const displayedText = ref('')
const isTyping = ref(false)
let typingTimer: ReturnType<typeof setInterval> | null = null
let prevNodeId = ''

// Reset when node changes
watch(() => store.currentNode?.id, (newId) => {
  if (newId && newId !== prevNodeId) {
    prevNodeId = newId
    transitions.value = []
    chosenIds.value = new Set()
    isTyping.value = false
    displayedText.value = ''
    startTypewriter()
  }
}, { immediate: true })

// Also clear transitions when content changes (same node, different content = new segment)
watch(() => store.currentNode?.content, (newContent, oldContent) => {
  if (newContent && newContent !== oldContent && oldContent) {
    transitions.value = []
    chosenIds.value = new Set()
  }
  if (!displayedText.value && newContent) startTypewriter()
})

const renderedContent = computed(() => store.currentNode ? md2html(store.currentNode.content) : '')

function startTypewriter() {
  if (typingTimer) clearInterval(typingTimer)
  const raw = store.currentNode?.content ?? ''
  if (!raw) { isTyping.value = false; return }
  isTyping.value = true
  displayedText.value = ''
  let i = 0
  typingTimer = setInterval(() => {
    i++
    if (i >= raw.length) {
      displayedText.value = md2html(raw)
      isTyping.value = false
      if (typingTimer) clearInterval(typingTimer)
      return
    }
    displayedText.value = md2html(raw.slice(0, i))
  }, 25)
}

// ── Choice handling ──
async function handleChoice(choice: any) {
  if (isTyping.value || chosenIds.value.has(choice.id) || store.loading) return

  const label = choice.text
  chosenIds.value = new Set([...chosenIds.value, choice.id])

  await store.choose(choice.id)

  // If transition text came back, show it
  if (store.transitionText) {
    transitions.value.push({ label, text: md2html(store.transitionText) })
    // Clear transition so it doesn't persist
    if (store.currentFrame) {
      store.currentFrame = { ...store.currentFrame, transition_text: undefined }
    }
  }

  // If node changed, reset
  if (store.currentNode && store.currentNode.id !== prevNodeId) {
    prevNodeId = store.currentNode.id
    transitions.value = []
    chosenIds.value = new Set()
    displayedText.value = ''
    startTypewriter()
  }

  scrollDown()
}

function isSceneTransition(c: any): boolean {
  // Choices that change scene: go to a different node, not "stay on same"
  return c.id && store.currentNode && c.next_node_id !== store.currentNode.id
}

function onBgClick() {
  if (isTyping.value) { skipTypewriter(); return }
}

function skipTypewriter() {
  if (typingTimer) clearInterval(typingTimer)
  displayedText.value = renderedContent.value
  isTyping.value = false
}

function scrollDown() {
  nextTick(() => { if (mainRef.value) mainRef.value.scrollTop = mainRef.value.scrollHeight })
}

function md2html(t: string): string {
  t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  t = t.replace(/\*(.+?)\*/g, '<em>$1</em>')
  t = t.replace(/---/g, '<span class="scene-break">· · ·</span>')
  t = t.replace(/\n\n/g, '</p><p>')
  return `<p>${t}</p>`
}

// ── Extras ──
const bgTintStyle = computed(() => {
  const p = store.currentNode?.color_palette
  if (!p) return {}
  const c = p.split('+')[0]?.trim()
  return c ? { background: `radial-gradient(ellipse at center, transparent 40%, ${c}10 100%)` } : {}
})

let ambientAudio: HTMLAudioElement | null = null
watch(() => store.currentNode?.ambient, (s) => {
  if (ambientAudio) { ambientAudio.pause(); ambientAudio = null }
  if (s) { ambientAudio = new Audio(s); ambientAudio.loop = true; ambientAudio.volume = 0.3; ambientAudio.play().catch(() => {}) }
})

const sceneEffect = ref<string | null>(null); const notifyText = ref('')
watch(() => store.currentFrame?.scene_effects, (fx) => {
  if (!fx?.length) return
  for (const e of fx) {
    if (e.type === 'notify') { notifyText.value = e.target || ''; sceneEffect.value = 'notify'; setTimeout(() => sceneEffect.value = null, 2500) }
  }
})

const showBackpack = ref(false); const showMap = ref(false)
const DISCARDABLE = new Set(['item_qing_coin','item_denim_rag','item_warning_note','item_old_newspaper'])
function isDiscardable(it: any) { return DISCARDABLE.has(it.id) }
function discardItem(i: number) { store.currentState?.inventory.splice(i, 1) }

const showLoadPanel = ref(false); const saveList = ref<any[]>([])
async function refreshSaves() { try { const r = await axios.get('/api/saves'); saveList.value = r.data.saves ?? [] } catch {} }
async function doSave() {
  if (!store.currentState) return
  const n = prompt('存档名称:', '存档 ' + new Date().toLocaleTimeString())
  if (!n) return
  try { await axios.post('/api/saves?name=' + encodeURIComponent(n), store.currentState); alert('存档成功') } catch { alert('存档失败') }
}
watch(showLoadPanel, (v) => { if (v) refreshSaves() })
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.game-play { width:100vw; height:100vh; overflow:hidden; display:flex; flex-direction:column; position:relative; background:$bg-void; }
.bg-layer { position:fixed; inset:0; z-index:0; pointer-events:none; }
.bg-vignette { position:absolute; inset:0; background:radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.6) 100%); animation:breathe 8s ease-in-out infinite; }
@keyframes breathe { 0%,100%{opacity:0.6} 50%{opacity:0.9} }

.game-main { position:relative; z-index:1; flex:1; overflow-y:auto; padding-bottom:4rem; }
.content-wrapper { max-width:$narrative-max-width; margin:0 auto; padding:1rem 1.5rem; }

.loading { display:flex; justify-content:center; align-items:center; height:60vh; }
.dot { font-size:3rem; color:$accent-gold; animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:0.15} 50%{opacity:1} }
.error { text-align:center; padding:4rem; color:$accent-red;
  button { margin-top:1rem; padding:0.5rem 2rem; background:transparent; border:1px solid rgba($accent-gold,0.3); color:$accent-gold; cursor:pointer; font-family:$font-ui; }
}

.time-label { text-align:center; color:$text-dim; font-family:$font-ui; font-size:0.85rem; padding:0.8rem 0 0.5rem; }
.speaker-row { display:flex; align-items:center; gap:0.6rem; padding:0.5rem 0 0.3rem; }
.speaker-avatar { width:36px; height:36px; border-radius:50%; background:rgba($accent-gold,0.08); border:1px solid rgba($accent-gold,0.25); display:flex; align-items:center; justify-content:center; color:$accent-gold; font-family:$font-display; font-size:1rem; font-weight:600; flex-shrink:0; }
.speaker-name { color:$accent-gold; font-family:$font-ui; font-size:0.9rem; }

.narrative-box { margin:0.5rem 0; }
.narrative-text { font-size:1rem; line-height:1.85;
  :deep(p) { margin-bottom:0.8rem; text-indent:2em; &:first-child { text-indent:0; } }
  :deep(strong) { color:$accent-gold; font-weight:700; }
  :deep(em) { color:$text-secondary; }
  :deep(.scene-break) { display:block; text-align:center; color:$accent-red; margin:1.5rem 0; font-family:$font-display; letter-spacing:0.8em; }
}

// Transition inline
.transition-inline { margin:0.8rem 0; padding:0.8rem 1rem; background:rgba($accent-gold,0.04); border-left:2px solid rgba($accent-gold,0.4); animation:fadeIn 0.3s ease-out; }
@keyframes fadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
.chosen-label { font-family:$font-ui; font-size:0.75rem; color:rgba($accent-gold,0.5); margin-bottom:0.3rem; }
.transition-text { color:$text-secondary; font-size:0.95rem; line-height:1.8;
  :deep(p) { margin-bottom:0.6rem; text-indent:2em; &:first-child { text-indent:0; } }
  :deep(strong) { color:$accent-gold; }
}

// Choices
.choice-area { margin:1rem 0; }
.choice-btn { display:block; width:100%; padding:0.85rem 1.2rem; margin-bottom:0.5rem;
  background:linear-gradient(135deg, rgba(26,20,16,0.95), rgba(30,24,18,0.9));
  border:1px solid rgba($accent-gold,0.18); border-left:3px solid rgba($accent-gold,0.35);
  color:$text-primary; font-family:$font-body; font-size:0.95rem; letter-spacing:0.03em; text-align:left; cursor:pointer; transition:all 0.2s; position:relative;
  &:hover:not(.chosen) { border-color:rgba($accent-gold,0.5); border-left-color:$accent-gold; transform:translateX(2px); }
  &.chosen { opacity:0.35; cursor:default; border-left-color:rgba($text-dim,0.3);
    .choice-text { text-decoration:line-through; }
  }
  &.warp { border-color:rgba($accent-ghost,0.35); border-left-color:rgba($accent-ghost,0.6); border-style:dashed; }
  &.scene-transition { border-color:rgba($accent-red,0.25); border-left-color:rgba($accent-red,0.5); background:linear-gradient(135deg, rgba(20,14,14,0.95), rgba(26,16,16,0.9));
    &:hover:not(.chosen) { border-color:rgba($accent-red,0.5); border-left-color:$accent-red; background:linear-gradient(135deg, rgba(30,18,18,0.95), rgba(36,20,20,0.9)); }
  }
}
.transition-icon { position:absolute; right:0.8rem; top:50%; transform:translateY(-50%); color:rgba($accent-red,0.6); font-size:1rem; }
.chosen-mark { position:absolute; right:0.8rem; top:50%; transform:translateY(-50%); color:$accent-gold; font-size:0.8rem; }
.warp-tag { position:absolute; right:0.8rem; top:50%; transform:translateY(-50%); font-family:$font-ui; font-size:0.65rem; color:rgba($accent-ghost,0.6); border:1px solid rgba($accent-ghost,0.25); padding:0.1rem 0.4rem; border-radius:2px; }

// Action bar
.save-bar { display:flex; gap:0.5rem; justify-content:center; padding:0.5rem 0 2rem; }
.save-btn { padding:0.3rem 1rem; background:transparent; border:1px solid rgba($accent-gold,0.2); color:$text-dim; font-family:$font-ui; font-size:0.8rem; cursor:pointer; border-radius:3px;
  &:hover { border-color:$accent-gold; color:$accent-gold; }
}
.load-panel { max-width:400px; margin:0 auto 1rem; padding:1rem; background:rgba($bg-void,0.95); border:1px solid rgba($accent-gold,0.15); border-radius:6px; }
.load-empty { color:$text-dim; text-align:center; padding:1rem; font-size:0.85rem; }
.load-row { display:flex; align-items:center; gap:0.5rem; padding:0.4rem 0; border-bottom:1px solid rgba($accent-gold,0.06);
  button { padding:0.2rem 0.6rem; background:transparent; border:1px solid rgba($accent-gold,0.2); color:$text-secondary; font-family:$font-ui; font-size:0.75rem; cursor:pointer; border-radius:2px;
    &:hover { border-color:$accent-gold; color:$accent-gold; }
    &.del { border-color:rgba($accent-red,0.2); color:rgba($accent-red,0.6); &:hover { border-color:$accent-red; color:$accent-red; } }
  }
}
.load-name { flex:1; color:$text-primary; font-size:0.85rem; }
.close-btn { display:block; margin:0.5rem auto 0; padding:0.3rem 1.5rem; background:transparent; border:1px solid rgba($accent-gold,0.15); color:$text-dim; font-size:0.8rem; cursor:pointer; }

.start-screen { display:flex; align-items:center; justify-content:center; height:100%; }
.start-content { text-align:center; }
h1 { font-family:$font-display; font-size:3rem; font-weight:700; color:$accent-gold; letter-spacing:0.15em; margin-bottom:0.5rem; }
.divider { color:$accent-red; margin:0 0.3rem; }
.start-screen p { color:$text-dim; font-size:0.95rem; margin-bottom:2.5rem; }
.start-btn { padding:0.8rem 3.5rem; font-size:1.1rem; background:transparent; color:$accent-red; border:1px solid rgba($accent-red,0.4); font-family:$font-display; letter-spacing:0.1em; cursor:pointer;
  &:hover { background:rgba($accent-red,0.1); border-color:$accent-red; }
}

.scene-notify { position:fixed; top:15%; left:50%; transform:translateX(-50%); z-index:310; color:$accent-gold; font-family:$font-display; font-size:1.2rem; pointer-events:none; animation:notifyAnim 2.5s ease-out; }
@keyframes notifyAnim { 0%{opacity:0;transform:translateX(-50%) translateY(-10px)} 15%{opacity:1;transform:translateX(-50%) translateY(0)} 70%{opacity:1} 100%{opacity:0} }

.cycle-toast { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:100; color:$accent-gold; font-family:$font-display; font-size:1.1rem; pointer-events:none; animation:cycleFade 3s infinite; }
.cycle-icon { display:inline-block; animation:spin 8s linear infinite; }
@keyframes cycleFade { 0%,100%{opacity:0} 50%{opacity:1} }
@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
</style>
