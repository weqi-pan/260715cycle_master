import { randomUUID } from 'node:crypto'
import type { GameState, Frame, SaveMetadata, SaveSummary } from '@cycle-master/api-contract'
import { GameStateSchema } from '@cycle-master/api-contract'
import type { StorySnapshotV3 } from '@cycle-master/story-schema'
import { GameEngine, STATE_SCHEMA_VERSION } from '@cycle-master/game-runtime'
import { GameDatabase } from './database.ts'
import { TurnStore } from './turnStore.ts'

export class HttpError extends Error {
  status: number
code: string
details?: unknown

  constructor(status: number, code: string, message: string, details?: unknown) {
    super(message)
    this.name = 'HttpError'
    this.status = status
    this.code = code
    if (details !== undefined) this.details = details
  }
}

function nowIso(): string {
  return new Date().toISOString()
}

export class GameService {
  private readonly engine = new GameEngine()
  private readonly turns = new TurnStore()
  private readonly story: StorySnapshotV3
  private readonly database: GameDatabase

  constructor(story: StorySnapshotV3, database: GameDatabase) {
    this.story = story
    this.database = database
  }

  health() {
    return {
      status: 'ok' as const,
      apiVersion: 2,
      storyRevision: this.story.revision,
      stateSchemaVersion: STATE_SCHEMA_VERSION,
    }
  }

  start(): Frame {
    const result = this.engine.start(this.story)
    const state = result.state as GameState
    const turnId = this.turns.issue(state)
    return this.frame(this.engine.buildFrame(this.story, result.state, turnId))
  }

  resume(saveId: string): Frame {
    const row = this.database.getSave(saveId)
    if (!row) throw new HttpError(404, 'NOT_FOUND', '存档不存在。')
    if (row.story_revision !== this.story.revision) {
      throw new HttpError(409, 'SAVE_STORY_MISMATCH', '存档与当前剧情不匹配。', {
        saveStoryRevision: row.story_revision,
        currentStoryRevision: this.story.revision,
      })
    }
    if (row.state_schema_version !== STATE_SCHEMA_VERSION) {
      throw new HttpError(409, 'SAVE_STATE_VERSION_MISMATCH', '存档状态格式与当前版本不匹配。', {
        saveStateSchemaVersion: row.state_schema_version,
        currentStateSchemaVersion: STATE_SCHEMA_VERSION,
      })
    }
    let parsed: GameState
    try {
      parsed = GameStateSchema.parse(JSON.parse(row.state_json))
    } catch (error) {
      throw new HttpError(409, 'SAVE_INVALID_STATE', '存档状态无效。', { cause: String(error) })
    }
    parsed.persistentNodes = this.database.loadPersistentNodes(saveId) as GameState['persistentNodes']
    try {
      const resumed = this.engine.resume(this.story, parsed as never)
      const state = resumed.state as GameState
      const turnId = this.turns.issue(state)
      return this.frame(this.engine.buildFrame(this.story, resumed.state, turnId))
    } catch (error) {
      throw new HttpError(409, 'SAVE_INVALID_STATE', '存档状态无效。', { cause: String(error) })
    }
  }

  choose(nodeId: string, choiceId: string, turnId: string): Frame {
    const state = this.consume(turnId)
    try {
      const result = this.engine.choose(this.story, state as never, { nodeId, choiceId })
      const nextState = result.state as GameState
      this.turns.replace(turnId, nextState)
      return this.frame(this.engine.buildFrame(this.story, result.state, turnId, {
        resultBlocks: result.resultBlocks,
        cycleEvent: result.cycleEvent,
        ...(result.transitionText ? { transitionText: result.transitionText } : {}),
      }))
    } catch (error) {
      this.turns.replace(turnId, state)
      throw error
    }
  }

  discard(itemId: string, turnId: string): Frame {
    const state = this.consume(turnId)
    try {
      const result = this.engine.discard(this.story, state as never, itemId)
      const nextState = result.state as GameState
      this.turns.replace(turnId, nextState)
      return this.frame(this.engine.buildFrame(this.story, result.state, turnId))
    } catch (error) {
      this.turns.replace(turnId, state)
      throw error
    }
  }

  listSaves(): { saves: SaveSummary[] } {
    return { saves: this.database.listSaves().map(row => this.summary(row)) }
  }

  saveMetadata(saveId: string): SaveMetadata {
    const row = this.database.getSave(saveId)
    if (!row) throw new HttpError(404, 'NOT_FOUND', '存档不存在。')
    return this.summary(row)
  }

  createSave(name: string, turnId: string): { status: 'ok' } {
    const state = this.consumeCurrent(turnId)
    const id = randomUUID()
    this.database.createSave({ id, name, revision: this.story.revision, state, now: nowIso() })
    return { status: 'ok' }
  }

  updateSave(saveId: string, turnId: string, name?: string): { status: 'ok' } {
    const state = this.consumeCurrent(turnId)
    const updated = this.database.updateSave({
      id: saveId,
      ...(name ? { name } : {}),
      revision: this.story.revision,
      state,
      now: nowIso(),
    })
    if (!updated) throw new HttpError(404, 'NOT_FOUND', '存档不存在。')
    return { status: 'ok' }
  }

  deleteSave(saveId: string): { status: 'ok' } {
    if (!this.database.deleteSave(saveId)) throw new HttpError(404, 'NOT_FOUND', '存档不存在。')
    return { status: 'ok' }
  }

  private consume(turnId: string): GameState {
    const state = this.turns.current(turnId)
    if (!state) throw new HttpError(409, 'TURN_STALE', '回合已过期或已被消耗。')
    return state
  }

  private consumeCurrent(turnId: string): GameState {
    const state = this.consume(turnId)
    return state
  }

  private frame(frame: import('@cycle-master/game-runtime').Frame): Frame {
    return frame as unknown as Frame
  }

  private compatibility(row: { story_revision: string; state_schema_version: number }): { compatible: boolean; incompatibleReason?: string } {
    if (row.story_revision !== this.story.revision) return { compatible: false, incompatibleReason: 'SAVE_STORY_MISMATCH' }
    if (row.state_schema_version !== STATE_SCHEMA_VERSION) return { compatible: false, incompatibleReason: 'SAVE_STATE_VERSION_MISMATCH' }
    return { compatible: true }
  }

  private summary(row: import('./database').SaveRow): SaveSummary {
    const compatibility = this.compatibility(row)
    const result: SaveSummary = {
      id: row.id,
      name: row.name,
      storyRevision: row.story_revision,
      stateSchemaVersion: row.state_schema_version,
      currentNodeId: row.current_node_id,
      cycleCount: row.cycle_count,
      compatible: compatibility.compatible,
      createdAt: row.created_at,
      updatedAt: row.updated_at,
    }
    if (compatibility.incompatibleReason) result.incompatibleReason = compatibility.incompatibleReason
    return result
  }
}
