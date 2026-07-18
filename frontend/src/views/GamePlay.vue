<!-- GamePlay.vue — 视觉小说主界面 (inline expand mode) -->
<template>
  <div class="game-play">
    <div class="bg-layer" :style="bgTintStyle"><div class="bg-vignette" /></div>

    <StatusBar
      v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count"
      :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes"
      :inventory="store.currentState.inventory"
      :node-name="store.currentNode?.name"
      @toggle-map="showMap = !showMap"
    />

    <div class="game-main" ref="mainRef">
      <div v-if="store.loading && segments.length === 0" class="loading"><span class="dot">·</span></div>
      <div v-else-if="store.error" class="error"><p>{{ store.error }}</p><button @click="store.init()">重试</button></div>

      <template v-else-if="store.currentNode">
        <div class="content-wrapper" :key="store.currentNode.id">
          <div v-if="store.currentNode.time_label" class="time-label">◈ {{ store.currentNode.time_label }}</div>
          <div v-if="store.currentNode.speaker" class="speaker-row">
            <div class="speaker-avatar">{{ store.currentNode.speaker[0] }}</div>
            <span class="speaker-name">{{ store.currentNode.speaker }}</span>
          </div>

          <!-- Render accumulated segments -->
          <div v-for="(seg, si) in segments" :key="si" class="segment">
            <!-- Narrative text -->
            <div class="narrative-box" v-if="seg.text">
              <div class="narrative-text" v-html="seg.rendered" />
            </div>

            <!-- Choices that were available for this segment -->
            <div v-if="seg.choices.length && !seg.resolved" class="choice-area">
              <button
                v-for="c in visibleChoices(seg)" :key="c.id"
                class="choice-btn" :class="{ warp: c.source === 'special_warp' }"
                @click="pickChoice(si, c)"
              >
                <span class="choice-text">{{ c.text }}</span>
                <span v-if="c.source === 'special_warp'" class="warp-tag">跃迁</span>
              </button>
            </div>

            <!-- Selected choice transition text (inline) -->
            <div v-if="seg.selectedTransition" class="transition-inline" @click="advanceSegment(si)">
              <div class="transition-text" v-html="seg.selectedTransition" />
              <p class="dismiss-hint">— 点击继续 —</p>
            </div>
          </div>

          <!-- Current choices (not yet in a segment) -->
          <div v-if="store.choices.length && !isTyping && !waitingForTransition" class="choice-area">
            <button
              v-for="c in store.choices" :key="c.id"
              class="choice-btn" :class="{ warp: c.source === 'special_warp' }"
              @click="pickChoice(-1, c)"
            >
              <span class="choice-text">{{ c.text }}</span>
              <span v-if="c.source === 'special_warp'" class="warp-tag">跃迁</span>
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

    <div v-if="sceneEffect === 'shake'" class="scene-shake" />
    <div v-if="sceneEffect === 'flash'" class="scene-flash" :style="flashStyle" />
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

// ── Segment system ──
interface Segment {
  text: string
  rendered: string
  choices: any[]
  resolved: boolean
  selectedId: string | null
  selectedTransition: string | null
  nodeId: string
}

const segments = ref<Segment[]>([])
const waitingForTransition = ref(false)

// When node changes, add initial segment
watch(() => store.currentNode?.id, (newId, oldId) => {
  if (!newId) return
  if (newId !== oldId) {
    // New node — clear segments and start fresh
    segments.value = []
    waitingForTransition.value = false
    if (store.currentNode) {
      addSegment(store.currentNode.content, [])
    }
  }
})

watch(() => store.currentNode?.content, (content) => {
  if (!content || segments.value.length > 0) return
  addSegment(content, [])
})

function addSegment(text: string, choices: any[]) {
  segments.value.push({
    text,
    rendered: md2html(text),
    choices: JSON.parse(JSON.stringify(choices)),
    resolved: false,
    selectedId: null,
    selectedTransition: null,
    nodeId: store.currentNode?.id ?? '',
  })
  scrollDown()
}

