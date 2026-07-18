<!-- GamePlay.vue — 视觉小说主界面 -->
<template>
  <div class="game-play" @click="onGlobalClick">
    <div class="bg-layer" :style="bgTintStyle"><div class="bg-vignette" /></div>

    <StatusBar v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count" :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes" :inventory="store.currentState.inventory"
      :node-name="store.currentNode?.name"
      @toggle-map="showMap = !showMap" @toggle-backpack="showBP = !showBP" @save="doSave" @load="showLoad = !showLoad" />

    <div class="game-main" ref="mainRef">
      <div v-if="store.loading && !store.currentNode" class="loading"><span class="dot">·</span></div>
      <div v-else-if="store.error" class="error"><p>{{ store.error }}</p><button @click="store.init()">重试</button></div>

      <template v-else-if="store.currentNode">
        <div class="content-wrapper">
          <div v-if="store.currentNode.time_label" class="time-label">◈ {{ store.currentNode.time_label }}</div>

          <!-- Narration mode (no speaker) -->
          <template v-if="!store.currentNode.speaker">
            <div class="narrative-box">
              <div class="narrative-text" v-html="renderedContent" />
            </div>
            <div v-for="(t,i) in transitions" :key="'t'+i" class="transition-inline">
              <div class="transition-text" v-html="t.text" />
            </div>
          </template>

          <!-- Dialogue mode (has speaker) — chat bubbles -->
          <template v-else>
            <div class="dialogue-area">
              <div v-for="(line, i) in visibleLines" :key="'d'+i" class="chat-row" :class="{ me: i % 2 === 1 }">
                <div class="chat-avatar">{{ store.currentNode.speaker[0] }}</div>
                <div class="chat-bubble">
                  <div class="chat-name">{{ store.currentNode.speaker }}</div>
                  <div class="chat-text" v-html="line" />
                </div>
              </div>
            </div>
            <div v-if="hasMoreLines" class="continue-hint" @click.stop="nextLine">
              <span class="arrow">▼</span>
            </div>
            <div v-for="(t,i) in transitions" :key="'dt'+i" class="transition-inline">
              <div class="transition-text" v-html="t.text" />
            </div>
          </template>

          <!-- Choices -->
          <div v-if="canShowChoices" class="choice-area">
            <button v-for="c in store.choices" :key="c.id"
              class="choice-btn"
              :class="{ warp: c.source === 'special_warp', chosen: chosenIds.has(c.id), 'scene-transition': c.next_node_id !== store.currentNode?.id }"
              :disabled="chosenIds.has(c.id)"
              @click="handleChoice(c)"
            >
              <span class="choice-text">{{ c.text }}</span>
              <span v-if="chosenIds.has(c.id)" class="chosen-mark">✓</span>
              <span v-if="c.source === 'special_warp'" class="warp-tag">跃迁</span>
              <span v-if="c.next_node_id !== store.currentNode?.id" class="transition-icon">→</span>
            </button>
          </div>

          <!-- Panels -->
          <div v-if="showBP" class="panel">
            <div v-if="!store.currentState || store.currentState.inventory.length===0" class="panel-empty">背包空空如也</div>
            <div v-for="(item,idx) in (store.currentState?.inventory??[])" :key="idx" class="panel-row">
              <span class="panel-name">{{ item.name }}</span>
              <button v-if="isDiscardable(item)" @click="discardItem(idx)" class="btn-del">丢弃</button>
            </div>
            <button class="btn-close" @click="showBP=false">关闭</button>
          </div>
          <div v-if="showLoad" class="panel">
            <div v-if="saveList.length===0" class="panel-empty">暂无存档</div>
            <div v-for="s in saveList" :key="s.id" class="panel-row">
              <span class="panel-name">{{ s.save_name||s.id }}</span>
              <span class="panel-meta">节点{{ s.current_node_id }}·循环{{ s.cycle_count }}</span>
              <button @click="doLoad(s.id)">读取</button><button @click="doDelete(s.id)" class="btn-del">删除</button>
            </div>
            <button class="btn-close" @click="showLoad=false">关闭</button>
          </div>
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

    <!-- Scene transition overlay -->
    <div v-if="trans.active" class="trans-overlay" :class="'trans-' + trans.type">
      <template v-if="trans.type==='title'">
        <div class="trans-title-text">{{ trans.nodeName }}</div>
        <div class="trans-title-time">{{ trans.nodeTime }}</div>
      </template>
    </div>

    <CycleMap v-if="showMap && store.currentState"
      :current-id="store.currentNode?.id??'A'" :visited-ids="store.currentState.visited_nodes"
      :has-warp-access="store.currentState.flags?.taoist_chant===true" />

    <div v-if="notifyText" class="scene-notify">{{ notifyText }}</div>
    <div v-if="store.cycleEvent" class="cycle-toast"><span class="cycle-icon">⟳</span> 第 {{ store.cycleEvent.cycle_count }} 次循环完成</div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed, watch, nextTick } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import StatusBar from '@/components/player/StatusBar.vue'
