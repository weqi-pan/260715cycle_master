<!-- GamePlay.vue -->
<template>
  <div class="game-play" :class="screenEffectClass" @click="onGlobalClick">
    <div class="bg-layer" :style="bgTintStyle"><div class="bg-vignette" /></div>

    <StatusBar v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count" :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes" :inventory="store.currentState.inventory"
      :node-name="store.currentNode?.name"
      @toggle-map="showMap = !showMap" @toggle-backpack="showBP = !showBP" @save="doSave" @load="showLoad = !showLoad" />

    <div class="game-main" ref="mainRef">
      <div v-if="store.loading && !store.currentNode" class="loading"><span class="dot">·</span></div>
      <div v-else-if="store.error" class="error"><p>{{ store.error }}</p><button @click.stop="startFromUI">重试</button></div>

      <template v-else-if="store.currentNode">
        <div class="content-wrapper">
          <div v-if="store.currentNode.time_label" class="time-label">◈ {{ store.currentNode.time_label }}</div>

          <!-- 所有内容块使用同一条有序时间线，类型切换不会清空历史 -->
          <div
            v-if="visibleBlocks.length"
            class="story-timeline"
            data-testid="story-timeline"
          >
            <template v-for="block in visibleBlocks" :key="block.id">
              <div
                v-if="block.type === 'dialogue'"
                class="chat-row"
                :class="{ me: isPlayerSpeaker(block.speaker_id || 'unknown') }"
                data-testid="story-block"
                data-block-type="dialogue"
                :data-speaker-id="block.speaker_id || 'unknown'"
              >
                <div class="chat-avatar"><span>{{ speakerInitial(block.speaker_id || 'unknown') }}</span></div>
                <div class="chat-bubble">
                  <div class="chat-name">{{ speakerName(block.speaker_id || 'unknown') }}</div>
                  <div class="chat-text" v-html="md2html(block.displayed_text)" />
                </div>
              </div>

              <div
                v-else-if="block.type === 'narration'"
                class="narrative-box"
                data-testid="story-block"
                data-block-type="narration"
              >
                <div class="narrative-text" v-html="md2html(block.displayed_text)" />
              </div>

              <div
                v-else
                class="system-block"
                data-testid="story-block"
                data-block-type="system"
              >
                {{ block.displayed_text }}
              </div>
            </template>
          </div>

          <div v-if="waitingForAdvance && playbackPhase !== 'choices'" class="continue-hint">
            <span class="arrow">▼</span>
          </div>

          <!-- Choices -->
          <div v-if="showChoices" class="choice-area">
            <button v-for="(c, index) in store.choices" :key="c.id"
              class="choice-btn"
              :class="{ warp: c.source === 'special_warp', 'scene-trans': c.next_node_id !== store.currentNode?.id }"
              :disabled="store.loading || chosenIds.has(c.id)"
              @click.stop="handleChoice(c)"
            >
              <span class="choice-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span class="choice-copy">
                <span class="choice-text">{{ c.text }}</span>
              </span>
              <span v-if="c.source === 'special_warp'" class="warp-tag">跃迁</span>
              <span v-if="c.next_node_id !== store.currentNode?.id" class="trans-arrow">→</span>
            </button>
          </div>

          <!-- Panels -->
          <div v-if="showBP" class="panel" @click.stop><div v-if="!store.currentState||store.currentState.inventory.length===0" class="p-empty">暂无道具</div><div v-for="it in (store.currentState?.inventory??[])" :key="it.id" class="p-row"><span class="p-name">{{ it.name }}<template v-if="it.count && it.count > 1"> ×{{ it.count }}</template></span><button v-if="canDiscard(it)" :disabled="store.loading" @click="discardItem(it.id)" class="p-del">丢弃</button></div><button class="p-close" @click="showBP=false">关闭</button></div>
          <div v-if="showLoad" class="panel" @click.stop><div v-if="saveList.length===0" class="p-empty">暂无存档</div><div v-for="s in saveList" :key="s.id" class="p-row"><span class="p-name">{{ s.save_name||s.id }}</span><span class="p-meta">{{ s.current_node_id }}·第{{ s.cycle_count }}轮</span><button @click="doLoad(s.id)">加载</button><button @click="doDelete(s.id)" class="p-del">删除</button></div><button class="p-close" @click="showLoad=false">关闭</button></div>
        </div>
      </template>

      <div v-else class="start-screen"><div class="start-content"><h1>荔湾<span class="divider">·</span>四日轮回</h1><p>荔湾广场之下，时间如莫比乌斯环般扭曲</p><button class="start-btn" @click.stop="startFromUI">踏入循环</button></div></div>
    </div>

    <div v-if="trans.active" class="trans-overlay" :class="'trans-'+trans.type">
      <template v-if="trans.type==='title'"><div class="trans-title-text">{{ trans.nodeName }}</div><div class="trans-title-time">{{ trans.nodeTime }}</div></template>
    </div>

    <CycleMap v-if="showMap&&store.currentState" :current-id="store.currentNode?.id??'A'" :visited-ids="store.currentState.visited_nodes" :has-warp-access="store.currentState.flags?.taoist_chant===true" />
    <div v-if="notifyText" class="scene-notify">{{ notifyText }}</div>
    <div v-if="cycleToast" class="cycle-toast"><span class="cycle-icon">⟳</span> 第 {{ cycleToast }} 轮</div>
  </div>