// ── Typewriter for latest segment ──
const TYPING_SPEED = 25
const isTyping = ref(false)
const displayedText = ref('')
let typingTimer: ReturnType<typeof setInterval> | null = null

function startTypewriter(seg: Segment) {
  if (typingTimer) clearInterval(typingTimer)
  const raw = seg.text
  if (!raw) { seg.rendered = ''; isTyping.value = false; return }
  isTyping.value = true
  displayedText.value = ''
  let i = 0
  typingTimer = setInterval(() => {
    i++
    if (i >= raw.length) {
      seg.rendered = md2html(raw)
      isTyping.value = false
      if (typingTimer) clearInterval(typingTimer)
      return
    }
    seg.rendered = md2html(raw.slice(0, i))
  }, TYPING_SPEED)
}

function skipTypewriter() {
  if (isTyping.value) {
    if (typingTimer) clearInterval(typingTimer)
    const last = segments.value[segments.value.length - 1]
    if (last) last.rendered = md2html(last.text)
    isTyping.value = false
  }
}

// ── Choice handling ──
function visibleChoices(seg: Segment) {
  return seg.choices.filter(c => !seg.resolved || c.id === seg.selectedId)
}

async function pickChoice(segIdx: number, choice: any) {
  if (waitingForTransition.value) return

  // If this is a "current" choice (not from a segment), use store.choose
  if (segIdx === -1) {
    // Mark current choices as resolved
    waitingForTransition.value = true
    await store.choose(choice.id)
    // store.choose updated currentFrame — now handle the result
    if (store.transitionText) {
      // Add transition text to the last segment or as new content
      const lastSeg = segments.value[segments.value.length - 1]
      if (lastSeg) {
        lastSeg.selectedTransition = store.transitionText
        lastSeg.resolved = true
        lastSeg.selectedId = choice.id
        lastSeg.choices = JSON.parse(JSON.stringify(store.choices)) // snapshot choices
      }
    }
    // After clicking "continue" on transition, advance
    waitingForTransition.value = false
    if (store.currentNode) {
      addSegment(store.currentNode.content, store.choices)
      startTypewriter(segments.value[segments.value.length - 1])
    }
    return
  }

  // Segment-based choice
  const seg = segments.value[segIdx]
  if (!seg || seg.resolved) return

  waitingForTransition.value = true
  seg.resolved = true
  seg.selectedId = choice.id
  seg.selectedTransition = choice.transition_text || null

  await store.choose(choice.id)

  if (store.transitionText) {
    seg.selectedTransition = store.transitionText
  }

  waitingForTransition.value = false

  // If returned to same node, add new segment
  if (store.currentNode && store.currentNode.id === seg.nodeId) {
    addSegment(store.currentNode.content, store.choices)
    startTypewriter(segments.value[segments.value.length - 1])
  }
}

function advanceSegment(segIdx: number) {
  const seg = segments.value[segIdx]
  if (!seg) return
  seg.selectedTransition = null
  scrollDown()
}

function scrollDown() {
  nextTick(() => {
    if (mainRef.value) mainRef.value.scrollTop = mainRef.value.scrollHeight
  })
}

// ── Markdown ──
function md2html(t: string): string {
  t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  t = t.replace(/\*(.+?)\*/g, '<em>$1</em>')
  t = t.replace(/---/g, '<span class="scene-break">· · ·</span>')
  t = t.replace(/\n\n/g, '</p><p>')
  return `<p>${t}</p>`
}

// ── Ambient audio ──
let ambientAudio: HTMLAudioElement | null = null
watch(() => store.currentNode?.ambient, (src) => {
  if (ambientAudio) { ambientAudio.pause(); ambientAudio = null }
  if (src) { ambientAudio = new Audio(src); ambientAudio.loop = true; ambientAudio.volume = 0.3; ambientAudio.play().catch(() => {}) }
})

