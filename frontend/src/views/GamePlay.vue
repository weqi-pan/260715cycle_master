<!-- frontend/src/views/GamePlay.vue -->
<template>
  <div class="game-play">
    <StatusBar
      v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count"
      :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes"
      :inventory="store.currentState.inventory"
      :node-name="store.currentNode?.name"
    />

    <div class="game-main">
      <div v-if="store.loading" class="loading">
        <span class="loading-dot">·</span>
      </div>
      <div v-else-if="store.error" class="error">
        <p>{{ store.error }}</p>
        <button @click="store.init()">重试</button>
      </div>

      <template v-else-if="store.currentNode">
        <div class="time-label" v-if="store.currentNode.time_label">
          <span class="time-icon">◈</span> {{ store.currentNode.time_label }}
        </div>
        <NarrativePanel
          :content="store.currentNode.content"
          :speaker="store.currentNode.speaker"
        />
        <ChoicePanel
          :choices="store.choices"
          @select="handleChoice"
        />

        <div v-if="store.cycleEvent" class="cycle-event">
          <span class="cycle-icon">⟳</span>
          第 {{ store.cycleEvent.cycle_count }} 次循环完成
        </div>
      </template>

      <div v-else class="start-screen">
        <div class="start-content">
          <h1 class="start-title">荔湾<span class="title-divider">·</span>四日轮回</h1>
          <p class="start-subtitle">荔湾广场之下，时间如莫比乌斯环般扭曲</p>
          <button class="start-btn" @click="store.init()">踏入循环</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import NarrativePanel from '@/components/player/NarrativePanel.vue'
import ChoicePanel from '@/components/player/ChoicePanel.vue'
import StatusBar from '@/components/player/StatusBar.vue'

const store = useGameStore()

onMounted(() => {
  store.init()
})

function handleChoice(choiceId: string) {
  store.choose(choiceId)
}
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.game-play {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.game-main {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 5rem;
}

.time-label {
  text-align: center;
  color: $text-dim;
  font-family: $font-ui;
  font-size: 0.85rem;
  padding: 1.2rem 0 0;
  letter-spacing: 0.1em;
}

.time-icon {
  color: $accent-gold;
}

.loading {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60vh;
}

.loading-dot {
  font-size: 2rem;
  color: $accent-gold;
  animation: loading-pulse 1.5s ease-in-out infinite;
}

@keyframes loading-pulse {
  0%, 100% { opacity: 0.2; }
  50% { opacity: 1; }
}

.error {
  text-align: center;
  padding: 4rem;
  color: $accent-red;

  button {
    margin-top: 1.5rem;
    padding: 0.5rem 2rem;
    background: transparent;
    border: 1px solid rgba($accent-gold, 0.3);
    color: $accent-gold;
    font-family: $font-ui;
    cursor: pointer;
    transition: all 0.2s;

    &:hover {
      border-color: $accent-gold;
      background: rgba($accent-gold, 0.08);
    }
  }
}

// ── Start Screen ──
.start-screen {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  position: relative;
}

.start-content {
  text-align: center;
}

.start-title {
  font-family: $font-display;
  font-size: 3rem;
  font-weight: 700;
  color: $accent-gold;
  letter-spacing: 0.15em;
  margin-bottom: 0.5rem;
}

.title-divider {
  color: $accent-red;
  margin: 0 0.3rem;
}

.start-subtitle {
  color: $text-dim;
  font-size: 0.95rem;
  margin-bottom: 2.5rem;
  letter-spacing: 0.05em;
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

// ── Cycle Event ──
.cycle-event {
  text-align: center;
  color: $accent-gold;
  padding: 2rem;
  font-family: $font-display;
  font-size: 1.1rem;
  letter-spacing: 0.1em;
  animation: cycle-fade 3s ease-in-out infinite;
}

.cycle-icon {
  display: inline-block;
  margin-right: 0.3rem;
  animation: spin 8s linear infinite;
}

@keyframes cycle-fade {
  0%, 100% { opacity: 0.6; }
  50% { opacity: 1; }
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
