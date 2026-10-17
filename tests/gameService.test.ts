import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { loadOrCompileStory } from '../packages/story-schema/src/index'
import { GameDatabase } from '../apps/server/src/database'
import { GameService, HttpError } from '../apps/server/src/service'

let tempDir: string
let service: GameService
let database: GameDatabase

beforeAll(async () => {
  tempDir = await mkdtemp(path.join(os.tmpdir(), 'cycle-master-service-'))
  const story = await loadOrCompileStory(path.resolve('content/story_v3'), path.join(tempDir, 'build'), true)
  database = new GameDatabase(path.join(tempDir, 'game.sqlite'))
  service = new GameService(story, database)
})

afterAll(async () => {
  database.close()
  await rm(tempDir, { recursive: true, force: true })
})

describe('GameService', () => {
  it('starts a new game with an active turn and available choices', () => {
    const frame = service.start()
    expect(frame.state.currentNodeId).toBe('A')
    expect(frame.turnId).not.toBe('')
    expect(frame.choices.some(choice => choice.available)).toBe(true)
  })

  it('保存不消耗回合，读档能恢复完整状态并签发新回合', async () => {
    const original = service.start()
    const choice = original.choices.find(item => item.available)!
    await service.createSave('回归测试', original.turnId)
    const advanced = service.choose(original.state.currentNodeId, choice.id, original.turnId)
    expect(advanced.state.currentNodeId).not.toBe(original.state.currentNodeId)
    const saves = service.listSaves().saves
    expect(saves).toHaveLength(1)
    expect(saves[0]!.compatible).toBe(true)
    const restored = service.resume(saves[0]!.id)
    expect(restored.state.currentNodeId).toBe(original.state.currentNodeId)
    expect(restored.state.playerAttributes).toEqual(original.state.playerAttributes)
    expect(restored.turnId).not.toBe(original.turnId)
  })

  it('rejects an unknown turn with a stable conflict error', async () => {
    const error = await Promise.resolve().then(() => service.choose('A', 'anything', 'missing-turn')).catch(caught => caught)
    expect(error).toBeInstanceOf(HttpError)
    expect(error.status).toBe(409)
    expect(error.code).toBe('TURN_STALE')
  })

  it('rejects unknown saves without changing other saves', async () => {
    const error = await Promise.resolve().then(() => service.resume('missing-save')).catch(caught => caught)
    expect(error).toBeInstanceOf(HttpError)
    expect(error.status).toBe(404)
    expect(service.listSaves().saves).toHaveLength(1)
  })
})
