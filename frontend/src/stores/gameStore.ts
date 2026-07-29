// frontend/src/stores/gameStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Frame, GameState, NodeData, ChoiceResult } from '@/types'
import axios from 'axios'
import { startGame, resumeGame, chooseAction, discardInventoryItem } from '@/api/game'
import { visibleChoices } from '@/player/choiceVisibility'
import { resolveFrameRequest } from '@/player/frameRequest'

export const useGameStore = defineStore('game', () => {
  const currentFrame = ref<Frame | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const history = ref<Frame[]>([])

  const currentNode = computed<NodeData | null>(() => currentFrame.value?.node ?? null)
  const currentState = computed<GameState | null>(() => currentFrame.value?.state ?? null)
  const choices = computed<ChoiceResult[]>(() => visibleChoices(currentFrame.value?.available_choices ?? []))
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
    const outcome = await resolveFrameRequest(currentFrame.value, startGame)
    if (outcome.error) {
      error.value = errorMessage(outcome.error, '无法开始游戏')
    } else if (outcome.frame) {
      acceptFrame(outcome.frame, true)
    }
    loading.value = false
  }


  async function resume(state: GameState) {
    loading.value = true
    error.value = null
    const outcome = await resolveFrameRequest(
      currentFrame.value,
      () => resumeGame(state),
    )
    loading.value = false
    if (outcome.error) {
      error.value = errorMessage(outcome.error, '无法加载存档')
      throw outcome.error
    }
    if (outcome.frame) {
      acceptFrame(outcome.frame, true)
    }
  }

  async function choose(choiceId: string) {
    if (!currentFrame.value) return
    const frameBeforeRequest = currentFrame.value
    const nodeId = frameBeforeRequest.node.id
    loading.value = true
    error.value = null
    const outcome = await resolveFrameRequest(
      frameBeforeRequest,
      () => chooseAction(nodeId, choiceId, frameBeforeRequest.turn_id),
    )
    if (outcome.error) {
      error.value = errorMessage(outcome.error, '无法处理选择')
    } else if (outcome.frame) {
      acceptFrame(outcome.frame)
    }
    loading.value = false
  }

  async function discard(itemId: string) {
    if (!currentFrame.value) return
    const frameBeforeRequest = currentFrame.value
    loading.value = true
    error.value = null
    const outcome = await resolveFrameRequest(
      frameBeforeRequest,
      () => discardInventoryItem(itemId, frameBeforeRequest.turn_id),
    )
    loading.value = false
    if (outcome.error) {
      error.value = errorMessage(outcome.error, '无法丢弃道具')
      throw outcome.error
    }
    if (outcome.frame) {
      acceptFrame(outcome.frame)
    }
  }

  return { currentFrame, loading, error, history, currentNode, currentState, choices, cycleEvent, transitionText, init, resume, choose, discard }
})
