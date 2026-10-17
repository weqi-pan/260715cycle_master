import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import type { Frame, SaveSummary } from '@cycle-master/api-contract'
import { gameApi, ApiError } from '../features/game/api'
import { blocksToPlayback, type VisibleContentBlock } from '../lib/playbackTimeline'

export const useGameStore = defineStore('game', () => {
  const frame = ref<Frame | null>(null)
  const timeline = ref<VisibleContentBlock[]>([])
  const busy = ref(false)
  const error = ref<string | null>(null)
  const fatal = ref(false)
  const saves = ref<SaveSummary[]>([])
  const saveName = ref('')
  const openBackpack = ref(false)
  const openMap = ref(false)

  const canAct = computed(() => Boolean(frame.value && !busy.value && !fatal.value))
  const hasResultBlocks = computed(() => timeline.value.some(block => block.type === 'check_result'))

  function errorMessage(error: unknown): string {
    if (error instanceof ApiError) return error.message
    return error instanceof Error ? error.message : '发生未知错误。'
  }

  function present(next: Frame, mode: 'start' | 'resume' | 'choose') {
    const nodeChanged = !frame.value || frame.value.state.currentNodeId !== next.state.currentNodeId
    frame.value = next
    const result = blocksToPlayback(next.resultBlocks)
    const entry = blocksToPlayback(next.entryBlocks)
    timeline.value = mode === 'choose' && nodeChanged ? [...result, ...entry] : result
    openBackpack.value = false
    openMap.value = false
  }

  async function run<T>(action: () => Promise<T>): Promise<T | null> {
    if (busy.value || fatal.value) return null
    busy.value = true
    error.value = null
    try {
      return await action()
    } catch (caught) {
      error.value = errorMessage(caught)
      if (caught instanceof ApiError && (caught.status === 0 || caught.code === 'TURN_STALE' || caught.code === 'INTERNAL_ERROR')) {
        fatal.value = true
      }
      return null
    } finally {
      busy.value = false
    }
  }

  async function start() {
    const next = await run(async () => gameApi.start())
    if (next) present(next, 'start')
  }

  async function resume(saveId: string) {
    const next = await run(async () => gameApi.resume(saveId))
    if (next) present(next, 'resume')
  }

  async function choose(choiceId: string) {
    const current = frame.value
    if (!current || !canAct.value) return
    const next = await run(async () => gameApi.choose({
      nodeId: current.state.currentNodeId,
      choiceId,
      turnId: current.turnId,
    }))
    if (next) present(next, 'choose')
  }

  async function discard(itemId: string) {
    const current = frame.value
    if (!current || !canAct.value) return
    const next = await run(async () => gameApi.discard({
      itemId,
      turnId: current.turnId,
    }))
    if (next) present(next, 'resume')
  }

  async function deleteSave(saveId: string) {
    const result = await run(async () => gameApi.deleteSave(saveId))
    if (result) await refreshSaves()
  }

  async function refreshSaves() {
    const result = await run(async () => gameApi.listSaves())
    if (result) saves.value = result.saves
  }

  async function save(overwriteId?: string) {
    const current = frame.value
    if (!current || !canAct.value) return
    const name = saveName.value.trim() || `循环 ${current.state.cycleCount + 1} · ${current.node.name}`
    const result = await run(async () => {
      if (overwriteId) return gameApi.updateSave(overwriteId, current.turnId, name)
      return gameApi.createSave(name, current.turnId)
    })
    if (result) {
      await refreshSaves()
      error.value = null
    }
  }

  function toggleBackpack() { openBackpack.value = !openBackpack.value }
  function toggleMap() { openMap.value = !openMap.value }
  function leaveGame() {
    frame.value = null
    timeline.value = []
    fatal.value = false
    error.value = null
  }

  return {
    frame, timeline, busy, error, fatal, saves, saveName, openBackpack, openMap,
    canAct, hasResultBlocks,
    start, resume, choose, discard, deleteSave, refreshSaves, save, toggleBackpack, toggleMap, leaveGame,
  }
})
