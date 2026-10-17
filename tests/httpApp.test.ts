import { afterAll, beforeAll, describe, expect, it } from 'vitest'
import { mkdtemp, rm } from 'node:fs/promises'
import os from 'node:os'
import path from 'node:path'
import { Buffer } from 'node:buffer'
import { Readable } from 'node:stream'
import type { IncomingMessage, Server } from 'node:http'
import { loadOrCompileStory } from '../packages/story-schema/src/index'
import { GameDatabase } from '../apps/server/src/database'
import { GameService } from '../apps/server/src/service'
import { createApp } from '../apps/server/src/app'

interface FakeResponse {
  body: string
  headers: Record<string, unknown>
  status: number
  end(chunk?: string | Buffer): void
  writeHead(status: number, headers?: Record<string, unknown>): unknown
}

let tempDir: string
let app: Server
let database: GameDatabase
let service: GameService

function dispatch(method: string, url: string, body?: unknown): Promise<FakeResponse> {
  const request = Readable.from(body === undefined ? [] : [Buffer.from(JSON.stringify(body))]) as IncomingMessage
  request.method = method
  request.url = url
  const response: FakeResponse = {
    body: '',
    headers: {},
    status: 0,
    writeHead(status, headers = {}) {
      this.status = status
      this.headers = headers
      return this
    },
    end(chunk) {
      this.body = chunk?.toString() ?? ''
      return this
    },
  }
  return new Promise((resolve, reject) => {
    const originalEnd = response.end.bind(response)
    response.end = (chunk?: string | Buffer) => {
      originalEnd(chunk)
      resolve(response)
      return response
    }
    app.emit('request', request, response)
    request.on('error', reject)
  })
}

beforeAll(async () => {
  tempDir = await mkdtemp(path.join(os.tmpdir(), 'cycle-master-http-'))
  const story = await loadOrCompileStory(path.resolve('content/story_v3'), path.join(tempDir, 'build'), true)
  database = new GameDatabase(path.join(tempDir, 'game.sqlite'))
  service = new GameService(story, database)
  app = createApp(service, path.resolve('content/story_v3/assets'))
})

afterAll(async () => {
  app.close()
  database.close()
  await rm(tempDir, { recursive: true, force: true })
})

describe('HTTP 应用', () => {
  it('返回健康检查和剧情版本', async () => {
    const response = await dispatch('GET', '/api/health')
    expect(response.status).toBe(200)
    const payload = JSON.parse(response.body)
    expect(payload).toMatchObject({ status: 'ok', apiVersion: 2, stateSchemaVersion: 1 })
expect(payload.storyRevision).not.toBe('')
  })

  it('开始新游戏并完成创建、选择和读档流程', async () => {
    const started = JSON.parse((await dispatch('POST', '/api/game/start')).body)
    expect(started.state.currentNodeId).toBe('A')
    expect(started.choices.some((choice: { available: boolean }) => choice.available)).toBe(true)

    const saveResponse = await dispatch('POST', '/api/saves', {
      name: 'HTTP 回归存档',
      turnId: started.turnId,
    })
    expect(saveResponse.status).toBe(200)

    const choice = started.choices.find((choice: { available: boolean }) => choice.available)
    const advanced = JSON.parse((await dispatch('POST', '/api/game/choose', {
      nodeId: started.state.currentNodeId,
      choiceId: choice.id,
      turnId: started.turnId,
    })).body)
    expect(advanced.state.currentNodeId).not.toBe(started.state.currentNodeId)

    const saves = JSON.parse((await dispatch('GET', '/api/saves')).body)
    expect(saves.saves).toHaveLength(1)
    expect(saves.saves[0].compatible).toBe(true)

    const resumed = JSON.parse((await dispatch('POST', '/api/game/resume', {
      saveId: saves.saves[0].id,
    })).body)
    expect(resumed.state.currentNodeId).toBe(started.state.currentNodeId)
    expect(resumed.turnId).not.toBe(started.turnId)
  })

  it('拒绝无效请求和未知接口', async () => {
    const invalid = await dispatch('POST', '/api/game/resume', {})
    expect(invalid.status).toBe(400)
    expect(JSON.parse(invalid.body).error.code).toBe('VALIDATION_ERROR')

    const missing = await dispatch('GET', '/api/saves/missing-save')
    expect(missing.status).toBe(404)

    const unknown = await dispatch('GET', '/api/not-found')
    expect(unknown.status).toBe(404)
  })
})