import CycleMap from '@/components/player/CycleMap.vue'
import axios from 'axios'

const store = useGameStore(); const mainRef = ref<HTMLElement|null>(null); onMounted(()=>store.init())

// ── Dialogue system ──
const dialogLines = ref<string[]>([])
const dialogIdx = ref(0)
const visibleLines = computed(() => dialogLines.value.slice(0, dialogIdx.value + 1))
const hasMoreLines = computed(() => store.currentNode?.speaker && dialogIdx.value < dialogLines.value.length - 1)
const canShowChoices = computed(() => {
  if (!store.currentNode) return false
  const isNarration = !store.currentNode.speaker
  const narrationDone = isNarration && !isTyping.value
  const dialogueDone = !isNarration && !hasMoreLines.value && !isTyping.value
  return (narrationDone || dialogueDone) && store.choices.length > 0
})

function parseDialogue() {
  const content = store.currentNode?.content ?? ''
  const speaker = store.currentNode?.speaker
  if (!speaker) { dialogLines.value = []; dialogIdx.value = 0; return }
  // Split by double newlines into individual spoken lines
  dialogLines.value = content.split(/\n\n+/).filter(l => l.trim())
  dialogIdx.value = 0
}

function nextLine() {
  if (dialogIdx.value < dialogLines.value.length - 1) {
    dialogIdx.value++
    scrollDown()
  }
}

// ── Typewriter (narration only) ──
const displayedText = ref(''); const isTyping = ref(false)
let tt: ReturnType<typeof setInterval>|null = null
const renderedContent = computed(() => store.currentNode && !store.currentNode.speaker ? md2html(store.currentNode.content) : '')

function startTypewriter() {
  if (tt) clearInterval(tt)
  const raw = store.currentNode?.content ?? ''
  if (!raw || store.currentNode?.speaker) { isTyping.value = false; return }
  isTyping.value = true; displayedText.value = ''; let i = 0
  tt = setInterval(() => { i++; if (i >= raw.length) { displayedText.value = md2html(raw); isTyping.value = false; if(tt) clearInterval(tt); return } displayedText.value = md2html(raw.slice(0,i)) }, 25)
}

// ── Transitions ──
const transitions = ref<Array<{label:string;text:string}>>([])
const chosenIds = ref<Set<string>>(new Set())
let prevNid = ''

watch(() => store.currentNode?.id, (nid) => {
  if (nid && nid !== prevNid) { prevNid = nid; transitions.value = []; chosenIds.value = new Set(); parseDialogue(); startTypewriter() }
})

async function handleChoice(c: any) {
  if (isTyping.value || hasMoreLines.value || chosenIds.value.has(c.id) || store.loading) return
  const prevN = store.currentNode?.id; const label = c.text
  chosenIds.value = new Set([...chosenIds.value, c.id])
  await store.choose(c.id)
  const newN = store.currentNode?.id
  if (newN && newN !== prevN) {
    triggerSceneTrans(store.currentNode)
    setTimeout(() => { prevNid = newN; transitions.value = []; chosenIds.value = new Set(); parseDialogue(); startTypewriter(); scrollDown() }, 500)
    return
  }
  if (store.transitionText) { transitions.value.push({label, text: md2html(store.transitionText)}); if(store.currentFrame) store.currentFrame = {...store.currentFrame, transition_text:undefined} }
  scrollDown()
}

function onGlobalClick() {
  if (isTyping.value) { if(tt)clearInterval(tt); displayedText.value = renderedContent.value; isTyping.value = false; return }
  if (hasMoreLines.value) { nextLine(); return }
}

// ── Scene transitions ──
const trans = ref<{active:boolean;type:string;nodeName?:string;nodeTime?:string}>({active:false,type:'ink'})
function getTransType(n:any):string { if(n?.id==='E'||n?.id==='K') return 'rift'; if(n?.id==='A') return 'title'; return 'ink' }
function triggerSceneTrans(n:any) {
  trans.value = {active:true, type:getTransType(n), nodeName:n?.name, nodeTime:n?.time_label}
  setTimeout(() => { trans.value.active = false }, 1200)
}