</template>

<script setup lang="ts">
import { onUnmounted, ref, computed, watch, nextTick } from 'vue'
import type { ChoiceResult, ContentBlock, Frame, GameState, ItemBrief } from '@/types'
import { useGameStore } from '@/stores/gameStore'
import {
  appendVisibleBlock,
  updateVisibleBlockText,
  type VisibleContentBlock,
} from '@/player/playbackTimeline'
import StatusBar from '@/components/player/StatusBar.vue'
import CycleMap from '@/components/player/CycleMap.vue'
import axios from 'axios'

const store = useGameStore()
const mainRef = ref<HTMLElement|null>(null)
type PlaybackPhase = 'idle' | 'entry' | 'result' | 'choices'
type SequenceKind = 'entry' | 'result'

const playbackPhase = ref<PlaybackPhase>('idle')
const visibleBlocks = ref<VisibleContentBlock[]>([])
const activeBlocks = ref<ContentBlock[]>([])
const activeBlockIndex = ref(-1)
let sequenceKind:SequenceKind = 'entry'
const isTyping = ref(false)
const waitingForAdvance = ref(false)
const chosenIds = ref<Set<string>>(new Set())
let pendingSceneChange = false
let typeTimer: ReturnType<typeof setInterval>|null = null
let fullTypingText = ''
let activeSetter: ((value: string) => void)|null = null

const showChoices = computed(() => playbackPhase.value === 'choices' && store.choices.length > 0)

function stopTypeTimer() {
  if (typeTimer) clearInterval(typeTimer)
  typeTimer = null
}

function typeText(raw: string, setter: (value: string) => void) {
  stopTypeTimer()
  const chars = Array.from(raw)
  fullTypingText = raw
  activeSetter = setter
  waitingForAdvance.value = false
  setter('')
  if (!chars.length) {
    isTyping.value = false
    waitingForAdvance.value = true
    return
  }
  isTyping.value = true
  let index = 0
  typeTimer = setInterval(() => {
    index = Math.min(index + 1, chars.length)
    setter(chars.slice(0, index).join(''))
    if (index >= chars.length) {
      stopTypeTimer()
      isTyping.value = false
      waitingForAdvance.value = true
    }
  }, 22)
}

function skipTyping() {
  if (!isTyping.value || !activeSetter) return
  stopTypeTimer()
  activeSetter(fullTypingText)
  isTyping.value = false
  waitingForAdvance.value = true
}

