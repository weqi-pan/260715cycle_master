import assert from 'node:assert/strict'
import test from 'node:test'

import * as playback from '../src/player/playbackTimeline.ts'
import type { ContentBlock } from '../src/types/index.ts'


const blocks: ContentBlock[] = [
  {
    id: 'dialogue.01',
    type: 'dialogue',
    speaker_id: 'npc_yan_yan',
    text: 'Do you know that place?',
  },
  {
    id: 'narration.01',
    type: 'narration',
    text: 'She lowers her voice.',
  },
  {
    id: 'check.01',
    type: 'check_result',
    text: 'Insight check succeeded.',
  },
  {
    id: 'system.01',
    type: 'system',
    text: 'A memory was recorded.',
  },
]


test('visible timeline preserves authored v3 block order', () => {
  const timeline = blocks.reduce(playback.appendVisibleBlock, [])

  assert.deepEqual(
    timeline.map(({ id, type, displayed_text }) => ({ id, type, displayed_text })),
    blocks.map(({ id, type }) => ({ id, type, displayed_text: '' })),
  )
})


test('typing update changes only the active block and keeps history', () => {
  const initial = blocks.reduce(playback.appendVisibleBlock, [])
  const updated = playback.updateVisibleBlockText(
    initial,
    'check.01',
    'Insight check succeeded.',
  )

  assert.equal(updated[0].displayed_text, '')
  assert.equal(updated[2].displayed_text, 'Insight check succeeded.')
  assert.equal(updated[3].displayed_text, '')
  assert.notEqual(updated, initial)
  assert.equal(initial[2].displayed_text, '')
})


test('check results have a deterministic dedicated presentation', () => {
  const presentation = (
    playback as typeof playback & {
      contentBlockPresentation?: (block: ContentBlock) => string
    }
  ).contentBlockPresentation

  assert.equal(typeof presentation, 'function')
  assert.equal(presentation?.(blocks[0]), 'dialogue')
  assert.equal(presentation?.(blocks[1]), 'narration')
  assert.equal(presentation?.(blocks[2]), 'check_result')
  assert.equal(presentation?.(blocks[3]), 'system')
})


test('dialogue speaker IDs resolve through frame speaker names', () => {
  const speakerDisplayName = (
    playback as typeof playback & {
      speakerDisplayName?: (
        speakerId: string,
        speakerNames: Record<string, string>,
      ) => string
    }
  ).speakerDisplayName

  assert.equal(typeof speakerDisplayName, 'function')
  assert.equal(
    speakerDisplayName?.('npc_yan_yan', { npc_yan_yan: 'Yan Yan' }),
    'Yan Yan',
  )
})
