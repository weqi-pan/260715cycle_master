// frontend/src/stores/gameStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Frame, GameState, NodeData, ChoiceResult } from '@/types'
import axios from 'axios'
import { startGame, resumeGame, chooseAction } from '@/api/game'

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

  function errorMessage(e: unknown, fallback: string) {
    if (axios.isAxiosError(e)) {
      return String(e.response?.data?.detail ?? e.message ?? fallback)
    }
    return e instanceof Error ? e.message : fallback
  }

  function acceptFrame(frame: Frame, resetHistory = false) {
    currentFrame.value = frame
    history.value = resetHistory
      ? [frame]
      : [...history.value.slice(-49), frame]
  }

  async function init() {
    loading.value = true
    error.value = null
    try {
      const frame = await startGame()
      acceptFrame(frame, true)
    } catch (e: unknown) {
      error.value = errorMessage(e, '无法开始游戏')
    } finally {
      loading.value = false
    }
  }


  async function resume(state: GameState) {
    loading.value = true
    error.value = null
    try {
      const frame = await resumeGame(state)
      acceptFrame(frame, true)
    } catch (e: unknown) {
      error.value = errorMessage(e, '无法加载存档')
      throw e
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
      acceptFrame(frame)
    } catch (e: unknown) {
      error.value = errorMessage(e, '无法处理选择')
    } finally {
      loading.value = false
    }
  }

  return { currentFrame, loading, error, history, currentNode, currentState, choices, cycleEvent, transitionText, init, resume, choose }
})