function beginEntry(frame: Frame) {
  const legacyBlocks:ContentBlock[] = [
    ...(frame.node.content ? [{id:`${frame.node.id}.legacy.narration`,type:'narration' as const,text:frame.node.content}] : []),
    ...(frame.node.dialogue_lines ?? []).map((line,index) => ({
      id:`${frame.node.id}.legacy.dialogue.${index}`,
      type:'dialogue' as const,
      speaker_id:line.speaker || 'unknown',
      text:line.text,
    })),
  ]
  beginSequence(
    frame.node.entry_blocks?.length ? frame.node.entry_blocks : legacyBlocks,
    'entry',
  )
}

function beginSequence(blocks:ContentBlock[], kind:SequenceKind) {
  stopTypeTimer()
  activeSetter = null
  isTyping.value = false
  sequenceKind=kind
  activeBlocks.value=blocks
  activeBlockIndex.value=-1
  visibleBlocks.value=[]
  if(blocks.length) playBlock(0)
  else finishSequence()
  scrollDown()
}

function playBlock(index:number){
  const block=activeBlocks.value[index]
  if(!block){finishSequence();return}
  activeBlockIndex.value=index
  playbackPhase.value=sequenceKind
  visibleBlocks.value=appendVisibleBlock(visibleBlocks.value,block)
  typeText(block.text,value=>{
    visibleBlocks.value=updateVisibleBlockText(visibleBlocks.value,block.id,value)
  })
  scrollDown()
}

function beginResult(frame:Frame) {
  const fallback:ContentBlock[] = frame.transition_text ? [{
    id:'legacy.result',type:'narration',text:frame.transition_text,
  }] : []
  beginSequence(frame.result_blocks?.length ? frame.result_blocks : fallback,'result')
}

function finishSequence(){
  waitingForAdvance.value=false
  if(sequenceKind==='result'&&pendingSceneChange&&store.currentFrame){
    pendingSceneChange=false
    triggerSceneTrans(store.currentNode)
    setTimeout(()=>store.currentFrame&&beginEntry(store.currentFrame),520)
  }else{
    revealChoices()
  }
}

function revealChoices() {
  playbackPhase.value = 'choices'
  waitingForAdvance.value = false
  scrollDown()
}

function advancePlayback() {
  if (!waitingForAdvance.value) return
  waitingForAdvance.value = false
  const nextIndex=activeBlockIndex.value+1
  if(nextIndex<activeBlocks.value.length) playBlock(nextIndex)
  else finishSequence()
}

async function startFromUI() {
  await store.init()
  chosenIds.value = new Set()
  if (store.currentFrame) beginEntry(store.currentFrame)
}

async function handleChoice(c: ChoiceResult) {
  if (playbackPhase.value !== 'choices' || store.loading || !c.available || chosenIds.value.has(c.id)) return
  const previousNodeId = store.currentNode?.id
  chosenIds.value = new Set([...chosenIds.value, c.id])
  await store.choose(c.id)
  if (!store.currentFrame || store.error) {
    chosenIds.value = new Set([...chosenIds.value].filter(id => id !== c.id))
    return
  }
  chosenIds.value = new Set([...chosenIds.value].filter(id => id !== c.id))
  const nextNodeId = store.currentNode?.id
  pendingSceneChange = Boolean(nextNodeId && nextNodeId !== previousNodeId)
  consumeFrameEffects(store.currentFrame)
  if (store.currentFrame.result_blocks?.length || store.transitionText) beginResult(store.currentFrame)
  else if (pendingSceneChange) {
    pendingSceneChange = false
    triggerSceneTrans(store.currentNode)
    setTimeout(() => store.currentFrame && beginEntry(store.currentFrame), 520)
  } else revealChoices()
}

// ── Transitions ──
const trans = ref<{active:boolean;type:string;nodeName?:string;nodeTime?:string}>({active:false,type:'ink'})
function getTransType(n:any):string { if(n?.id==='E'||n?.id==='K') return 'rift'; if(n?.id==='A') return 'title'; return 'ink' }
function triggerSceneTrans(n:any) { trans.value = {active:true, type:getTransType(n), nodeName:n?.name, nodeTime:n?.time_label}; setTimeout(()=>{trans.value.active=false},1200) }

// ── Click handler ──
function onGlobalClick(event: MouseEvent) {
  const target = event.target as HTMLElement|null
  if (target?.closest('button, .panel, .status-bar, .cycle-map')) return
  if (isTyping.value) { skipTyping(); return }
  advancePlayback()
}

