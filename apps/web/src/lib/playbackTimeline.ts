import type { ContentBlockView } from '@cycle-master/api-contract'

export interface VisibleContentBlock extends ContentBlockView {
  displayedText: string
}

export function speakerDisplayName(speakerId: string, speakerNames: Record<string, string>): string {
  const lower = speakerId.toLowerCase()
  if (['player', 'protagonist', '我'].includes(lower)) return '我'
  return speakerNames[speakerId] ?? speakerId.replace(/^npc_/, '').replace(/_/g, ' ')
}

export function appendVisibleBlock(timeline: VisibleContentBlock[], block: ContentBlockView): VisibleContentBlock[] {
  return [...timeline, { ...block, displayedText: '' }]
}

export function updateVisibleBlockText(timeline: VisibleContentBlock[], blockId: string, text: string): VisibleContentBlock[] {
  return timeline.map(block => block.id === blockId ? { ...block, displayedText: text } : block)
}

export function blocksToPlayback(blocks: readonly ContentBlockView[]): VisibleContentBlock[] {
  return blocks.map(block => ({ ...block, displayedText: '' }))
}
