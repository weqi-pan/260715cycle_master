import axios from 'axios'
import type { Frame, GameState } from '@/types'

const api = axios.create({ baseURL: '/api' })

export async function startGame(): Promise<Frame> {
  const res = await api.get<Frame>('/game/start')
  return res.data
}

export async function resumeGame(state: GameState): Promise<Frame> {
  const res = await api.post<Frame>('/game/resume', state)
  return res.data
}

export async function chooseAction(nodeId: string, choiceId: string, turnId: string): Promise<Frame> {
  const res = await api.post<Frame>(`/game/choose/${nodeId}`, {
    choice_id: choiceId,
    turn_id: turnId,
  })
  return res.data
}

export async function discardInventoryItem(itemId: string, turnId: string): Promise<Frame> {
  const res = await api.post<Frame>(`/game/inventory/discard/${itemId}`, { turn_id: turnId })
  return res.data
}
