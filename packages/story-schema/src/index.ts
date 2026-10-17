import { createHash } from 'node:crypto'
import { readFile, readdir, rename, writeFile } from 'node:fs/promises'
import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { z } from 'zod'

const STORY_ID_RE = /^[A-Za-z][A-Za-z0-9_-]{0,63}$/
export type DiagnosticSeverity = 'error' | 'warning' | 'info'

export interface StoryDiagnostic {
  code: string
  severity: DiagnosticSeverity
  message: string
  location: string
}

export class StoryCompileError extends Error {
  readonly diagnostics: StoryDiagnostic[]
  constructor(diagnostics: StoryDiagnostic[]) {
    const errorCount = diagnostics.filter(d => d.severity === 'error').length
    super(`story compilation failed with ${errorCount} error(s)`)
    this.name = 'StoryCompileError'
    this.diagnostics = diagnostics
  }
}

function diagnostic(code: string, severity: DiagnosticSeverity, message: string, location: string): StoryDiagnostic {
  return { code, severity, message, location }
}

function storyId(value: string, kind = 'story'): string {
  if (!STORY_ID_RE.test(value)) {
    throw new Error(`invalid story id for ${kind}: ${JSON.stringify(value)}`)
  }
  return value
}

const StoryId = z.string().refine(value => {
  try { storyId(value); return true } catch { return false }
}, 'invalid story id')

const CompareOperator = z.enum(['lt', 'lte', 'eq', 'ne', 'gte', 'gt'])

const ConditionSchema: z.ZodType<any> = z.lazy(() => z.discriminatedUnion('type', [
  z.object({ type: z.literal('attribute_compare'), attribute: StoryId, operator: CompareOperator, value: z.number().int() }).strict(),
  z.object({ type: z.literal('flag_equals'), flag: StoryId, value: z.union([z.boolean(), z.number().int(), z.string()]) }).strict(),
  z.object({ type: z.literal('item'), item_id: StoryId, present: z.boolean().default(true) }).strict(),
  z.object({ type: z.literal('counter_compare'), counter: z.enum(['completed_cycles', 'current_cycle', 'half_cycles']), operator: CompareOperator, value: z.number().int().min(0) }).strict(),
  z.object({ type: z.literal('at_node'), node_id: StoryId }).strict(),
  z.object({ type: z.literal('all'), conditions: z.array(ConditionSchema).min(1) }).strict(),
  z.object({ type: z.literal('any'), conditions: z.array(ConditionSchema).min(1) }).strict(),
  z.object({ type: z.literal('not'), condition: ConditionSchema }).strict(),
]))


const EffectSchema: z.ZodType<any> = z.lazy(() => z.discriminatedUnion('type', [
  z.object({ type: z.literal('modify_attribute'), attribute: StoryId, operation: z.enum(['add', 'set']), value: z.number().int(), clamp: z.boolean().default(true) }).strict(),
  z.object({ type: z.literal('set_flag'), flag: StoryId, value: z.union([z.boolean(), z.number().int(), z.string()]) }).strict(),
  z.object({ type: z.literal('inventory'), item_id: StoryId, operation: z.enum(['add', 'remove']), quantity: z.number().int().min(1).default(1) }).strict(),
  z.object({ type: z.literal('persist_node_item'), node_id: StoryId, item_id: StoryId }).strict(),
  z.object({ type: z.literal('record_interaction'), group: StoryId, subject_id: StoryId }).strict(),
  z.object({ type: z.literal('modify_counter'), counter: z.enum(['completed_cycles', 'half_cycles']), operation: z.enum(['add', 'set']), value: z.number().int() }).strict(),
  z.object({ type: z.literal('mark_once'), key: StoryId, scope: z.enum(['visit', 'cycle', 'session']) }).strict(),
  z.object({ type: z.literal('restore_entry_attribute'), attribute: StoryId }).strict(),
]))


