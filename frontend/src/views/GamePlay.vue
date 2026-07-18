<!-- frontend/src/views/GamePlay.vue -->
<template>
  <div class="game-play">
    <StatusBar
      v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count"
      :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes"
      :node-name="store.currentNode?.name"
    />

    <div class="game-main">
      <div v-if="store.loading" class="loading">加载中...</div>
      <div v-else-if="store.error" class="error">{{ store.error }}</div>

      <template v-else-if="store.currentNode">
        <div class="time-label" v-if="store.currentNode.time_label">
          {{ store.currentNode.time_label }}
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
          ⏳ 第 {{ store.cycleEvent.cycle_count }} 次循环完成
        </div>
      </template>

      <div v-else class="start-screen">
        <h1>荔湾·四日轮回</h1>
        <button @click="store.init()">开始游戏</button>
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
  padding-bottom: 4rem;
}

.time-label {
  text-align: center;
  color: $text-secondary;
  font-size: 0.9rem;
  padding: 1rem 0 0;
}

.loading, .error {
  text-align: center;
  padding: 4rem;
}

.start-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;

  h1 {
    font-size: 2.5rem;
    color: $accent-gold;
    margin-bottom: 2rem;
  }

  button {
    padding: 1rem 3rem;
    font-size: 1.2rem;
    background: $accent-red;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;

    &:hover { opacity: 0.9; }
  }
}

.cycle-event {
  text-align: center;
  color: $accent-gold;
  padding: 2rem;
  font-size: 1.1rem;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