// ── Helpers ──
function md2html(t:string):string {
  t = t.replace(/^\[.*?\]\s*$/gm,'').replace(/\[(courage|sanity|insight|sanity_max)\s*[+-]?\d+\]/gi,'').replace(/\[flag:\s*\w+.*?\]/gi,'').replace(/\n{3,}/g,'\n\n')
  t = t.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  t = t.replace(/\*\*(.+?)\*\*/g,'<strong>$1</strong>').replace(/\*(.+?)\*/g,'<em>$1</em>').replace(/---/g,'<span class="scene-break">· · ·</span>').replace(/\n\n/g,'</p><p>')
  return `<p>${t}</p>`
}
function isPlayerSpeaker(speaker:string){return ['player','protagonist','主角','我'].includes(speaker.toLowerCase())}
function speakerName(speaker:string){return isPlayerSpeaker(speaker)?'我':store.currentFrame?.speaker_names[speaker]??speaker.replace(/^npc_/,'').replace(/_/g,' ')}
function speakerInitial(speaker:string){return speakerName(speaker).slice(0,1)||'·'}
function scrollDown() { nextTick(()=>{ if(mainRef.value) mainRef.value.scrollTop = mainRef.value.scrollHeight }) }

// ── Extras ──
const showBP = ref(false); const showMap = ref(false); const showLoad = ref(false); const saveList = ref<any[]>([])
function canDiscard(it:ItemBrief){return it.discardable === true}
async function discardItem(itemId:string){try{await store.discard(itemId)}catch{alert(store.error||'无法丢弃道具')}}
async function refreshSaves(){try{const r=await axios.get('/api/saves');saveList.value=r.data.saves??[]}catch{}}
async function doSave(){if(!store.currentState)return;const n=prompt('存档名称：');if(!n)return;try{await axios.post('/api/saves?name='+encodeURIComponent(n),store.currentState);alert('存档完成')}catch{alert('存档失败')}}
async function doLoad(sid:string){try{const r=await axios.get<GameState>('/api/saves/load/'+sid);await store.resume(r.data);chosenIds.value=new Set();if(store.currentFrame)beginEntry(store.currentFrame);showLoad.value=false}catch{alert(store.error||'加载失败')}}
async function doDelete(sid:string){if(!confirm('确定删除这个存档？'))return;try{await axios.delete('/api/saves/'+sid);refreshSaves()}catch{alert('删除失败')}}
watch(showLoad,v=>{if(v)refreshSaves()})
const bgTintStyle = computed(()=>{
  const background = store.currentNode?.background
  return background ? {
    backgroundImage:`linear-gradient(rgba(10,8,7,.72),rgba(10,8,7,.88)),url(${JSON.stringify(background).slice(1,-1)})`,
    backgroundSize:'cover',
    backgroundPosition:'center',
  } : {}
})
let amb:HTMLAudioElement|null=null
watch(()=>store.currentNode?.ambient,s=>{if(amb){amb.pause();amb=null}if(s){amb=new Audio(s);amb.loop=true;amb.volume=0.3;amb.play().catch(()=>{})}})
const notifyText=ref('')
const cycleToast=ref<number|null>(null)
const screenEffectClass=ref('')
let notifyTimer:ReturnType<typeof setTimeout>|null=null
let cycleTimer:ReturnType<typeof setTimeout>|null=null
let effectTimer:ReturnType<typeof setTimeout>|null=null
function consumeFrameEffects(frame:Frame){
  for(const effect of frame.scene_effects??[]){
    if(effect.type==='notify'){
      notifyText.value=effect.target||String(effect.value??'')
      if(notifyTimer)clearTimeout(notifyTimer)
      notifyTimer=setTimeout(()=>notifyText.value='',2500)
    }
    if(effect.type==='shake'||effect.type==='flash'){
      screenEffectClass.value=`effect-${effect.type}`
      if(effectTimer)clearTimeout(effectTimer)
      effectTimer=setTimeout(()=>screenEffectClass.value='',650)
    }
  }
  if(frame.cycle_event){
    cycleToast.value=frame.cycle_event.cycle_count
    if(cycleTimer)clearTimeout(cycleTimer)
    cycleTimer=setTimeout(()=>cycleToast.value=null,3000)
  }
}
onUnmounted(()=>{
  stopTypeTimer()
  if(notifyTimer)clearTimeout(notifyTimer)
  if(cycleTimer)clearTimeout(cycleTimer)
  if(effectTimer)clearTimeout(effectTimer)
  if(amb)amb.pause()
})
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.game-play { width:100vw; height:100vh; overflow:hidden; display:flex; flex-direction:column; position:relative; background:$bg-void; }
.game-play.effect-shake { animation:screenShake .45s ease-out; }
.game-play.effect-flash::after { content:''; position:fixed; inset:0; z-index:700; pointer-events:none; background:rgba(238,222,180,.75); animation:screenFlash .6s ease-out forwards; }
@keyframes screenShake { 0%,100%{transform:translate(0)} 20%{transform:translate(-7px,3px)} 40%{transform:translate(6px,-2px)} 60%{transform:translate(-4px,-1px)} 80%{transform:translate(3px,2px)} }
@keyframes screenFlash { from{opacity:1} to{opacity:0} }
.bg-layer { position:fixed; inset:0; z-index:0; pointer-events:none; }
.bg-vignette { position:absolute; inset:0; background:radial-gradient(ellipse at center, transparent 50%, rgba(0,0,0,0.55) 100%); animation:breathe 8s infinite; }
@keyframes breathe { 0%,100%{opacity:0.55} 50%{opacity:0.85} }

