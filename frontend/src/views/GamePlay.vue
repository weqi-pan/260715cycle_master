<!-- GamePlay.vue — 视觉小说主界面 -->
<template>
  <div class="game-play" @click="onBgClick">
    <!-- z-0: Background layer -->
    <div class="bg-layer" :style="bgTintStyle">
      <div class="bg-vignette" />
    </div>

    <!-- z-100: Status bar -->
    <StatusBar
      v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count"
      :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes"
      :inventory="store.currentState.inventory"
      :node-name="store.currentNode?.name"
    />

    <!-- Main content area -->
    <div class="game-main">
      <!-- Loading -->
      <div v-if="store.loading" class="loading"><span class="dot">·</span></div>

      <!-- Error -->
      <div v-else-if="store.error" class="error">
        <p>{{ store.error }}</p>
        <button @click="store.init()">重试</button>
      </div>

      <!-- Game content -->
      <template v-else-if="store.currentNode">
        <div class="content-wrapper" :key="store.currentNode.id" :class="transitionClass">
          <!-- Time label -->
          <div v-if="store.currentNode.time_label" class="time-label">
            ◈ {{ store.currentNode.time_label }}
          </div>

          <!-- Speaker -->
          <div v-if="store.currentNode.speaker" class="speaker-row">
            <div class="speaker-avatar">{{ store.currentNode.speaker[0] }}</div>
            <span class="speaker-name">{{ store.currentNode.speaker }}</span>
          </div>

          <!-- Narrative with typewriter -->
          <div class="narrative-box" @click.stop="skipTypewriter">
            <div class="narrative-text" v-html="displayedText" />
          </div>

          <!-- Choices -->
          <div v-if="store.choices.length && !isTyping" class="choice-area">
            <button
              v-for="c in store.choices" :key="c.id"
              class="choice-btn"
              :class="{ warp: c.source === 'special_warp' }"
              @click="store.choose(c.id)"
            >
              <span class="choice-text">{{ c.text }}</span>
              <span v-if="c.source === 'special_warp'" class="warp-tag">跃迁</span>
            </button>
          </div>

          <!-- Continue hint (no choices, typing done) -->
          <div v-else-if="!isTyping" class="continue-hint" @click.stop="dismissTransition">
            <span class="arrow">▼</span>
          </div>
          <!-- Save/Load bar -->
          <div class="save-bar">
            <button class="save-btn" @click="doSave" :disabled="store.loading">💾 存档</button>
            <button class="save-btn" @click="showLoadPanel = !showLoadPanel">📂 读档</button>
          </div>

          <!-- Load panel -->
          <div v-if="showLoadPanel" class="load-panel">
            <div v-if="saveList.length === 0" class="load-empty">暂无存档</div>
            <div v-for="s in saveList" :key="s.id" class="load-row">
              <span class="load-name">{{ s.save_name || s.id }}</span>
              <span class="load-meta">节点{{ s.current_node_id }} · 循环{{ s.cycle_count }}</span>
              <button @click="doLoad(s.id)">读取</button>
              <button @click="doDelete(s.id)" class="del">删除</button>
            </div>
            <button class="close-btn" @click="showLoadPanel = false">关闭</button>
          </div>
        </div>
      </template>

      <!-- Start screen -->
      <div v-else class="start-screen">
        <div class="start-content">
          <h1>荔湾<span class="divider">·</span>四日轮回</h1>
          <p>荔湾广场之下，时间如莫比乌斯环般扭曲</p>
          <button class="start-btn" @click="store.init()">踏入循环</button>
        </div>
      </div>
    </div>

    <!-- Transition overlay -->
    <Teleport to="body">
      <div v-if="store.transitionText" class="transition-overlay" @click="dismissTransition">
        <div class="transition-box">
          <div class="transition-text" v-html="renderedTransition" />
          <p class="dismiss-hint">— 点击任意处继续 —</p>
        </div>
      </div>
    </Teleport>

    <!-- Cycle Map -->
    <CycleMap
      v-if="store.currentState"
      :current-id="store.currentNode?.id ?? 'A'"
      :visited-ids="store.currentState.visited_nodes"
      :has-warp-access="store.currentState.flags?.taoist_chant === true"
    />

    <!-- Scene effect: shake -->
    <div v-if="sceneEffect === 'shake'" class="scene-shake" />
    <!-- Scene effect: flash -->
    <div v-if="sceneEffect === 'flash'" class="scene-flash" :style="flashStyle" />
    <!-- Scene effect: notify -->
    <div v-if="sceneEffect === 'notify' && notifyText" class="scene-notify">{{ notifyText }}</div>

    <!-- Cycle toast -->
    <div v-if="store.cycleEvent" class="cycle-toast">
      <span class="cycle-icon">⟳</span> 第 {{ store.cycleEvent.cycle_count }} 次循环完成
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import StatusBar from '@/components/player/StatusBar.vue'
import CycleMap from '@/components/player/CycleMap.vue'
import axios from 'axios'

