import { describe, expect, it } from 'vitest'
import { blocksToPlayback, speakerDisplayName } from '../apps/web/src/lib/playbackTimeline'
import { orderedChoices } from '../apps/web/src/lib/choiceVisibility'
import type { ChoiceView, ContentBlockView } from '../packages/api-contract/src/index'

describe('播放逻辑', () => {
  it('keeps authored block order for playback', () => {
    const blocks: ContentBlockView[] = [
      { id: 'r1', type: 'check_result', text: '结果' },
      { id: 'e1', type: 'narration', text: '入场' },
    ]
    expect(blocksToPlayback(blocks).map(block => block.id)).toEqual(['r1', 'e1'])
  })

  it('uses author display names and falls back cleanly', () => {
    expect(speakerDisplayName('npc_h', { npc_h: 'H' })).toBe('H')
    expect(speakerDisplayName('unknown', {})).toBe('unknown')
  })
})

describe('选项展示', () => {
  it('sorts available choices ahead of locked choices', () => {
    const choices: ChoiceView[] = [
      { id: 'locked', text: '锁定', nextNodeId: 'B', available: false, reason: '条件不足', source: 'static' },
      { id: 'open', text: '开放', nextNodeId: 'C', available: true, source: 'static' },
    ]
    expect(orderedChoices(choices).map(choice => choice.id)).toEqual(['open', 'locked'])
  })
})