const ContentBlock = z.discriminatedUnion('type', [
  z.object({ id: StoryId, type: z.literal('narration'), text: z.string(), when: ConditionSchema.nullish() }).strict(),
  z.object({ id: StoryId, type: z.literal('dialogue'), speaker_id: StoryId, text: z.string(), when: ConditionSchema.nullish() }).strict(),
  z.object({ id: StoryId, type: z.literal('system'), text: z.string(), when: ConditionSchema.nullish() }).strict(),
  z.object({ id: StoryId, type: z.literal('check_result'), text: z.string(), when: ConditionSchema.nullish() }).strict(),
])

const EntrySequence = z.object({
  id: StoryId,
  when: ConditionSchema.nullish(),
  blocks: z.array(ContentBlock).min(1),
}).strict()

const Choice = z.object({
  id: StoryId,
  text: z.string(),
  short_text: z.string().nullish(),
  availability: z.object({
    condition: ConditionSchema.nullish(),
    locked_visibility: z.enum(['show', 'hide']).default('show'),
    locked_reason: z.string().nullish(),
  }).strict(),
  repeat_policy: z.enum(['always', 'once_per_visit', 'once_per_cycle', 'once_ever']).default('once_per_visit'),
  hint: z.string().nullish(),
  result: z.array(ContentBlock).default([]),
  effects: z.array(EffectSchema).default([]),
  next: z.object({ target: StoryId, mode: z.enum(['stay', 'travel', 'shortcut', 'warp']) }).strict(),
}).strict()

const Routing = z.discriminatedUnion('type', [
  z.object({
    type: z.literal('crossing'),
    trigger_time: z.string(),
    target_era: StoryId,
    max_deep_interactions: z.number().int().min(1),
    deep_interactions: z.array(z.object({ choice_id: StoryId, npc_id: StoryId }).strict()).min(1),
    duration_note: z.string().nullish(),
    return_note: z.string().nullish(),
  }).strict(),
  z.object({
    type: z.literal('shortcut'),
    entry_condition: ConditionSchema,
    entry_node_id: StoryId,
    exit_node_id: StoryId,
    counter_effects: z.array(EffectSchema).default([]),
  }).strict(),
  z.object({
    type: z.literal('warp'),
    entry_condition: ConditionSchema,
    allowed_targets: z.array(StoryId).min(1),
    exit_effects: z.array(EffectSchema).min(1),
    sacrifice_target: StoryId.nullish(),
  }).strict(),
])

const Scene = z.object({
  background_id: StoryId.nullish(),
  allow_no_background: z.boolean(),
  ambient_id: StoryId.nullish(),
  palette: z.string().nullish(),
  atmosphere: z.array(z.string()).default([]),
}).strict()

const Terminal = z.object({
  type: z.enum(['ending', 'cycle_complete']),
  ending_id: StoryId.nullish(),
}).strict()

const NodeMeta = z.object({
  name: z.string(),
  node_type: z.enum(['main', 'normal', 'special_shortcut', 'special_warp']),
  position: z.number(),
  time_label: z.string().nullish(),
  parent_node_id: StoryId.nullish(),
  terminal: Terminal.nullish(),
}).strict()

const Authoring = z.object({
  trigger_description: z.string().nullish(),
  npcs_present: z.array(StoryId).default([]),
  scene_items: z.array(z.object({ item_id: StoryId, location: z.string(), acquisition_note: z.string().nullish() }).strict()).default([]),
  npc_item_notes: z.array(z.object({ npc_id: StoryId, item_id: StoryId, required_flag: StoryId.nullish() }).strict()).default([]),
  sensory: z.string().nullish(),
  gender_variant: z.object({ male: z.string(), female: z.string() }).strict().nullish(),
  notes: z.array(z.string()).default([]),
}).strict()

const StoryNode = z.object({
  schema_version: z.literal(3),
  id: StoryId,
  meta: NodeMeta,
  scene: Scene,
  entry_sequences: z.array(EntrySequence).min(1),
  choices: z.array(Choice).default([]),
  routing: Routing.nullish(),
  authoring: Authoring.default({ npcs_present: [], scene_items: [], npc_item_notes: [], notes: [] }),
}).strict()