const store = useGameStore()
onMounted(() => { store.init() })

// ── Typewriter ──
const TYPING_SPEED = 25 // ms per character
const displayedText = ref('')
const isTyping = ref(false)
let typingTimer: ReturnType<typeof setInterval> | null = null

const fullContent = computed(() => store.currentNode?.content ?? '')
const fullHtml = computed(() => md2html(fullContent.value))

watch(() => store.currentNode?.id, () => { startTypewriter() })
watch(() => store.currentNode?.content, () => { startTypewriter() })

function startTypewriter() {
  if (typingTimer) clearInterval(typingTimer)
  const raw = store.currentNode?.content ?? ''
  if (!raw) { displayedText.value = ''; isTyping.value = false; return }
  isTyping.value = true
  displayedText.value = ''
  let i = 0
  typingTimer = setInterval(() => {
    // Match Chinese chars, punctuation, HTML tags, and whitespace
    i++
    if (i >= raw.length) {
      displayedText.value = md2html(raw)
      isTyping.value = false
      if (typingTimer) clearInterval(typingTimer)
      return
    }
    displayedText.value = md2html(raw.slice(0, i))
  }, TYPING_SPEED)
}

function skipTypewriter() {
  if (isTyping.value) {
    if (typingTimer) clearInterval(typingTimer)
    displayedText.value = fullHtml.value
    isTyping.value = false
  }
}

// ── Markdown ──
function md2html(t: string): string {
  t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  t = t.replace(/\*(.+?)\*/g, '<em>$1</em>')
  t = t.replace(/---/g, '<span class="scene-break">· · ·</span>')
  t = t.replace(/\n\n/g, '</p><p>')
  return `<p>${t}</p>`
}

const renderedTransition = computed(() => store.transitionText ? md2html(store.transitionText) : '')

function dismissTransition() {
  if (store.currentFrame) {
    store.currentFrame = { ...store.currentFrame, transition_text: undefined }
  }
}
function onBgClick() {
  if (store.choices.length > 0) return
  dismissTransition()
}

// ── Ambient audio ──
let ambientAudio: HTMLAudioElement | null = null
watch(() => store.currentNode?.ambient, (src) => {
  if (ambientAudio) { ambientAudio.pause(); ambientAudio = null }
  if (src) {
    ambientAudio = new Audio(src)
    ambientAudio.loop = true
    ambientAudio.volume = 0.3
    ambientAudio.play().catch(() => {})
  }
})

// ── Color tint from node palette ──
const bgTintStyle = computed(() => {
  const palette = store.currentNode?.color_palette
  if (!palette) return {}
  const color = palette.split('+')[0]?.trim()
  return color ? { background: `radial-gradient(ellipse at center, transparent 40%, ${color}10 100%)` } : {}
})

// ── Scene effects ──
const sceneEffect = ref<string | null>(null)
const notifyText = ref('')
const flashStyle = ref({})
const transitionClass = ref('fade-in')

