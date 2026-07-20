import assert from 'node:assert/strict'
import test from 'node:test'

import {
  appendVisibleBlock,
  updateVisibleBlockText,
} from '../src/player/playbackTimeline.ts'
import type { ContentBlock } from '../src/types/index.ts'


const blocks: ContentBlock[] = [
  {
    id: 'dialogue.01',
    type: 'dialogue',
    speaker_id: 'npc_yan_yan',
    text: '你知道吗，荔湾广场那个地方——',
  },
  {
    id: 'narration.01',
    type: 'narration',
    text: '她压低声音，',
  },
  {
    id: 'dialogue.02',
    type: 'dialogue',
    speaker_id: 'npc_yan_yan',
    text: '我查过了。',
  },
]


test('visible timeline preserves dialogue-narration-dialogue order', () => {
  const timeline = blocks.reduce(appendVisibleBlock, [])

  assert.deepEqual(
    timeline.map(({ type, speaker_id, displayed_text }) => ({
      type,
      speaker_id,
      displayed_text,
    })),
    [
      { type: 'dialogue', speaker_id: 'npc_yan_yan', displayed_text: '' },
      { type: 'narration', speaker_id: undefined, displayed_text: '' },
      { type: 'dialogue', speaker_id: 'npc_yan_yan', displayed_text: '' },
    ],
  )
})


test('typing update changes only the active block and keeps history', () => {
  const initial = blocks.reduce(appendVisibleBlock, [])
  const updated = updateVisibleBlockText(initial, 'narration.01', '她压低声音，')

  assert.equal(updated[0].displayed_text, '')
  assert.equal(updated[1].displayed_text, '她压低声音，')
  assert.equal(updated[2].displayed_text, '')
  assert.notEqual(updated, initial)
  assert.equal(initial[1].displayed_text, '')
})