const Project = z.object({
  schema_version: z.literal(3),
  entry_node_id: StoryId,
  attributes: z.record(StoryId, z.object({
    display_name: z.string(),
    default: z.number().int(),
    minimum: z.number().int(),
    maximum: z.number().int(),
  }).strict()),
  flags: z.record(StoryId, z.object({
    display_name: z.string(),
    default: z.union([z.boolean(), z.number().int(), z.string()]),
  }).strict()),
  items: z.record(StoryId, z.object({
    display_name: z.string(),
    discardable: z.boolean().default(false),
    cross_surface: z.boolean().default(false),
  }).strict()),
  npcs: z.record(StoryId, z.object({ display_name: z.string() }).strict()),
  counters: z.array(z.enum(['completed_cycles', 'half_cycles'])),
  jump_modes: z.array(z.enum(['stay', 'travel', 'shortcut', 'warp'])),
}).strict()

const AssetCatalog = z.object({
  schema_version: z.literal(3),
  assets: z.record(StoryId, z.object({
    kind: z.enum(['background', 'audio', 'sprite']),
    path: z.string(),
  }).strict()),
}).strict()

export type StoryProjectV3 = z.infer<typeof Project>
export type StoryAssetCatalogV3 = z.infer<typeof AssetCatalog>
export type StoryNodeV3 = z.infer<typeof StoryNode>
export type ConditionV3 = any
export type StoryEffectV3 = any
export type ContentBlockV3 = z.infer<typeof ContentBlock>
export type StoryChoiceV3 = z.infer<typeof Choice>


export interface StorySnapshotV3 {
  schema_version: 3
  revision: string
  project: StoryProjectV3
  assets: StoryAssetCatalogV3
  nodes: Record<string, StoryNodeV3>
}

export interface StoryCompilation {
  snapshot: StorySnapshotV3 | null
  diagnostics: StoryDiagnostic[]
}

function sortedObject(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(item => sortedObject(item))
  if (value === null || typeof value !== 'object') return value
  const result: Record<string, unknown> = {}
  for (const key of Object.keys(value).sort()) {
    result[key] = sortedObject((value as Record<string, unknown>)[key])
  }
  return result
}

export function canonicalJsonBytes(value: unknown): Buffer {
  return Buffer.from(JSON.stringify(sortedObject(value)), 'utf8')
}

export function snapshotRevisionWithoutRevision(snapshot: Omit<StorySnapshotV3, 'revision'>): string {
  return createHash('sha256').update(canonicalJsonBytes(snapshot)).digest('hex')
}

function buildSnapshot(project: StoryProjectV3, assets: StoryAssetCatalogV3, nodes: Record<string, StoryNodeV3>): StorySnapshotV3 {
  const base = { schema_version: 3 as const, project, assets, nodes }
  return { ...base, revision: snapshotRevisionWithoutRevision(base) }
}

function hasErrors(diagnostics: StoryDiagnostic[]): boolean {
  return diagnostics.some(item => item.severity === 'error')
}

async function readJson(file: string): Promise<{ value?: unknown; error?: string }> {
  try {
    return { value: JSON.parse(await readFile(file, 'utf8')) }
  } catch (error) {
    return { error: error instanceof Error ? error.message : String(error) }
  }
}

function zodDiagnostics(file: string, error: z.ZodError): StoryDiagnostic[] {
  return error.issues.map(issue => diagnostic(
    'STORY_SCHEMA_INVALID',
    'error',
    `${issue.path.join('.')}: ${issue.message}`,
    file,
  ))
}

function visitConditions(condition: ConditionV3 | null | undefined, visit: (condition: ConditionV3) => void): void {
  if (!condition) return
  visit(condition)
  if (condition.type === 'all' || condition.type === 'any') {
    condition.conditions.forEach((item: ConditionV3) => visitConditions(item, visit))
  }
  if (condition.type === 'not') visitConditions(condition.condition, visit)
}