// ── Color tint ──
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
watch(() => store.currentFrame?.scene_effects, (effects) => {
  if (!effects?.length) return
  for (const e of effects) {
    if (e.type === 'notify') { notifyText.value = e.target || e.value || ''; sceneEffect.value = 'notify'; setTimeout(() => { sceneEffect.value = null }, 2500) }
    if (e.type === 'shake') { sceneEffect.value = 'shake'; setTimeout(() => { sceneEffect.value = null }, 500) }
    if (e.type === 'flash') { flashStyle.value = { background: e.target || 'rgba(255,255,255,0.1)' }; sceneEffect.value = 'flash'; setTimeout(() => { sceneEffect.value = null }, 300) }
  }
})

// ── Backpack ──
const showBackpack = ref(false)
const showMap = ref(false)
const DISCARDABLE_ITEMS = new Set(['item_qing_coin','item_denim_rag','item_warning_note','item_old_newspaper'])
function isDiscardable(item: any) { return DISCARDABLE_ITEMS.has(item.id) }
function discardItem(idx: number) { if (store.currentState) store.currentState.inventory.splice(idx, 1) }

// ── Save/Load ──
const showLoadPanel = ref(false)
const saveList = ref<any[]>([])
async function refreshSaveList() { try { const r = await axios.get('/api/saves'); saveList.value = r.data.saves ?? [] } catch {} }
async function doSave() {
  if (!store.currentState) return
  const name = prompt('存档名称:', '存档 ' + new Date().toLocaleTimeString())
  if (!name) return
  try { await axios.post('/api/saves?name=' + encodeURIComponent(name), store.currentState); alert('存档成功') } catch { alert('存档失败') }
}
async function doLoad(saveId: string) {
  try { const r = await axios.get('/api/saves/load/' + saveId); const state = r.data; const frame = await (await import('@/api/game')).startGame(); store.currentFrame = { ...frame, state, node: frame.node }; showLoadPanel.value = false } catch { alert('读档失败') }
}
async function doDelete(saveId: string) { if (!confirm('确认删除？')) return; try { await axios.delete('/api/saves/' + saveId); refreshSaveList() } catch {} }
watch(showLoadPanel, (v) => { if (v) refreshSaveList() })
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

// Segment
.segment { margin-bottom:0.5rem; }

// Time
.time-label { text-align:center; color:$text-dim; font-family:$font-ui; font-size:0.85rem; padding:0.8rem 0 0.5rem; letter-spacing:0.1em; }

// Speaker
.speaker-row { display:flex; align-items:center; gap:0.6rem; padding:0.5rem 0 0.3rem; }
.speaker-avatar { width:36px; height:36px; border-radius:50%; background:rgba($accent-gold,0.08); border:1px solid rgba($accent-gold,0.25); display:flex; align-items:center; justify-content:center; color:$accent-gold; font-family:$font-display; font-size:1rem; font-weight:600; flex-shrink:0; }
.speaker-name { color:$accent-gold; font-family:$font-ui; font-size:0.9rem; font-weight:500; }

// Narrative
.narrative-box { margin:0.5rem 0; }
.narrative-text { font-size:1rem; line-height:1.85; letter-spacing:0.02em;
  :deep(p) { margin-bottom:0.8rem; text-indent:2em; &:first-child { text-indent:0; } }
  :deep(strong) { color:$accent-gold; font-weight:700; }
  :deep(em) { color:$text-secondary; font-style:italic; }
  :deep(.scene-break) { display:block; text-align:center; color:$accent-red; margin:1.5rem 0; font-family:$font-display; letter-spacing:0.8em; font-size:1rem; }
}