.game-main { position:relative; z-index:1; flex:1; overflow-y:auto; scroll-behavior:smooth; padding-bottom:5rem; }
.content-wrapper { position:relative; width:min(980px,100%); min-height:calc(100vh - 90px); margin:0 auto; padding:1.25rem 3rem 3rem; background:linear-gradient(90deg,transparent,rgba(18,15,12,.28) 8%,rgba(18,15,12,.36) 92%,transparent); }
.content-wrapper::before { content:''; position:absolute; top:0; bottom:0; left:14px; width:1px; background:linear-gradient(transparent,rgba($accent-red,.28) 12%,rgba($accent-red,.14) 88%,transparent); pointer-events:none; }

.loading { display:flex; justify-content:center; align-items:center; height:60vh; }
.dot { font-size:3rem; color:$accent-gold; animation:pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:0.15} 50%{opacity:1} }
.error { text-align:center; padding:4rem; color:$accent-red; button{margin-top:1rem;padding:.5rem 2rem;background:transparent;border:1px solid rgba($accent-gold,.3);color:$accent-gold;cursor:pointer} }

.time-label { display:flex; align-items:center; justify-content:center; gap:.65rem; text-align:center; color:$text-dim; font-family:$font-ui; font-size:.78rem; padding:.8rem 0 1rem; letter-spacing:.16em; }
.time-label::before,.time-label::after{content:'';width:34px;height:1px;background:linear-gradient(90deg,transparent,rgba($accent-gold,.24))}
.time-label::after{transform:scaleX(-1)}

// Narration
.story-timeline { display:flex; flex-direction:column; gap:.15rem; }
.narrative-box { position:relative; margin:.5rem 0 1.1rem; padding:1.15rem 1.25rem 1.15rem 1.5rem; background:linear-gradient(135deg,rgba(17,15,12,.78),rgba(12,11,10,.42)); border:1px solid rgba($accent-gold,.08); border-left:2px solid rgba($accent-red,.42); box-shadow:0 18px 48px rgba(0,0,0,.18); }
.narrative-box::after{content:'叙';position:absolute;right:.7rem;top:.55rem;color:rgba($accent-red,.15);font-family:$font-display;font-size:1.4rem}
.narrative-text { font-size:1rem; line-height:1.95; text-shadow:0 1px 12px rgba(0,0,0,.45);
  :deep(p) { margin-bottom:.8rem; text-indent:2em; &:first-child{text-indent:0} }
  :deep(strong) { color:$accent-gold; }
  :deep(em) { color:$text-secondary; }
  :deep(.scene-break) { display:block; text-align:center; color:$accent-red; margin:1.5rem 0; font-family:$font-display; letter-spacing:.8em; }
}

