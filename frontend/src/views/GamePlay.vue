<!-- GamePlay.vue — five-layer visual novel layout -->
<template>
  <div class="game-play" @click.self="handleContinue">
    <!-- z-0: Background -->
    <BackgroundLayer :background="store.currentNode?.background ?? null" />

    <!-- z-10: Character layer (placeholder) -->
    <CharacterLayer />

    <!-- z-20: Dialog box -->
    <DialogBox
      v-if="store.currentNode"
      :content="store.currentNode.content"
      :speaker="store.currentNode.speaker ?? null"
      :speaker-avatar="store.currentNode.speaker_avatar ?? null"
      :choices="store.choices"
      @continue="handleContinue"
      @select="handleChoice"
    />

    <!-- z-100: Status bar -->
    <StatusBar
      v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count"
      :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes"
      :inventory="store.currentState.inventory"
      :node-name="store.currentNode?.name"
    />

    <!-- Start screen -->
    <div v-if="!store.currentNode && !store.loading" class="start-screen">
      <div class="start-content">
        <h1 class="start-title">荔湾<span class="title-divider">·</span>四日轮回</h1>
        <p class="start-subtitle">荔湾广场之下，时间如莫比乌斯环般扭曲</p>
        <button class="start-btn" @click="store.init()">踏入循环</button>
      </div>
    </div>

    <!-- Loading / Error -->
    <div v-if="store.loading" class="loading">
      <span class="loading-dot">·</span>
    </div>
    <div v-if="store.error" class="error">
      <p>{{ store.error }}</p>
      <button @click="store.init()">重试</button>
    </div>

    <!-- Cycle event toast -->
    <div v-if="store.cycleEvent" class="cycle-event">
      <span class="cycle-icon">⟳</span>
      第 {{ store.cycleEvent.cycle_count }} 次循环完成
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import BackgroundLayer from '@/components/player/BackgroundLayer.vue'
import CharacterLayer from '@/components/player/CharacterLayer.vue'
import DialogBox from '@/components/player/DialogBox.vue'
import StatusBar from '@/components/player/StatusBar.vue'

const store = useGameStore()

onMounted(() => { store.init() })

function handleContinue() {
  // If choices are available, ignore continue clicks — user must pick one
  if (store.choices.length > 0) return
}

function handleChoice(id: string) {
  store.choose(id)
}
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.game-play {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  position: relative;
  background: $bg-void;
  cursor: default;
}

// ── Start Screen ──
.start-screen {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  align-items: center;
  justify-content: center;
  background: $bg-void;
}

.start-content { text-align: center; }

.start-title {
  font-family: $font-display;
  font-size: 3rem;
  font-weight: 700;
  color: $accent-gold;
  letter-spacing: 0.15em;
  margin-bottom: 0.5rem;
}

.title-divider { color: $accent-red; margin: 0 0.3rem; }

.start-subtitle {
  color: $text-dim;
  font-size: 0.95rem;
  margin-bottom: 2.5rem;
}

.start-btn {
  padding: 0.8rem 3.5rem;
  font-size: 1.1rem;
  background: transparent;
  color: $accent-red;
  border: 1px solid rgba($accent-red, 0.4);
  font-family: $font-display;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: all 0.3s;
  &:hover {
    background: rgba($accent-red, 0.1);
    border-color: $accent-red;
    box-shadow: 0 0 20px rgba($accent-red, 0.15);
  }
}

// ── Loading / Error ──
.loading {
  position: fixed;
  inset: 0;
  z-index: 200;
  display: flex;
  justify-content: center;
  align-items: center;
  pointer-events: none;
}

.loading-dot {
  font-size: 3rem;
  color: $accent-gold;
  animation: loading-pulse 1.5s ease-in-out infinite;
}

@keyframes loading-pulse {
  0%, 100% { opacity: 0.15; }
  50% { opacity: 1; }
}

.error {
  position: fixed;
  inset: 0;
  z-index: 300;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba($bg-void, 0.9);
  color: $accent-red;

  button {
    margin-top: 1.5rem;
    padding: 0.5rem 2rem;
    background: transparent;
    border: 1px solid rgba($accent-gold, 0.3);
    color: $accent-gold;
    cursor: pointer;
    font-family: $font-ui;
    &:hover { border-color: $accent-gold; }
  }
}

// ── Cycle Event Toast ──
.cycle-event {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 250;
  color: $accent-gold;
  font-family: $font-display;
  font-size: 1.1rem;
  letter-spacing: 0.1em;
  animation: cycle-fade 3s ease-in-out infinite;
  pointer-events: none;
}

.cycle-icon {
  display: inline-block;
  margin-right: 0.3rem;
  animation: spin 8s linear infinite;
}

@keyframes cycle-fade {
  0%, 100% { opacity: 0; }
  50% { opacity: 1; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
