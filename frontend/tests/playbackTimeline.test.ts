import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

import {
  appendVisibleBlock,
  updateVisibleBlockText,
} from '../src/player/playbackTimeline.ts'
import { visibleChoices } from '../src/player/choiceVisibility.ts'
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

test('choice list preserves server-authored visible locked choices', () => {
  const choices = [
    { id: 'open', text: '可选', next_node_id: 'A', available: true, source: 'static' as const },
    { id: 'locked', text: '不可选', next_node_id: 'A', available: false, source: 'static' as const },
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

test('gameplay renders visible locked choices as disabled with their reason', () => {
  const source = readFileSync(
    new URL('../src/views/GamePlay.vue', import.meta.url),
    'utf8',
  )

  assert.match(source, /:disabled="store\.loading \|\| !c\.available \|\| chosenIds\.has\(c\.id\)"/)
  assert.match(source, /v-if="!c\.available && c\.reason" class="choice-reason"/)
})