// Dialogue bubbles
.chat-row { display:flex; align-items:flex-start; gap:.75rem; margin-bottom:1rem; animation:bubbleIn .35s ease-out both;
  &.me { flex-direction:row-reverse;
    .chat-bubble { background:rgba($accent-gold,.05); border-color:rgba($accent-gold,.12); }
    .chat-name { text-align:right; }
  }
}
@keyframes bubbleIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
.chat-avatar { width:38px; height:38px; border-radius:2px; transform:rotate(45deg); background:rgba($accent-red,.09); border:1px solid rgba($accent-red,.34); display:flex; align-items:center; justify-content:center; color:$accent-gold; font-family:$font-display; font-size:.88rem; flex-shrink:0; box-shadow:0 5px 18px rgba(0,0,0,.3); }
.chat-avatar span{transform:rotate(-45deg)}
.chat-bubble { flex:1; background:linear-gradient(135deg,rgba(13,14,13,.86),rgba(21,18,14,.62)); border:1px solid rgba($accent-gold,.12); border-radius:2px 8px 8px 8px; padding:.75rem 1rem; max-width:82%; box-shadow:0 10px 24px rgba(0,0,0,.18); }
.chat-name { font-family:$font-ui; font-size:.72rem; color:$accent-gold; margin-bottom:.2rem; }
.chat-text { font-size:.95rem; line-height:1.7; color:$text-primary;
  :deep(p) { margin-bottom:0; }
  :deep(strong) { color:$accent-gold; }
  :deep(em) { color:$text-secondary; }
}

.system-block { align-self:center; margin:.5rem 0 1rem; padding:.5rem 1rem; color:$accent-gold; border:1px solid rgba($accent-gold,.16); background:rgba($accent-gold,.045); font-family:$font-ui; font-size:.78rem; letter-spacing:.08em; }

.continue-hint { text-align:center; padding:.6rem 0; cursor:pointer; }
.arrow { color:$accent-gold; font-size:1.2rem; animation:blink 1.5s infinite; }
@keyframes blink { 0%,100%{opacity:.3} 50%{opacity:1} }

// Transition inline (no box)
.trans-inline { margin:.8rem 0 1.2rem; padding:1rem 1.2rem; border-top:1px solid rgba($accent-red,.18); border-bottom:1px solid rgba($accent-red,.12); background:linear-gradient(90deg,transparent,rgba($accent-red,.035),transparent); animation:fadeIn .3s ease-out; }
@keyframes fadeIn { from{opacity:0;transform:translateY(4px)} to{opacity:1;transform:translateY(0)} }
.trans-text { color:$text-secondary; font-size:.93rem; line-height:1.8;
  :deep(p) { margin-bottom:.5rem; text-indent:2em; &:first-child{text-indent:0} }
  :deep(strong) { color:$accent-gold; }
}