function iterateEffects(node: StoryNodeV3, visit: (effect: StoryEffectV3) => void): void {
  const visitBlocks = (blocks: ContentBlockV3[]): void => {
    blocks.forEach((block: ContentBlockV3) => visitConditions(block.when, current => {
      if (current.type === 'item' && !Object.hasOwn(node, 'item')) return
    }))
  }
  node.entry_sequences.forEach(sequence => {
    visitConditions(sequence.when, () => undefined)
    visitBlocks(sequence.blocks)
  })
  node.choices.forEach(choice => {
    visitConditions(choice.availability.condition, () => undefined)
    visitBlocks(choice.result)
    choice.effects.forEach(visit)
  })
  const routing = node.routing
  if (routing?.type === 'shortcut') routing.counter_effects.forEach(visit)
  if (routing?.type === 'warp') routing.exit_effects.forEach(visit)
}

export class StoryCompiler {
  compile(sourceRoot: string): StoryCompilation {
    const root = path.resolve(sourceRoot)
    const diagnostics: StoryDiagnostic[] = []
    const loaded = this.load(root, diagnostics)
    if (hasErrors(diagnostics) || !loaded) return { snapshot: null, diagnostics }
    diagnostics.push(...this.validate(loaded))
    if (hasErrors(diagnostics)) return { snapshot: null, diagnostics }
    return { snapshot: buildSnapshot(loaded.project, loaded.assets, loaded.nodes), diagnostics }
  }

  private load(root: string, diagnostics: StoryDiagnostic[]): { project: StoryProjectV3; assets: StoryAssetCatalogV3; nodes: Record<string, StoryNodeV3> } | null {
    let project: StoryProjectV3 | undefined
    let assets: StoryAssetCatalogV3 | undefined
    const nodes: Record<string, StoryNodeV3> = {}
    void (async () => undefined)()
    // Synchronous reads keep the compile API simple and deterministic.
    const read = (file: string): unknown => {
      const text = readFileSync(file, 'utf8')
      return JSON.parse(text)
    }
    try {
      project = Project.parse(read(path.join(root, 'project.json')))
    } catch (error) {
      if (error instanceof z.ZodError) diagnostics.push(...zodDiagnostics('project.json', error))
      else diagnostics.push(diagnostic('STORY_SOURCE_READ_FAILED', 'error', String(error), 'project.json'))
    }
    try {
      assets = AssetCatalog.parse(read(path.join(root, 'assets.json')))
    } catch (error) {
      if (error instanceof z.ZodError) diagnostics.push(...zodDiagnostics('assets.json', error))
      else diagnostics.push(diagnostic('STORY_SOURCE_READ_FAILED', 'error', String(error), 'assets.json'))
    }
    const nodesRoot = path.join(root, 'nodes')
    try {
      const files = readdirSync(nodesRoot).filter((name: string) => name.endsWith('.json')).sort()
      if (!files.length) diagnostics.push(diagnostic('STORY_SOURCE_MISSING', 'error', 'No node source files were found.', 'nodes'))
      for (const name of files) {
        const location = `nodes/${name}`
        try { const parsed = StoryNode.parse(read(path.join(nodesRoot, name))); nodes[parsed.id] = parsed }
        catch (error) {
          if (error instanceof z.ZodError) diagnostics.push(...zodDiagnostics(location, error))
          else diagnostics.push(diagnostic('STORY_SOURCE_READ_FAILED', 'error', String(error), location))
        }
      }
    } catch (error) {
      diagnostics.push(diagnostic('STORY_SOURCE_MISSING', 'error', String(error), 'nodes'))
    }
    if (!project || !assets || hasErrors(diagnostics)) return null
    return { project, assets, nodes }
  }

