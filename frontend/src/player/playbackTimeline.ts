import type { ContentBlock } from '@/types'


export interface VisibleContentBlock extends ContentBlock {
  displayed_text: string
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
