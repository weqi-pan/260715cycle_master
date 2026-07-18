import axios from 'axios'
import type { Frame } from '@/types'

const api = axios.create({ baseURL: '/api' })

export async function startGame(): Promise<Frame> {
  const res = await api.get<Frame>('/game/start')
  return res.data
}

export async function chooseAction(nodeId: string, choiceId: string): Promise<Frame> {
  const res = await api.post<Frame>(`/game/choose/${nodeId}`, { choice_id: choiceId })
  return res.data
}