  private validate(story: { project: StoryProjectV3; assets: StoryAssetCatalogV3; nodes: Record<string, StoryNodeV3> }): StoryDiagnostic[] {
    const results: StoryDiagnostic[] = []
    const nodeIds = new Set(Object.keys(story.nodes))
    if (!nodeIds.has(story.project.entry_node_id)) {
      results.push(diagnostic('STORY_ENTRY_MISSING', 'error', `Entry node '${story.project.entry_node_id}' not found`, 'project.json'))
    }
    const unsafeAssetPath = (value: string): boolean => /(^|[\\/])\.\.($|[\\/])/.test(value) || /^[a-zA-Z]:[\\/]/.test(value) || value.includes('\0')
    for (const [id, asset] of Object.entries(story.assets.assets)) {
      if (unsafeAssetPath(asset.path)) results.push(diagnostic('STORY_ASSET_UNSAFE_PATH', 'error', `Unsafe asset path: ${asset.path}`, `assets/${id}`))
    }
    for (const node of Object.values(story.nodes)) {
      const location = `nodes/${node.id}`
      const blockIds = new Set<string>()
      for (const sequence of node.entry_sequences) {
        for (const block of sequence.blocks) {
          if (blockIds.has(block.id)) results.push(diagnostic('STORY_BLOCK_ID_DUPLICATE', 'error', `Duplicate content block '${block.id}'`, location))
          blockIds.add(block.id)
        }
      }
      const choiceIds = new Set<string>()
      for (const choice of node.choices) {
        if (choiceIds.has(choice.id)) results.push(diagnostic('STORY_CHOICE_ID_DUPLICATE', 'error', `Duplicate choice '${choice.id}'`, location))
        choiceIds.add(choice.id)
        if (choice.next.mode === 'stay' && choice.next.target !== node.id) results.push(diagnostic('STORY_STAY_TARGET_INVALID', 'error', 'stay choice must target its owning node', location))
        if (!nodeIds.has(choice.next.target)) results.push(diagnostic('STORY_TARGET_MISSING', 'error', `Target node '${choice.next.target}' not found`, location))
        for (const block of choice.result) {
          if (blockIds.has(block.id)) results.push(diagnostic('STORY_BLOCK_ID_DUPLICATE', 'error', `Duplicate content block '${block.id}'`, location))
          blockIds.add(block.id)
        }
      }
      const check = (condition: ConditionV3 | null | undefined, scope: string): void => {
        visitConditions(condition, current => {
          if (current.type === 'attribute_compare' && !Object.hasOwn(story.project.attributes, current.attribute)) results.push(diagnostic('STORY_ATTRIBUTE_MISSING', 'error', `Unknown attribute '${current.attribute}'`, scope))
          if (current.type === 'flag_equals' && !Object.hasOwn(story.project.flags, current.flag)) results.push(diagnostic('STORY_FLAG_MISSING', 'error', `Unknown flag '${current.flag}'`, scope))
          if (current.type === 'item' && !Object.hasOwn(story.project.items, current.item_id)) results.push(diagnostic('STORY_ITEM_MISSING', 'error', `Unknown item '${current.item_id}'`, scope))
          if (current.type === 'at_node' && !nodeIds.has(current.node_id)) results.push(diagnostic('STORY_NODE_MISSING', 'error', `Unknown node '${current.node_id}'`, scope))
        })
      }
      for (const sequence of node.entry_sequences) {
        check(sequence.when, `${location}/entry_sequences/${sequence.id}`)
        for (const block of sequence.blocks) check(block.when, `${location}/blocks/${block.id}`)
      }
      for (const choice of node.choices) {
        check(choice.availability.condition, `${location}/choices/${choice.id}`)
        for (const block of choice.result) check(block.when, `${location}/result/${block.id}`)
        iterateEffects(node, effect => {
          if (effect.type === 'modify_attribute' && !Object.hasOwn(story.project.attributes, effect.attribute)) results.push(diagnostic('STORY_ATTRIBUTE_MISSING', 'error', `Unknown attribute '${effect.attribute}'`, location))
          if (effect.type === 'set_flag' && !Object.hasOwn(story.project.flags, effect.flag)) results.push(diagnostic('STORY_FLAG_MISSING', 'error', `Unknown flag '${effect.flag}'`, location))
          if (effect.type === 'inventory' && !Object.hasOwn(story.project.items, effect.item_id)) results.push(diagnostic('STORY_ITEM_MISSING', 'error', `Unknown item '${effect.item_id}'`, location))
          if (effect.type === 'persist_node_item') {
            if (!nodeIds.has(effect.node_id)) results.push(diagnostic('STORY_NODE_MISSING', 'error', `Unknown node '${effect.node_id}'`, location))
            if (!Object.hasOwn(story.project.items, effect.item_id)) results.push(diagnostic('STORY_ITEM_MISSING', 'error', `Unknown item '${effect.item_id}'`, location))
          }
          if (effect.type === 'record_interaction' && !Object.hasOwn(story.project.npcs, effect.subject_id)) results.push(diagnostic('STORY_NPC_MISSING', 'error', `Unknown NPC '${effect.subject_id}'`, location))
          if (effect.type === 'restore_entry_attribute' && !Object.hasOwn(story.project.attributes, effect.attribute)) results.push(diagnostic('STORY_ATTRIBUTE_MISSING', 'error', `Unknown attribute '${effect.attribute}'`, location))
        })
      }
      const routing = node.routing
      if (routing?.type === 'shortcut') {
        check(routing.entry_condition, `${location}/routing`)
        if (!nodeIds.has(routing.entry_node_id) || !nodeIds.has(routing.exit_node_id)) results.push(diagnostic('STORY_ROUTING_TARGET_INVALID', 'error', 'Shortcut routing references missing node', location))
      }
      if (routing?.type === 'warp') {
        check(routing.entry_condition, `${location}/routing`)
        if (routing.allowed_targets.some(id => !nodeIds.has(id))) results.push(diagnostic('STORY_ROUTING_TARGET_INVALID', 'error', 'Warp routing references missing target', location))
      }
    }
    return results
  }
}