function md2html(t:string):string {
  t = t.replace(/^\[.*?\]\s*$/gm,'').replace(/\[(courage|sanity|insight|sanity_max)\s*[+-]?\d+\]/gi,'').replace(/\[flag:\s*\w+.*?\]/gi,'').replace(/\n{3,}/g,'\n\n')
  t = t.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>').replace(/---/g,'<span class="scene-break">· · ·</span>').replace(/\n\n/g,'</p><p>')
  return `<p>${t}</p>`
}

function scrollDown() { nextTick(()=>{ if(mainRef.value) mainRef.value.scrollTop = mainRef.value.scrollHeight }) }

// ── Extras ──
const showBP = ref(false); const showMap = ref(false)
const DISCARD = new Set(['item_qing_coin','item_denim_rag','item_warning_note','item_old_newspaper'])
function isDiscardable(it:any) { return DISCARD.has(it.id) }
function discardItem(i:number) { store.currentState?.inventory.splice(i,1) }
const showLoad = ref(false); const saveList = ref<any[]>([])
async function refreshSaves() { try{ const r = await axios.get('/api/saves'); saveList.value = r.data.saves??[] } catch{} }
async function doSave() { if(!store.currentState) return; const n = prompt('存档名称:'); if(!n) return; try{ await axios.post('/api/saves?name='+encodeURIComponent(n),store.currentState); alert('存档成功') } catch{ alert('存档失败') } }
async function doLoad(sid:string) { try{ const r = await axios.get('/api/saves/load/'+sid); await (await import('@/api/game')).startGame(); showLoad.value = false } catch{ alert('读档失败') } }
async function doDelete(sid:string) { if(!confirm('确认删除?')) return; try{ await axios.delete('/api/saves/'+sid); refreshSaves() } catch{} }
watch(showLoad, v => { if(v) refreshSaves() })
const bgTintStyle = computed(() => { const p = store.currentNode?.color_palette; if(!p) return{}; const c = p.split('+')[0]?.trim(); return c?{background:`radial-gradient(ellipse at center, transparent 40%, ${c}10 100%)`}:{} })
let amb:HTMLAudioElement|null = null
watch(()=>store.currentNode?.ambient, s=>{ if(amb){amb.pause();amb=null} if(s){amb=new Audio(s);amb.loop=true;amb.volume=0.3;amb.play().catch(()=>{})} })
const notifyText = ref('')
watch(()=>store.currentFrame?.scene_effects, fx=>{ if(!fx?.length) return; for(const e of fx){ if(e.type==='notify'){ notifyText.value=e.target||''; setTimeout(()=>notifyText.value='',2500) } } })
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.game-play { width:100vw; height:100vh; overflow:hidden; display:flex; flex-direction:column; position:relative; background:$bg-void; }
.bg-layer { position:fixed; inset:0; z-index:0; pointer-events:none; }
.bg-vignette { position:absolute; inset:0; background:radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.55) 100%); animation:breathe 8s infinite; }
@keyframes breathe { 0%,100%{opacity:0.55} 50%{opacity:0.85} }

.game-main { position:relative; z-index:1; flex:1; overflow-y:auto; padding-bottom:5rem; }
.content-wrapper { max-width:$narrative-max-width; margin:0 auto; padding:1rem 1.5rem; }

.loading { display:flex; justify-content:center; align-items:center; height:60vh; }
.dot { font-size:3rem; color:$accent-gold; animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:0.15} 50%{opacity:1} }
.error { text-align:center; padding:4rem; color:$accent-red; button { margin-top:1rem; padding:.5rem 2rem; background:transparent; border:1px solid rgba($accent-gold,.3); color:$accent-gold; cursor:pointer; } }

.time-label { text-align:center; color:$text-dim; font-family:$font-ui; font-size:.85rem; padding:.8rem 0 .5rem; letter-spacing:.1em; }

// ── Narration ──
.narrative-box { margin:.5rem 0; }
.narrative-text { font-size:1rem; line-height:1.85;
  :deep(p) { margin-bottom:.8rem; text-indent:2em; &:first-child{text-indent:0} }
  :deep(strong) { color:$accent-gold; }
  :deep(em) { color:$text-secondary; }
  :deep(.scene-break) { display:block; text-align:center; color:$accent-red; margin:1.5rem 0; font-family:$font-display; letter-spacing:.8em; }
}