// Choices
.choice-area { margin:1.25rem 0; }
.choice-btn { display:grid; grid-template-columns:34px 1fr; align-items:center; width:100%; min-height:54px; padding:.72rem 2.7rem .72rem .55rem; margin-bottom:.58rem;
  background:linear-gradient(135deg, rgba(26,20,16,.95), rgba(30,24,18,.9));
  border:1px solid rgba($accent-gold,.18); border-left:3px solid rgba($accent-gold,.35);
  color:$text-primary; font-family:$font-body; font-size:.95rem; text-align:left; cursor:pointer; transition:.2s; position:relative;
  &:hover:not(.chosen) { border-color:rgba($accent-gold,.5); border-left-color:$accent-gold; transform:translateX(2px); }
  &.chosen { opacity:.35; cursor:default; border-left-color:rgba($text-dim,.3); .choice-text{text-decoration:line-through} }
  &.locked { opacity:.48; cursor:not-allowed; border-color:rgba($text-dim,.16); border-left-color:rgba($text-dim,.3); }
  &.warp { border-color:rgba($accent-ghost,.35); border-left-color:rgba($accent-ghost,.6); border-style:dashed; }
  &.scene-trans { border-color:rgba($accent-red,.25); border-left-color:rgba($accent-red,.5); background:linear-gradient(135deg, rgba(20,14,14,.95), rgba(26,16,16,.9));
    &:hover:not(.chosen) { border-color:rgba($accent-red,.5); border-left-color:$accent-red; }
  }
}
.choice-index{align-self:stretch;display:flex;align-items:center;justify-content:center;margin-right:.75rem;border-right:1px solid rgba($accent-gold,.12);color:rgba($accent-gold,.42);font-family:$font-ui;font-size:.64rem;letter-spacing:.08em}
.choice-copy{display:block;min-width:0}
.choice-text{display:block}
.choice-reason { display:block; margin-top:.35rem; color:$text-dim; font-family:$font-ui; font-size:.72rem; }
.chosen-mark { position:absolute; right:.8rem; top:50%; transform:translateY(-50%); color:$accent-gold; font-size:.8rem; }
.warp-tag { position:absolute; right:.8rem; top:50%; transform:translateY(-50%); font-family:$font-ui; font-size:.65rem; color:rgba($accent-ghost,.6); border:1px solid rgba($accent-ghost,.25); padding:.1rem .4rem; border-radius:2px; }
.trans-arrow { position:absolute; right:.8rem; top:50%; transform:translateY(-50%); color:rgba($accent-red,.6); font-size:1rem; }

// Panels
.panel { max-width:400px; margin:0 auto 1rem; padding:1rem; background:rgba($bg-void,.95); border:1px solid rgba($accent-gold,.15); border-radius:6px; }
.p-empty { color:$text-dim; text-align:center; padding:1rem; font-size:.85rem; }
.p-row { display:flex; align-items:center; gap:.5rem; padding:.4rem 0; border-bottom:1px solid rgba($accent-gold,.06);
  button { padding:.2rem .6rem; background:transparent; border:1px solid rgba($accent-gold,.2); color:$text-secondary; font-size:.75rem; cursor:pointer; border-radius:2px;
    &:hover{ border-color:$accent-gold; color:$accent-gold; }
    &.p-del { border-color:rgba($accent-red,.2); color:rgba($accent-red,.6); &:hover{ border-color:$accent-red; color:$accent-red; } }
  }
}
.p-name { flex:1; color:$text-primary; font-size:.85rem; }
.p-meta { color:$text-dim; font-size:.7rem; }
.p-close { display:block; margin:.5rem auto 0; padding:.3rem 1.5rem; background:transparent; border:1px solid rgba($accent-gold,.15); color:$text-dim; font-size:.8rem; cursor:pointer; }

// Start
.start-screen { display:flex; align-items:center; justify-content:center; height:100%; background:radial-gradient(circle at 50% 42%,rgba($accent-red,.08),transparent 22%),linear-gradient(135deg,transparent 49.8%,rgba($accent-gold,.035) 50%,transparent 50.2%); }
.start-content { position:relative; text-align:center; padding:4rem 5rem; border-top:1px solid rgba($accent-gold,.16); border-bottom:1px solid rgba($accent-gold,.08); }
.start-content::after{content:'循';position:absolute;right:1rem;bottom:1rem;width:42px;height:42px;display:flex;align-items:center;justify-content:center;border:1px solid rgba($accent-red,.34);color:rgba($accent-red,.38);font-family:$font-display;font-size:1.35rem;transform:rotate(-7deg)}
h1 { font-family:$font-display; font-size:3rem; font-weight:700; color:$accent-gold; letter-spacing:.15em; margin-bottom:.5rem; }
.divider { color:$accent-red; margin:0 .3rem; }
.start-screen p { color:$text-dim; font-size:.95rem; margin-bottom:2.5rem; }
.start-btn { padding:.8rem 3.5rem; font-size:1.1rem; background:transparent; color:$accent-red; border:1px solid rgba($accent-red,.4); font-family:$font-display; letter-spacing:.1em; cursor:pointer; transition:.3s;
  &:hover { background:rgba($accent-red,.1); border-color:$accent-red; }
}