export class StoryPublisher {
  readonly buildRoot: string
  constructor(buildRoot: string) {
    this.buildRoot = buildRoot
  }

  async publish(snapshot: StorySnapshotV3): Promise<void> {
    await (await import('node:fs/promises')).mkdir(this.buildRoot, { recursive: true })
    const target = path.join(this.buildRoot, 'current.json')
    const temporary = path.join(this.buildRoot, `.current-${process.pid}-${Date.now()}.tmp`)
    await writeFile(temporary, JSON.stringify(snapshot, null, 2), 'utf8')
    await rename(temporary, target)
  }

  async loadActive(): Promise<StorySnapshotV3> {
    const file = path.join(this.buildRoot, 'current.json')
    const text = await readFile(file, 'utf8')
    const payload = JSON.parse(text) as unknown as StorySnapshotV3
    const { revision, ...rest } = payload
    if (revision !== snapshotRevisionWithoutRevision(rest)) throw new StoryCompileError([{ code: 'STORY_SNAPSHOT_CORRUPT', severity: 'error', message: 'Story snapshot revision does not match its content.', location: 'current.json' }])
    return payload as StorySnapshotV3
  }
}

export async function loadOrCompileStory(sourceRoot: string, buildRoot: string, strict = true): Promise<StorySnapshotV3> {
  const compilation = new StoryCompiler().compile(sourceRoot)
  if (strict && compilation.diagnostics.some(item => item.severity !== 'info')) throw new StoryCompileError(compilation.diagnostics)
  if (!compilation.snapshot) throw new StoryCompileError(compilation.diagnostics)
  await new StoryPublisher(buildRoot).publish(compilation.snapshot)
  return compilation.snapshot
}

export async function listStoryFiles(sourceRoot: string): Promise<string[]> {
  const nodesRoot = path.join(sourceRoot, 'nodes')
  const names = await readdir(nodesRoot)
  return ['project.json', 'assets.json', ...names.filter(name => name.endsWith('.json')).map(name => `nodes/${name}`)]
}