// ── Dialogue (chat bubbles) ──
.dialogue-area { padding:.5rem 0; }
.chat-row { display:flex; align-items:flex-start; gap:.6rem; margin-bottom:1rem; animation: bubbleIn .35s ease-out both;
  &.me { flex-direction:row-reverse;
    .chat-bubble { background:rgba($accent-gold,.06); border-color:rgba($accent-gold,.15); }
    .chat-name { text-align:right; }
  }
}
@keyframes bubbleIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
.chat-avatar { width:34px; height:34px; border-radius:50%; background:rgba($accent-gold,.08); border:1px solid rgba($accent-gold,.2); display:flex; align-items:center; justify-content:center; color:$accent-gold; font-family:$font-display; font-size:.95rem; flex-shrink:0; }
.chat-bubble { flex:1; background:rgba($bg-void,.6); border:1px solid rgba($accent-gold,.1); border-radius:6px; padding:.6rem .9rem; max-width:85%; }
.chat-name { font-family:$font-ui; font-size:.72rem; color:$accent-gold; margin-bottom:.2rem; }
.chat-text { font-size:.95rem; line-height:1.7; color:$text-primary;
  :deep(p) { margin-bottom:0; }
  :deep(strong) { color:$accent-gold; }
  :deep(em) { color:$text-secondary; }
}

// ── Transitions inline ──
.transition-inline { margin:.8rem 0; padding:.8rem 1rem; background:rgba($accent-gold,.03); border-left:2px solid rgba($accent-gold,.35); animation:fadeIn .3s; }
@keyframes fadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
.transition-text { color:$text-secondary; font-size:.93rem; line-height:1.8;
  :deep(p) { margin-bottom:.5rem; text-indent:2em; &:first-child{text-indent:0} }
  :deep(strong) { color:$accent-gold; }
}

.continue-hint { text-align:center; padding:.8rem 0; cursor:pointer; }
.arrow { color:$accent-gold; font-size:1.2rem; animation:blink 1.5s infinite; }
@keyframes blink { 0%,100%{opacity:.3} 50%{opacity:1} }

// ── Choices ──
.choice-area { margin:1rem 0; }
.choice-btn { display:block; width:100%; padding:.85rem 1.2rem; margin-bottom:.5rem;
  background:linear-gradient(135deg, rgba(26,20,16,.95), rgba(30,24,18,.9));
  border:1px solid rgba($accent-gold,.18); border-left:3px solid rgba($accent-gold,.35);
  color:$text-primary; font-family:$font-body; font-size:.95rem; text-align:left; cursor:pointer; transition:.2s; position:relative;
  &:hover:not(.chosen) { border-color:rgba($accent-gold,.5); border-left-color:$accent-gold; transform:translateX(2px); }
  &.chosen { opacity:.35; cursor:default; border-left-color:rgba($text-dim,.3); .choice-text{text-decoration:line-through} }
  &.warp { border-color:rgba($accent-ghost,.35); border-left-color:rgba($accent-ghost,.6); border-style:dashed; }
  &.scene-transition { border-color:rgba($accent-red,.25); border-left-color:rgba($accent-red,.5); background:linear-gradient(135deg, rgba(20,14,14,.95), rgba(26,16,16,.9));
    &:hover:not(.chosen) { border-color:rgba($accent-red,.5); border-left-color:$accent-red; }
  }
}
.chosen-mark { position:absolute; right:.8rem; top:50%; transform:translateY(-50%); color:$accent-gold; font-size:.8rem; }
.warp-tag { position:absolute; right:.8rem; top:50%; transform:translateY(-50%); font-family:$font-ui; font-size:.65rem; color:rgba($accent-ghost,.6); border:1px solid rgba($accent-ghost,.25); padding:.1rem .4rem; border-radius:2px; }
.transition-icon { position:absolute; right:.8rem; top:50%; transform:translateY(-50%); color:rgba($accent-red,.6); font-size:1rem; }

