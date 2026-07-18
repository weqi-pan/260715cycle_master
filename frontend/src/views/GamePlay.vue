<!-- GamePlay.vue -->
<template>
  <div class="game-play">
    <!-- Status bar -->
    <StatusBar
      v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count"
      :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes"
      :inventory="store.currentState.inventory"
      :node-name="store.currentNode?.name"
    />

    <!-- Main area -->
    <div class="game-main">
      <div v-if="store.loading" class="loading"><span class="dot">·</span></div>

      <div v-else-if="store.error" class="error">
        <p>{{ store.error }}</p>
        <button @click="store.init()">Retry</button>
      </div>

      <template v-else-if="store.currentNode">
        <!-- Time label -->
        <div v-if="store.currentNode.time_label" class="time-label">
          {{ store.currentNode.time_label }}
        </div>

        <!-- Speaker header -->
        <div v-if="store.currentNode.speaker" class="speaker-row">
          <div class="speaker-avatar">{{ store.currentNode.speaker[0] }}</div>
          <span class="speaker-name">{{ store.currentNode.speaker }}</span>
        </div>

        <!-- Narrative text -->
        <div class="narrative-box">
          <div class="narrative-text" v-html="renderedContent"></div>
        </div>

        <!-- Choices -->
        <div v-if="store.choices.length" class="choice-area">
          <button
            v-for="c in store.choices"
            :key="c.id"
            class="choice-btn"
            :class="{ warp: c.source === 'special_warp' }"
            @click="store.choose(c.id)"
          >{{ c.text }}</button>
        </div>
      </template>

      <!-- Start screen -->
      <div v-else class="start-screen">
        <h1>荔湾<span class="divider">·</span>四日轮回</h1>
        <p>荔湾广场之下，时间如莫比乌斯环般扭曲</p>
        <button class="start-btn" @click="store.init()">踏入循环</button>
      </div>
    </div>

    <!-- Transition text overlay -->
    <div v-if="store.transitionText" class="transition-overlay" @click="store.currentFrame = { ...store.currentFrame!, transition_text: undefined }">
      <div class="transition-text" v-html="renderedTransition"></div>
      <p class="dismiss-hint">(点击任意处继续)</p>
    </div>

    <!-- Cycle event -->
    <div v-if="store.cycleEvent" class="cycle-toast">
      ⟳ 第 {{ store.cycleEvent.cycle_count }} 次循环完成
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, computed } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import StatusBar from '@/components/player/StatusBar.vue'

const store = useGameStore()

onMounted(() => { store.init() })

const renderedContent = computed(() => {
  if (!store.currentNode) return ''
  return md2html(store.currentNode.content)
})

const renderedTransition = computed(() => {
  if (!store.transitionText) return ''
  return md2html(store.transitionText)
})

function md2html(text: string): string {
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>')
  text = text.replace(/---/g, '<span class="scene-break">· · ·</span>')
  text = text.replace(/\n\n/g, '</p><p>')
  return `<p>${text}</p>`
}
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.game-play {
  width: 100vw; height: 100vh; overflow: hidden;
  display: flex; flex-direction: column;
  background: $bg-void;
}

.game-main {
  flex: 1; overflow-y: auto; padding: 0 1.5rem 3rem;
}

// Loading
.loading { display: flex; justify-content: center; align-items: center; height: 60vh; }
.dot { font-size: 3rem; color: $accent-gold; animation: pulse 1.5s infinite; }
@keyframes pulse { 0%,100%{opacity:0.15} 50%{opacity:1} }

// Error
.error { text-align: center; padding: 4rem; color: $accent-red;
  button { margin-top:1rem; padding:0.5rem 2rem; background:transparent; border:1px solid rgba($accent-gold,0.3); color:$accent-gold; cursor:pointer; }
}

// Time label
.time-label { text-align:center; color:$text-dim; font-size:0.85rem; padding:1rem 0 0.5rem; }

// Speaker
.speaker-row { display:flex; align-items:center; gap:0.6rem; padding:0.5rem 0; max-width:$narrative-max-width; margin:0 auto; }
.speaker-avatar { width:32px; height:32px; border-radius:50%; background:rgba($accent-gold,0.1); border:1px solid rgba($accent-gold,0.25); display:flex; align-items:center; justify-content:center; color:$accent-gold; font-family:$font-display; font-size:0.9rem; flex-shrink:0; }
.speaker-name { color:$accent-gold; font-family:$font-ui; font-size:0.9rem; }

// Narrative
.narrative-box { max-width:$narrative-max-width; margin:0 auto; }
.narrative-text {
  font-size:1rem; line-height:1.85; letter-spacing:0.02em;
  :deep(p) { margin-bottom:0.8rem; text-indent:2em; &:first-child { text-indent:0; } }
  :deep(strong) { color:$accent-gold; }
  :deep(em) { color:$text-secondary; }
  :deep(.scene-break) { display:block; text-align:center; color:$accent-red; margin:1.5rem 0; letter-spacing:0.8em; }
}

// Choices
.choice-area { max-width:540px; margin:1.5rem auto; }
.choice-btn {
  display:block; width:100%; padding:0.8rem 1.2rem; margin-bottom:0.5rem;
  background:linear-gradient(135deg, rgba(26,20,16,0.95), rgba(30,24,18,0.9));
  border:1px solid rgba($accent-gold,0.18); border-left:3px solid rgba($accent-gold,0.35);
  color:$text-primary; font-family:$font-body; font-size:0.95rem;
  text-align:left; cursor:pointer; transition:all 0.2s;
  &:hover { border-color:rgba($accent-gold,0.5); border-left-color:$accent-gold; transform:translateX(2px); }
  &.warp { border-color:rgba($accent-ghost,0.35); border-left-color:rgba($accent-ghost,0.6); border-style:dashed; }
}

// Start screen
.start-screen { display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; text-align:center;
  h1 { font-family:$font-display; font-size:3rem; color:$accent-gold; letter-spacing:0.15em; margin-bottom:0.5rem; }
  .divider { color:$accent-red; }
  p { color:$text-dim; margin-bottom:2rem; }
}
.start-btn { padding:0.8rem 3.5rem; font-size:1.1rem; background:transparent; color:$accent-red; border:1px solid rgba($accent-red,0.4); font-family:$font-display; letter-spacing:0.1em; cursor:pointer; transition:0.3s;
  &:hover { background:rgba($accent-red,0.1); border-color:$accent-red; box-shadow:0 0 20px rgba($accent-red,0.15); }
}

// Transition overlay
.transition-overlay { position:fixed; inset:0; z-index:50; background:rgba(0,0,0,0.85); display:flex; align-items:center; justify-content:center; }
.transition-text { max-width:$narrative-max-width; padding:2rem; color:$text-primary; font-size:1rem; line-height:1.85; letter-spacing:0.02em;
  :deep(p) { margin-bottom:0.8rem; text-indent:2em; &:first-child { text-indent:0; } }
  :deep(strong) { color:$accent-gold; }
  :deep(em) { color:$text-secondary; }
}

// Cycle toast
.cycle-toast { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:100; color:$accent-gold; font-family:$font-display; font-size:1.1rem; pointer-events:none; animation:cycleFade 3s infinite; }
@keyframes cycleFade { 0%,100%{opacity:0} 50%{opacity:1} }
</style>
