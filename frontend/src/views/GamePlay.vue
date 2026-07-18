<!-- GamePlay.vue — 视觉小说主界面 -->
<template>
  <div class="game-play" @click="onBgClick">
    <!-- z-0: Background layer -->
    <div class="bg-layer">
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
        <div class="content-wrapper">
          <!-- Time label -->
          <div v-if="store.currentNode.time_label" class="time-label">
            ◈ {{ store.currentNode.time_label }}
          </div>

          <!-- Speaker -->
          <div v-if="store.currentNode.speaker" class="speaker-row">
            <div class="speaker-avatar">{{ store.currentNode.speaker[0] }}</div>
            <span class="speaker-name">{{ store.currentNode.speaker }}</span>
          </div>

          <!-- Narrative -->
          <div class="narrative-box">
            <div class="narrative-text" v-html="renderedContent" />
          </div>

          <!-- Choices -->
          <div v-if="store.choices.length" class="choice-area">
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

          <!-- Continue hint (no choices) -->
          <div v-else class="continue-hint" @click.stop="dismissTransition">
            <span class="arrow">▼</span>
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

    <!-- Cycle toast -->
    <div v-if="store.cycleEvent" class="cycle-toast">
      <span class="cycle-icon">⟳</span> 第 {{ store.cycleEvent.cycle_count }} 次循环完成
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import StatusBar from '@/components/player/StatusBar.vue'

const store = useGameStore()
onMounted(() => { store.init() })

function md2html(t: string): string {
  t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  t = t.replace(/\*(.+?)\*/g, '<em>$1</em>')
  t = t.replace(/---/g, '<span class="scene-break">· · ·</span>')
  t = t.replace(/\n\n/g, '</p><p>')
  return `<p>${t}</p>`
}

const renderedContent = computed(() => store.currentNode ? md2html(store.currentNode.content) : '')
const renderedTransition = computed(() => store.transitionText ? md2html(store.transitionText) : '')

function dismissTransition() {
  if (store.currentFrame) {
    store.currentFrame = { ...store.currentFrame, transition_text: undefined }
  }
}
function onBgClick() {
  if (store.choices.length > 0) return   // don't dismiss while choosing
  dismissTransition()
}
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

// ── Cycle toast ──
.cycle-toast { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:100; color:$accent-gold; font-family:$font-display; font-size:1.1rem; letter-spacing:0.1em; pointer-events:none; animation:cycleFade 3s infinite; }
.cycle-icon { display:inline-block; animation:spin 8s linear infinite; }
@keyframes cycleFade { 0%,100%{opacity:0} 50%{opacity:1} }
@keyframes spin { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
</style>
