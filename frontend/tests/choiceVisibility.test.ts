import assert from 'node:assert/strict'
import test from 'node:test'

import { visibleChoices } from '../src/player/choiceVisibility.ts'


test('choice list preserves server-authored visible locked choices', () => {
  const choices = [
    { id: 'open', text: 'Open', next_node_id: 'A', available: true },
    {
      id: 'locked',
      text: 'Locked',
      next_node_id: 'A',
      available: false,
      reason: 'A key is required.',
    },
  ]

  assert.deepEqual(visibleChoices(choices).map(choice => choice.id), ['open', 'locked'])
})


test('choice list drops malformed response entries defensively', () => {
  const choices = [
    { id: 'open', text: 'Open', next_node_id: 'A', available: true },
    { id: '', text: 'Malformed', next_node_id: 'A', available: true },
  ]

  assert.deepEqual(visibleChoices(choices).map(choice => choice.id), ['open'])
})


test('a rejected request keeps the exact current frame object', async () => {
  const requestModule = await import('../src/player/frameRequest.ts').catch(() => ({}))
  const resolveFrameRequest = (
    requestModule as {
      resolveFrameRequest?: <T>(currentFrame: T, request: () => Promise<T>) => Promise<{
        frame: T
        error: unknown
      }>
    }
  ).resolveFrameRequest
  const currentFrame = { turn_id: 'turn-1', node: { id: 'A' } }
  const failure = new Error('network failed')

  assert.equal(typeof resolveFrameRequest, 'function')
  const outcome = await resolveFrameRequest?.(
    currentFrame,
    async () => Promise.reject(failure),
  )
  assert.equal(outcome?.frame, currentFrame)
  assert.equal(outcome?.error, failure)
})


test('a successful request exposes the replacement frame', async () => {
  const requestModule = await import('../src/player/frameRequest.ts').catch(() => ({}))
  const resolveFrameRequest = (
    requestModule as {
      resolveFrameRequest?: <T>(currentFrame: T, request: () => Promise<T>) => Promise<{
        frame: T
        error: unknown
      }>
    }
  ).resolveFrameRequest
  const currentFrame = { turn_id: 'turn-1', node: { id: 'A' } }
  const nextFrame = { turn_id: 'turn-2', node: { id: 'B' } }

  assert.equal(typeof resolveFrameRequest, 'function')
  const outcome = await resolveFrameRequest?.(currentFrame, async () => nextFrame)
  assert.equal(outcome?.frame, nextFrame)
  assert.equal(outcome?.error, null)
})
