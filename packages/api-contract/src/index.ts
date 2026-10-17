import { z } from 'zod'

export const API_VERSION = 2
export const STATE_SCHEMA_VERSION = 1

export const ContentBlockViewSchema = z.object({
  id: z.string(),
  type: z.enum(['narration', 'dialogue', 'system', 'check_result']),
  text: z.string(),
  speakerId: z.string().optional(),
})

export const ItemBriefSchema = z.object({
  id: z.string(),
  name: z.string(),
  count: z.number().int().min(1).optional(),
  discardable: z.boolean(),
  crossSurface: z.boolean(),
})

export const NodePersistentStateSchema = z.object({
  items: z.array(ItemBriefSchema),
  dangers: z.array(z.unknown()),
})

export const GameStateSchema = z.object({
  currentNodeId: z.string(),
  cycleCount: z.number().int().min(0),
  halfCycleCount: z.number().int().min(0),
  inventory: z.array(ItemBriefSchema),
  flags: z.record(z.string(), z.union([z.boolean(), z.number(), z.string()])),
  visitedNodes: z.array(z.string()),
  endingsReached: z.array(z.string()),
  playerAttributes: z.record(z.string(), z.number()),
  persistentNodes: z.record(z.string(), NodePersistentStateSchema),
  visitId: z.number().int().min(0),
  choiceHistory: z.record(z.string(), z.object({
    count: z.number().int().min(0),
    lastCycle: z.number().int().min(0),
    lastVisitId: z.number().int().min(0),
  })),
  entryAttributes: z.record(z.string(), z.number()),
  interactionHistory: z.record(z.string(), z.array(z.string())),
  onceMarks: z.object({
    visit: z.array(z.string()),
    cycle: z.array(z.string()),
    session: z.array(z.string()),
  }),
})

export const ChoiceViewSchema = z.object({
  id: z.string(),
  text: z.string(),
  shortText: z.string().optional(),
  nextNodeId: z.string(),
  available: z.boolean(),
  reason: z.string().optional(),
  source: z.literal('static'),
})

export const NodeViewSchema = z.object({
  id: z.string(),
  name: z.string(),
  nodeType: z.string(),
  position: z.number(),
  timeLabel: z.string().optional(),
  background: z.string().optional(),
  ambient: z.string().optional(),
  colorPalette: z.string().optional(),
  entryBlocks: z.array(ContentBlockViewSchema),
})

export const CycleEventViewSchema = z.object({
  type: z.literal('cycle_complete'),
  cycleCount: z.number().int().min(0),
  halfCycleCount: z.number().int().min(0),
})

export const FrameSchema = z.object({
  turnId: z.string(),
  storyRevision: z.string(),
  state: GameStateSchema,
  node: NodeViewSchema,
  choices: z.array(ChoiceViewSchema),
  persistentFound: z.object({
    items: z.array(ItemBriefSchema),
    dangers: z.array(z.unknown()),
  }),
  entryBlocks: z.array(ContentBlockViewSchema),
  resultBlocks: z.array(ContentBlockViewSchema),
  cycleEvent: CycleEventViewSchema.nullable(),
  transitionText: z.string().optional(),
  speakerNames: z.record(z.string(), z.string()),
})

export const StartResponseSchema = FrameSchema
export const ResumeRequestSchema = z.object({ saveId: z.string().min(1) }).strict()
export const ChooseRequestSchema = z.object({
  nodeId: z.string().min(1),
  choiceId: z.string().min(1),
  turnId: z.string().min(1),
}).strict()
export const DiscardRequestSchema = z.object({
  itemId: z.string().min(1),
  turnId: z.string().min(1),
}).strict()
export const SaveCreateRequestSchema = z.object({
  name: z.string().min(1).max(120),
  turnId: z.string().min(1),
}).strict()
export const SaveUpdateRequestSchema = z.object({
  turnId: z.string().min(1),
  name: z.string().min(1).max(120).optional(),
}).strict()
export const SaveSummarySchema = z.object({
  id: z.string(),
  name: z.string(),
  storyRevision: z.string(),
  stateSchemaVersion: z.number().int(),
  currentNodeId: z.string(),
  cycleCount: z.number().int().min(0),
  compatible: z.boolean(),
  incompatibleReason: z.string().optional(),
  createdAt: z.string(),
  updatedAt: z.string(),
})
export const SaveMetadataSchema = SaveSummarySchema
export const SaveListResponseSchema = z.object({ saves: z.array(SaveSummarySchema) })
export const SaveMutationResponseSchema = z.object({ status: z.literal('ok') })
export const HealthResponseSchema = z.object({
  status: z.literal('ok'),
  apiVersion: z.number().int(),
  storyRevision: z.string(),
  stateSchemaVersion: z.number().int(),
})

export type ContentBlockView = z.infer<typeof ContentBlockViewSchema>
export type ItemBrief = z.infer<typeof ItemBriefSchema>
export type GameState = z.infer<typeof GameStateSchema>
export type ChoiceView = z.infer<typeof ChoiceViewSchema>
export type NodeView = z.infer<typeof NodeViewSchema>
export type CycleEventView = z.infer<typeof CycleEventViewSchema>
export type Frame = z.infer<typeof FrameSchema>
export type ResumeRequest = z.infer<typeof ResumeRequestSchema>
export type ChooseRequest = z.infer<typeof ChooseRequestSchema>
export type DiscardRequest = z.infer<typeof DiscardRequestSchema>
export type SaveCreateRequest = z.infer<typeof SaveCreateRequestSchema>
export type SaveUpdateRequest = z.infer<typeof SaveUpdateRequestSchema>
export type SaveSummary = z.infer<typeof SaveSummarySchema>
export type SaveMetadata = z.infer<typeof SaveMetadataSchema>
export type HealthResponse = z.infer<typeof HealthResponseSchema>

export type ApiErrorCode =
  | 'VALIDATION_ERROR'
  | 'GAME_RULE_ERROR'
  | 'NOT_FOUND'
  | 'TURN_STALE'
  | 'SAVE_STORY_MISMATCH'
  | 'SAVE_STATE_VERSION_MISMATCH'
  | 'SAVE_INVALID_STATE'
  | 'INTERNAL_ERROR'

export interface ApiError {
  error: {
    code: ApiErrorCode
    message: string
    details?: unknown
  }
}