// Choices
.choice-area { margin:1rem 0; }
.choice-btn { display:block; width:100%; padding:0.85rem 1.2rem; margin-bottom:0.5rem;
  background:linear-gradient(135deg, rgba(26,20,16,0.95), rgba(30,24,18,0.9));
  border:1px solid rgba($accent-gold,0.18); border-left:3px solid rgba($accent-gold,0.35);
  color:$text-primary; font-family:$font-body; font-size:0.95rem; letter-spacing:0.03em; text-align:left; cursor:pointer; transition:all 0.2s; position:relative;
  &:hover { border-color:rgba($accent-gold,0.5); border-left-color:$accent-gold; transform:translateX(2px); }
  &.warp { border-color:rgba($accent-ghost,0.35); border-left-color:rgba($accent-ghost,0.6); border-style:dashed; }
}
.warp-tag { position:absolute; right:0.8rem; top:50%; transform:translateY(-50%); font-family:$font-ui; font-size:0.65rem; color:rgba($accent-ghost,0.6); border:1px solid rgba($accent-ghost,0.25); padding:0.1rem 0.4rem; border-radius:2px; }

// Transition inline
.transition-inline { margin:0.8rem 0; padding:0.8rem 1rem; background:rgba($accent-gold,0.04); border-left:2px solid $accent-gold; cursor:pointer; animation:fadeIn 0.3s ease-out; }
@keyframes fadeIn { from { opacity:0; transform:translateY(4px); } to { opacity:1; transform:translateY(0); } }
.transition-text { color:$text-secondary; font-size:0.95rem; line-height:1.8;
  :deep(p) { margin-bottom:0.6rem; text-indent:2em; &:first-child { text-indent:0; } }
  :deep(strong) { color:$accent-gold; }
}
.dismiss-hint { text-align:right; color:$text-dim; font-size:0.7rem; margin-top:0.3rem; }

// Bars
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
.load-meta { color:$text-dim; font-size:0.7rem; }
.close-btn { display:block; margin:0.5rem auto 0; padding:0.3rem 1.5rem; background:transparent; border:1px solid rgba($accent-gold,0.15); color:$text-dim; font-family:$font-ui; font-size:0.8rem; cursor:pointer; border-radius:3px; }

// Start screen
.start-screen { display:flex; align-items:center; justify-content:center; height:100%; }
.start-content { text-align:center; }
h1 { font-family:$font-display; font-size:3rem; font-weight:700; color:$accent-gold; letter-spacing:0.15em; margin-bottom:0.5rem; }
.divider { color:$accent-red; margin:0 0.3rem; }
.start-screen p { color:$text-dim; font-size:0.95rem; margin-bottom:2.5rem; }
.start-btn { padding:0.8rem 3.5rem; font-size:1.1rem; background:transparent; color:$accent-red; border:1px solid rgba($accent-red,0.4); font-family:$font-display; letter-spacing:0.1em; cursor:pointer;
  &:hover { background:rgba($accent-red,0.1); border-color:$accent-red; box-shadow:0 0 20px rgba($accent-red,0.15); }
}

// Effects
.scene-shake { position:fixed; inset:0; z-index:300; pointer-events:none; animation:shake 0.4s ease-out; }
@keyframes shake { 0%,100%{transform:translateX(0)} 20%{transform:translateX(-6px)} 40%{transform:translateX(6px)} 60%{transform:translateX(-4px)} 80%{transform:translateX(4px)} }
.scene-flash { position:fixed; inset:0; z-index:299; pointer-events:none; animation:flashAnim 0.3s ease-out; }
@keyframes flashAnim { from{opacity:1} to{opacity:0} }
.scene-notify { position:fixed; top:15%; left:50%; transform:translateX(-50%); z-index:310; color:$accent-gold; font-family:$font-display; font-size:1.2rem; pointer-events:none; animation:notifyAnim 2.5s ease-out; }
@keyframes notifyAnim { 0%{opacity:0;transform:translateX(-50%) translateY(-10px)} 15%{opacity:1;transform:translateX(-50%) translateY(0)} 70%{opacity:1} 100%{opacity:0} }

.cycle-toast { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:100; color:$accent-gold; font-family:$font-display; font-size:1.1rem; pointer-events:none; animation:cycleFade 3s infinite; }
.cycle-icon { display:inline-block; animation:spin 8s linear infinite; }
@keyframes cycleFade { 0%,100%{opacity:0} 50%{opacity:1} }
@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
</style>