// Scene transitions
.trans-overlay { position:fixed; inset:0; z-index:500; pointer-events:none; }
.trans-ink { background:radial-gradient(circle at 50% 50%, #2a2018 0%, #1a1410 60%, #0d0804 100%); animation:inkIn .5s ease-in forwards, inkOut .6s ease-out .5s forwards; }
@keyframes inkIn { 0%{clip-path:circle(0% at 50% 50%)} 100%{clip-path:circle(85% at 50% 50%)} }
@keyframes inkOut { 0%{clip-path:circle(85% at 50% 50%)} 100%{clip-path:circle(0% at 50% 50%)} }
.trans-rift { background:radial-gradient(ellipse at 50% 50%, #1a0808 0%, #0d0000 100%); animation:riftIn .45s ease-in forwards, riftOut .7s ease-out .45s forwards; }
@keyframes riftIn { 0%{clip-path:inset(0 50% 0 50%);opacity:0} 20%{opacity:1} 100%{clip-path:inset(0 0 0 0)} }
@keyframes riftOut { 0%{clip-path:inset(0 0 0 0);opacity:1} 100%{clip-path:inset(0 50% 0 50%);opacity:0} }
.trans-title { background:radial-gradient(ellipse at center, #1a1410 0%, #0d0804 100%); display:flex; flex-direction:column; align-items:center; justify-content:center; animation:titleIn .4s ease-in forwards, titleOut .5s ease-out .9s forwards; }
@keyframes titleIn { 0%{opacity:0} 100%{opacity:1} }
@keyframes titleOut { 0%{opacity:1} 100%{opacity:0} }
.trans-title-text { font-family:$font-display; font-size:2.2rem; color:$accent-gold; letter-spacing:.2em; text-align:center; animation:titleFade .5s ease-out .2s both; }
.trans-title-time { font-family:$font-ui; font-size:.85rem; color:$text-dim; letter-spacing:.15em; margin-top:.6rem; animation:titleFade .5s ease-out .4s both; }
@keyframes titleFade { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }

.scene-notify { position:fixed; top:15%; left:50%; transform:translateX(-50%); z-index:310; color:$accent-gold; font-family:$font-display; font-size:1.2rem; pointer-events:none; animation:notifyAnim 2.5s ease-out; }
@keyframes notifyAnim { 0%{opacity:0;transform:translateX(-50%) translateY(-10px)} 15%{opacity:1;transform:translateX(-50%) translateY(0)} 70%{opacity:1} 100%{opacity:0} }
.cycle-toast { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:100; color:$accent-gold; font-family:$font-display; font-size:1.1rem; pointer-events:none; animation:cycleFade 3s ease-in-out forwards; }
.cycle-icon { display:inline-block; animation:spin 8s linear infinite; }
@keyframes cycleFade { 0%,100%{opacity:0} 50%{opacity:1} }
@keyframes spin { from{transform:rotate(0)} to{transform:rotate(360deg)} }

@media (max-width:760px){
  .game-main{padding-bottom:2rem}
  .content-wrapper{min-height:auto;padding:.8rem 1rem 2rem}
  .content-wrapper::before{left:4px}
  .narrative-box{padding:1rem .9rem 1rem 1.05rem}
  .narrative-text{font-size:.94rem;line-height:1.85}
  .chat-avatar{width:32px;height:32px}
  .chat-bubble{max-width:88%;padding:.65rem .8rem}
  .choice-btn{grid-template-columns:28px 1fr;padding:.65rem 2.2rem .65rem .4rem;font-size:.9rem}
  .start-content{padding:3rem 1.25rem;width:calc(100% - 2rem)}
  h1{font-size:2rem}
}

@media (prefers-reduced-motion:reduce){
  .game-play,.bg-vignette,.chat-row,.trans-overlay,.cycle-icon,.arrow{animation:none!important;transition:none!important}
}
</style>