watch(() => store.currentNode?.id, () => {
  transitionClass.value = 'fade-in'
  setTimeout(() => { transitionClass.value = '' }, 500)
})

watch(() => store.currentFrame?.scene_effects, (effects) => {
  if (!effects?.length) return
  for (const e of effects) {
    if (e.type === 'notify') { notifyText.value = e.target || e.value || ''; sceneEffect.value = 'notify'; setTimeout(() => { sceneEffect.value = null }, 2500) }
    if (e.type === 'shake') { sceneEffect.value = 'shake'; setTimeout(() => { sceneEffect.value = null }, 500) }
    if (e.type === 'flash') { flashStyle.value = { background: e.target || 'rgba(255,255,255,0.1)' }; sceneEffect.value = 'flash'; setTimeout(() => { sceneEffect.value = null }, 300) }
  }
}, { deep: true })

// ── Save/Load ──
const showLoadPanel = ref(false)
const saveList = ref<any[]>([])

async function refreshSaveList() {
  try { const r = await axios.get('/api/saves'); saveList.value = r.data.saves ?? [] } catch {}
}
async function doSave() {
  if (!store.currentState) return
  const name = prompt('存档名称:', '存档 ' + new Date().toLocaleTimeString())
  if (!name) return
  try {
    await axios.post('/api/saves?name=' + encodeURIComponent(name), store.currentState)
    alert('存档成功')
  } catch { alert('存档失败') }
}
async function doLoad(saveId: string) {
  try {
    const r = await axios.get('/api/saves/load/' + saveId)
    const state = r.data
    // Restart game at saved state
    const frame = await (await import('@/api/game')).startGame()
    store.currentFrame = { ...frame, state, node: frame.node }
    // Re-resolve with correct state
    showLoadPanel.value = false
  } catch { alert('读档失败') }
}
async function doDelete(saveId: string) {
  if (!confirm('确认删除？')) return
  try { await axios.delete('/api/saves/' + saveId); refreshSaveList() } catch {}
}
watch(showLoadPanel, (v) => { if (v) refreshSaveList() })
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

// ── Layout ──
.game-play {
  width: 100vw; height: 100vh; overflow: hidden;
  display: flex; flex-direction: column;
  position: relative; background: $bg-void;
}

// ── Background ──
.bg-layer { position: fixed; inset: 0; z-index: 0; pointer-events: none; }
.bg-vignette {
  position: absolute; inset: 0;
  background: radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.6) 100%);
  animation: breathe 8s ease-in-out infinite;
}
@keyframes breathe { 0%,100%{opacity:0.6} 50%{opacity:0.9} }

// ── Main scrollable area ──
.game-main {
  position: relative; z-index: 1;
  flex: 1; overflow-y: auto; padding-bottom: 4rem;
}

.content-wrapper {
  max-width: $narrative-max-width; margin: 0 auto;
  padding: 1rem 1.5rem;
}

// ── Loading / Error ──
.loading { display:flex; justify-content:center; align-items:center; height:60vh; }
.dot { font-size:3rem; color:$accent-gold; animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:0.15} 50%{opacity:1} }
.error { text-align:center; padding:4rem; color:$accent-red;
  button { margin-top:1rem; padding:0.5rem 2rem; background:transparent; border:1px solid rgba($accent-gold,0.3); color:$accent-gold; cursor:pointer; font-family:$font-ui; }
}

// ── Time label ──
.time-label { text-align:center; color:$text-dim; font-family:$font-ui; font-size:0.85rem; padding:0.8rem 0 0.5rem; letter-spacing:0.1em; }

