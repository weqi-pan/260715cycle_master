// frontend/src/stores/gameStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Frame, GameState, NodeData, ChoiceResult } from '@/types'
import { startGame, chooseAction } from '@/api/game'

export const useGameStore = defineStore('game', () => {
  const currentFrame = ref<Frame | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const history = ref<Frame[]>([])

  const currentNode = computed<NodeData | null>(() => currentFrame.value?.node ?? null)
  const currentState = computed<GameState | null>(() => currentFrame.value?.state ?? null)
  const choices = computed<ChoiceResult[]>(() => currentFrame.value?.available_choices ?? [])
  const cycleEvent = computed(() => currentFrame.value?.cycle_event ?? null)
  const transitionText = computed(() => currentFrame.value?.transition_text ?? null)

  async function init() {
    loading.value = true
    error.value = null
    try {
      const frame = await startGame()
      currentFrame.value = frame
      history.value = [frame]
    } catch (e: any) {
      error.value = e.message || 'Failed to start game'
    } finally {
      loading.value = false
    }
  }

  async function choose(choiceId: string) {
    if (!currentFrame.value) return
    const nodeId = currentFrame.value.node.id
    const currentState = currentFrame.value.state
    loading.value = true
    error.value = null
    try {
      const frame = await chooseAction(nodeId, choiceId, currentState)
      currentFrame.value = frame
      history.value.push(frame)
    } catch (e: any) {
      error.value = e.message || 'Failed to process choice'
    } finally {
      loading.value = false
    }
  }

  return { currentFrame, loading, error, history, currentNode, currentState, choices, cycleEvent, transitionText, init, choose }
})
