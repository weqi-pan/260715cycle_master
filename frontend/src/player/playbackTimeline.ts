import type { ContentBlock } from '@/types'


export interface VisibleContentBlock extends ContentBlock {
  displayed_text: string
}


export function contentBlockPresentation(block: ContentBlock): ContentBlock['type'] {
  return block.type
}


export function speakerDisplayName(
  speakerId: string,
  speakerNames: Record<string, string>,
): string {
  if (['player', 'protagonist', '主角', '我'].includes(speakerId.toLowerCase())) {
    return '我'
  }
  return speakerNames[speakerId]
    ?? speakerId.replace(/^npc_/, '').replace(/_/g, ' ')
}


export function appendVisibleBlock(
  timeline: VisibleContentBlock[],
  block: ContentBlock,
): VisibleContentBlock[] {
  return [...timeline, { ...block, displayed_text: '' }]
}


export function updateVisibleBlockText(
  timeline: VisibleContentBlock[],
  blockId: string,
  displayedText: string,
): VisibleContentBlock[] {
  return timeline.map(block => (
    block.id === blockId
      ? { ...block, displayed_text: displayedText }
      : block
  ))
}