// ── Speaker ──
.speaker-row { display:flex; align-items:center; gap:0.6rem; padding:0.5rem 0 0.3rem; }
.speaker-avatar { width:36px; height:36px; border-radius:50%; background:rgba($accent-gold,0.08); border:1px solid rgba($accent-gold,0.25); display:flex; align-items:center; justify-content:center; color:$accent-gold; font-family:$font-display; font-size:1rem; font-weight:600; flex-shrink:0; }
.speaker-name { color:$accent-gold; font-family:$font-ui; font-size:0.9rem; font-weight:500; }

// ── Narrative ──
.narrative-box { margin:0.5rem 0; }
.narrative-text {
  font-size:1rem; line-height:1.85; letter-spacing:0.02em;
  :deep(p) { margin-bottom:0.8rem; text-indent:2em; &:first-child { text-indent:0; } }
  :deep(strong) { color:$accent-gold; font-weight:700; }
  :deep(em) { color:$text-secondary; font-style:italic; }
  :deep(.scene-break) { display:block; text-align:center; color:$accent-red; margin:1.5rem 0; font-family:$font-display; letter-spacing:0.8em; font-size:1rem; }
}

// ── Choices (talisman style) ──
.choice-area { margin:1.2rem 0; }
.choice-btn {
  display:block; width:100%; padding:0.85rem 1.2rem; margin-bottom:0.5rem;
  background:linear-gradient(135deg, rgba(26,20,16,0.95), rgba(30,24,18,0.9));
  border:1px solid rgba($accent-gold,0.18); border-left:3px solid rgba($accent-gold,0.35);
  color:$text-primary; font-family:$font-body; font-size:0.95rem; letter-spacing:0.03em;
  text-align:left; cursor:pointer; transition:all 0.2s; position:relative;
  &:hover { border-color:rgba($accent-gold,0.5); border-left-color:$accent-gold; background:linear-gradient(135deg, rgba(36,28,20,0.95), rgba(40,30,22,0.9)); transform:translateX(2px); }
  &.warp { border-color:rgba($accent-ghost,0.35); border-left-color:rgba($accent-ghost,0.6); border-style:dashed; background:linear-gradient(135deg, rgba(13,16,20,0.95), rgba(16,20,26,0.9));
    &:hover { border-color:rgba($accent-ghost,0.6); }
  }
}
.warp-tag { position:absolute; right:0.8rem; top:50%; transform:translateY(-50%); font-family:$font-ui; font-size:0.65rem; color:rgba($accent-ghost,0.6); border:1px solid rgba($accent-ghost,0.25); padding:0.1rem 0.4rem; border-radius:2px; }

// ── Continue hint ──
.continue-hint { text-align:center; padding:1rem 0; cursor:pointer; }
.arrow { color:$accent-gold; font-size:1.2rem; animation:blink 1.5s ease-in-out infinite; }
@keyframes blink { 0%,100%{opacity:0.3} 50%{opacity:1} }

// ── Start screen ──
.start-screen { display:flex; align-items:center; justify-content:center; height:100%; }
.start-content { text-align:center; }
h1 { font-family:$font-display; font-size:3rem; font-weight:700; color:$accent-gold; letter-spacing:0.15em; margin-bottom:0.5rem; }
.divider { color:$accent-red; margin:0 0.3rem; }
.start-screen p { color:$text-dim; font-size:0.95rem; margin-bottom:2.5rem; letter-spacing:0.05em; }
.start-btn { padding:0.8rem 3.5rem; font-size:1.1rem; background:transparent; color:$accent-red; border:1px solid rgba($accent-red,0.4); font-family:$font-display; letter-spacing:0.1em; cursor:pointer; transition:all 0.3s;
  &:hover { background:rgba($accent-red,0.1); border-color:$accent-red; box-shadow:0 0 20px rgba($accent-red,0.15); }
}