// ── Panels ──
.panel { max-width:400px; margin:0 auto 1rem; padding:1rem; background:rgba($bg-void,.95); border:1px solid rgba($accent-gold,.15); border-radius:6px; }
.panel-empty { color:$text-dim; text-align:center; padding:1rem; font-size:.85rem; }
.panel-row { display:flex; align-items:center; gap:.5rem; padding:.4rem 0; border-bottom:1px solid rgba($accent-gold,.06);
  button { padding:.2rem .6rem; background:transparent; border:1px solid rgba($accent-gold,.2); color:$text-secondary; font-size:.75rem; cursor:pointer; border-radius:2px;
    &:hover{ border-color:$accent-gold; color:$accent-gold; }
    &.btn-del { border-color:rgba($accent-red,.2); color:rgba($accent-red,.6); &:hover{ border-color:$accent-red; color:$accent-red; } }
  }
}
.panel-name { flex:1; color:$text-primary; font-size:.85rem; }
.panel-meta { color:$text-dim; font-size:.7rem; }
.btn-close { display:block; margin:.5rem auto 0; padding:.3rem 1.5rem; background:transparent; border:1px solid rgba($accent-gold,.15); color:$text-dim; font-size:.8rem; cursor:pointer; }

// ── Start ──
.start-screen { display:flex; align-items:center; justify-content:center; height:100%; }
.start-content { text-align:center; }
h1 { font-family:$font-display; font-size:3rem; font-weight:700; color:$accent-gold; letter-spacing:.15em; margin-bottom:.5rem; }
.divider { color:$accent-red; margin:0 .3rem; }
.start-screen p { color:$text-dim; font-size:.95rem; margin-bottom:2.5rem; }
.start-btn { padding:.8rem 3.5rem; font-size:1.1rem; background:transparent; color:$accent-red; border:1px solid rgba($accent-red,.4); font-family:$font-display; letter-spacing:.1em; cursor:pointer; transition:.3s;
  &:hover { background:rgba($accent-red,.1); border-color:$accent-red; }
}

// ── Scene transitions ──
.trans-overlay { position:fixed; inset:0; z-index:500; pointer-events:none; }
.trans-ink { background:radial-gradient(circle at 50% 50%, #2a2018 0%, #1a1410 60%, #0d0804 100%); animation: inkIn .5s ease-in forwards, inkOut .6s ease-out .5s forwards; }
@keyframes inkIn { 0%{clip-path:circle(0% at 50% 50%)} 100%{clip-path:circle(85% at 50% 50%)} }
@keyframes inkOut { 0%{clip-path:circle(85% at 50% 50%)} 100%{clip-path:circle(0% at 50% 50%)} }

.trans-rift { background:radial-gradient(ellipse at 50% 50%, #1a0808 0%, #0d0000 100%); animation: riftIn .45s ease-in forwards, riftOut .7s ease-out .45s forwards; }
@keyframes riftIn { 0%{clip-path:inset(0 50% 0 50%);opacity:0} 20%{opacity:1} 100%{clip-path:inset(0 0 0 0);opacity:1} }
@keyframes riftOut { 0%{clip-path:inset(0 0 0 0);opacity:1} 100%{clip-path:inset(0 50% 0 50%);opacity:0} }

.trans-title { background:radial-gradient(ellipse at center, #1a1410 0%, #0d0804 100%); display:flex; flex-direction:column; align-items:center; justify-content:center; animation: titleIn .4s ease-in forwards, titleOut .5s ease-out .9s forwards; }
@keyframes titleIn { 0%{opacity:0} 100%{opacity:1} }
@keyframes titleOut { 0%{opacity:1} 100%{opacity:0} }
.trans-title-text { font-family:$font-display; font-size:2.2rem; color:$accent-gold; letter-spacing:.2em; text-align:center; animation: titleFade .5s ease-out .2s both; }
.trans-title-time { font-family:$font-ui; font-size:.85rem; color:$text-dim; letter-spacing:.15em; margin-top:.6rem; animation: titleFade .5s ease-out .4s both; }
@keyframes titleFade { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }

.scene-notify { position:fixed; top:15%; left:50%; transform:translateX(-50%); z-index:310; color:$accent-gold; font-family:$font-display; font-size:1.2rem; pointer-events:none; animation:notifyAnim 2.5s ease-out; }
@keyframes notifyAnim { 0%{opacity:0;transform:translateX(-50%) translateY(-10px)} 15%{opacity:1;transform:translateX(-50%) translateY(0)} 70%{opacity:1} 100%{opacity:0} }
.cycle-toast { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:100; color:$accent-gold; font-family:$font-display; font-size:1.1rem; pointer-events:none; animation:cycleFade 3s infinite; }
.cycle-icon { display:inline-block; animation:spin 8s linear infinite; }
@keyframes cycleFade { 0%,100%{opacity:0} 50%{opacity:1} }
@keyframes spin { from{transform:rotate(0)} to{transform:rotate(360deg)} }
</style>
