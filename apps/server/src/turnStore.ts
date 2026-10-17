import { randomUUID } from 'node:crypto'
import type { GameState } from '@cycle-master/api-contract'

export class TurnStore {
  private active = new Map<string, GameState>()

  issue(state: GameState): string {
    this.active.clear()
    const turnId = randomUUID()
    this.active.set(turnId, structuredClone(state))
    return turnId
  }

  current(turnId: string): GameState | null {
    const state = this.active.get(turnId)
    return state ? structuredClone(state) : null
  }

  replace(turnId: string, state: GameState): boolean {
    if (!this.active.has(turnId)) return false
    this.active.set(turnId, structuredClone(state))
    return true
  }

  clear(): void {
    this.active.clear()
  }

  get size(): number {
    return this.active.size
  }
}