// ── Transition overlay ──
.transition-overlay { position:fixed; inset:0; z-index:200; background:rgba(0,0,0,0.88); display:flex; flex-direction:column; align-items:center; justify-content:center; cursor:pointer; }
.transition-box { max-width:$narrative-max-width; padding:2rem 2.5rem; }
.transition-text { color:$text-primary; font-size:1rem; line-height:1.85; letter-spacing:0.02em;
  :deep(p) { margin-bottom:0.8rem; text-indent:2em; &:first-child { text-indent:0; } }
  :deep(strong) { color:$accent-gold; }
  :deep(em) { color:$text-secondary; }
}
.dismiss-hint { text-align:center; color:$text-dim; font-size:0.8rem; margin-top:2rem; letter-spacing:0.1em; }

// ── Save/Load bar ──
.save-bar { display:flex; gap:0.5rem; justify-content:center; padding:0.5rem 0 2rem; }
.save-btn { padding:0.3rem 1rem; background:transparent; border:1px solid rgba($accent-gold,0.2); color:$text-dim; font-family:$font-ui; font-size:0.8rem; cursor:pointer; border-radius:3px;
  &:hover { border-color:$accent-gold; color:$accent-gold; }
}
.load-panel { max-width:400px; margin:0 auto 2rem; padding:1rem; background:rgba($bg-void,0.95); border:1px solid rgba($accent-gold,0.15); border-radius:6px; }
.load-empty { color:$text-dim; text-align:center; padding:1rem; font-size:0.85rem; }
.load-row { display:flex; align-items:center; gap:0.5rem; padding:0.4rem 0; border-bottom:1px solid rgba($accent-gold,0.06);
  button { padding:0.2rem 0.6rem; background:transparent; border:1px solid rgba($accent-gold,0.2); color:$text-secondary; font-family:$font-ui; font-size:0.75rem; cursor:pointer; border-radius:2px;
    &:hover { border-color:$accent-gold; color:$accent-gold; }
    &.del { border-color:rgba($accent-red,0.2); color:rgba($accent-red,0.6);
      &:hover { border-color:$accent-red; color:$accent-red; }
    }
  }
}
.load-name { flex:1; color:$text-primary; font-size:0.85rem; }
.load-meta { color:$text-dim; font-size:0.7rem; }
.close-btn { display:block; margin:0.5rem auto 0; padding:0.3rem 1.5rem; background:transparent; border:1px solid rgba($accent-gold,0.15); color:$text-dim; font-family:$font-ui; font-size:0.8rem; cursor:pointer; border-radius:3px; }

// ── Node transition ──
.fade-in { animation: fadeIn 0.4s ease-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

// ── Scene effects ──
.scene-shake { position: fixed; inset: 0; z-index: 300; pointer-events: none; animation: shake 0.4s ease-out; }
@keyframes shake { 0%,100%{transform:translateX(0)} 20%{transform:translateX(-6px)} 40%{transform:translateX(6px)} 60%{transform:translateX(-4px)} 80%{transform:translateX(4px)} }
.scene-flash { position: fixed; inset: 0; z-index: 299; pointer-events: none; animation: flashAnim 0.3s ease-out; }
@keyframes flashAnim { from { opacity: 1; } to { opacity: 0; } }
.scene-notify { position: fixed; top: 15%; left: 50%; transform: translateX(-50%); z-index: 310; color: $accent-gold; font-family: $font-display; font-size: 1.2rem; letter-spacing: 0.1em; pointer-events: none; animation: notifyAnim 2.5s ease-out; text-shadow: 0 0 10px rgba($accent-red,0.3); }
@keyframes notifyAnim { 0%{opacity:0;transform:translateX(-50%) translateY(-10px)} 15%{opacity:1;transform:translateX(-50%) translateY(0)} 70%{opacity:1} 100%{opacity:0} }

// ── Cycle toast ──
.cycle-toast { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:100; color:$accent-gold; font-family:$font-display; font-size:1.1rem; letter-spacing:0.1em; pointer-events:none; animation:cycleFade 3s infinite; }
.cycle-icon { display:inline-block; animation:spin 8s linear infinite; }
@keyframes cycleFade { 0%,100%{opacity:0} 50%{opacity:1} }
@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
</style>
