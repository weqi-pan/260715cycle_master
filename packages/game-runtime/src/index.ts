import type { ConditionV3, StoryChoiceV3, StoryEffectV3, StoryNodeV3, StoryProjectV3, StorySnapshotV3 } from '@cycle-master/story-schema'

export const STATE_SCHEMA_VERSION = 1

export interface ItemBrief {
  id: string
  name: string
  count?: number
  discardable: boolean
  crossSurface: boolean
}

export interface NodePersistentState {
  items: ItemBrief[]
  dangers: unknown[]
}

export interface GameState {
  currentNodeId: string
  cycleCount: number
  halfCycleCount: number
  inventory: ItemBrief[]
  flags: Record<string, boolean | number | string>
  visitedNodes: string[]
  endingsReached: string[]
  playerAttributes: Record<string, number>
  persistentNodes: Record<string, NodePersistentState>
  visitId: number
  choiceHistory: Record<string, { count: number; lastCycle: number; lastVisitId: number }>
  entryAttributes: Record<string, number>
  interactionHistory: Record<string, string[]>
  onceMarks: Record<'visit' | 'cycle' | 'session', string[]>
}

export interface ContentBlockView {
  id: string
  type: 'narration' | 'dialogue' | 'system' | 'check_result'
  text: string
  speakerId?: string
}

export interface ChoiceView {
  id: string
  text: string
  shortText?: string
  nextNodeId: string
  available: boolean
  reason?: string
  source: 'static'
}

export interface NodeView {
  id: string
  name: string
  nodeType: string
  position: number
  timeLabel?: string
  background?: string
  ambient?: string
  colorPalette?: string
  entryBlocks: ContentBlockView[]
}

export interface PersistentFoundView {
  items: ItemBrief[]
  dangers: unknown[]
}

export interface CycleEventView {
  type: 'cycle_complete'
  cycleCount: number
  halfCycleCount: number
}

export interface Frame {
  node: NodeView
  state: GameState
  choices: ChoiceView[]
  persistentFound: PersistentFoundView
  entryBlocks: ContentBlockView[]
  resultBlocks: ContentBlockView[]
  cycleEvent: CycleEventView | null
  transitionText?: string
  speakerNames: Record<string, string>
  turnId: string
  storyRevision: string
}

export class GameEngineError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'GameEngineError'
  }
}

function clone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function compare(left: number, operator: 'lt' | 'lte' | 'eq' | 'ne' | 'gte' | 'gt', right: number): boolean {
  switch (operator) {
    case 'lt': return left < right
    case 'lte': return left <= right
    case 'eq': return left === right
    case 'ne': return left !== right
    case 'gte': return left >= right
    case 'gt': return left > right
  }
}

export class ConditionEvaluator {
  check(condition: ConditionV3 | null | undefined, state: GameState): boolean {
    if (!condition) return true
    switch (condition.type) {
      case 'attribute_compare': {
        const value = state.playerAttributes[condition.attribute]
        if (value === undefined) throw new GameEngineError(`Unknown attribute: ${condition.attribute}`)
        return compare(value, condition.operator, condition.value)
      }
      case 'flag_equals': {
        const value = state.flags[condition.flag]
        return typeof value === typeof condition.value && value === condition.value
      }
      case 'item': {
        const present = state.inventory.some(item => item.id === condition.item_id && (item.count ?? 1) > 0)
        return present === (condition.present ?? true)
      }
      case 'counter_compare': {
        type CounterKey = 'completed_cycles' | 'current_cycle' | 'half_cycles'
        const counters: Record<CounterKey, number> = {
          completed_cycles: state.cycleCount,
          current_cycle: state.cycleCount + 1,
          half_cycles: state.halfCycleCount,
        }
        const counterValue = counters[condition.counter as CounterKey]
        if (counterValue === undefined) throw new GameEngineError(`Unknown counter: ${condition.counter}`)
        return compare(counterValue, condition.operator, condition.value)
      }
      case 'at_node': return state.currentNodeId === condition.node_id
      case 'all': return condition.conditions.every((item: ConditionV3) => this.check(item, state))
      case 'any': return condition.conditions.some((item: ConditionV3) => this.check(item, state))
      case 'not': return !this.check(condition.condition, state)
      default:
        throw new GameEngineError(`Unsupported v3 condition: ${String((condition as { type?: unknown }).type)}`)
    }
  }
}

function itemFromDefinition(id: string, project: StoryProjectV3, count?: number): ItemBrief {
  const definition = project.items[id]
  if (!definition) throw new GameEngineError(`Unknown item: ${id}`)
  const item: ItemBrief = {
    id,
    name: definition.display_name,
    discardable: definition.discardable,
    crossSurface: definition.cross_surface,
  }
  if (count !== undefined) item.count = count
  return item
}

export function createNewState(snapshot: StorySnapshotV3): GameState {
  return {
    currentNodeId: snapshot.project.entry_node_id,
    cycleCount: 0,
    halfCycleCount: 0,
    inventory: [],
    flags: Object.fromEntries(Object.entries(snapshot.project.flags).map(([id, def]) => [id, def.default])),
    visitedNodes: [],
    endingsReached: [],
    playerAttributes: Object.fromEntries(Object.entries(snapshot.project.attributes).map(([id, def]) => [id, def.default])),
    persistentNodes: {},
    visitId: 0,
    choiceHistory: {},
    entryAttributes: Object.fromEntries(Object.entries(snapshot.project.attributes).map(([id, def]) => [id, def.default])),
    interactionHistory: {},
    onceMarks: { visit: [], cycle: [], session: [] },
  }
}

export function normalizeState(
  snapshot: StorySnapshotV3,
  input: GameState,
  options: { clampAttributes?: boolean } = {},
): GameState {
  const clampAttributes = options.clampAttributes ?? true
  const nodeIds = new Set(Object.keys(snapshot.nodes))
  const referenced = new Set([input.currentNodeId, ...input.visitedNodes, ...Object.keys(input.persistentNodes)])
  for (const nodeId of referenced) {
    if (!nodeIds.has(nodeId)) throw new GameEngineError(`Unknown story node: ${nodeId}`)
  }
  const state = clone(input)
  state.playerAttributes = { ...state.playerAttributes }
  for (const [id, definition] of Object.entries(snapshot.project.attributes)) {
    let value = state.playerAttributes[id]
    if (value === undefined) value = definition.default
    if (clampAttributes) value = Math.min(definition.maximum, Math.max(definition.minimum, value))
    state.playerAttributes[id] = value
  }
  state.flags = { ...state.flags }
  for (const [id, definition] of Object.entries(snapshot.project.flags)) {
    if (state.flags[id] === undefined) state.flags[id] = definition.default
  }
  state.inventory = state.inventory.map(item => itemFromDefinition(item.id, snapshot.project, item.count))
  for (const [nodeId, nodeState] of Object.entries(state.persistentNodes)) {
    state.persistentNodes[nodeId] = {
      items: (nodeState?.items ?? []).map(item => itemFromDefinition(item.id, snapshot.project, item.count)),
      dangers: nodeState?.dangers ?? [],
    }
  }
  return state
}

export class EffectExecutor {
  private readonly snapshot: StorySnapshotV3
  private readonly nodeIds: Set<string>

  constructor(snapshot: StorySnapshotV3) {
    this.snapshot = snapshot
    this.nodeIds = new Set(Object.keys(snapshot.nodes))
  }

  apply(effects: StoryEffectV3[], input: GameState, nodeId: string): GameState {
    if (!this.nodeIds.has(nodeId)) throw new GameEngineError(`Unknown node: ${nodeId}`)
    const state = normalizeState(this.snapshot, input, { clampAttributes: false })
    for (const effect of effects) this.applyOne(effect, state, nodeId)
    return state
  }

  private applyOne(effect: StoryEffectV3, state: GameState, nodeId: string): void {
    switch (effect.type) {
      case 'modify_attribute': {
        const definition = this.snapshot.project.attributes[effect.attribute]
        if (!definition) throw new GameEngineError(`Unknown attribute: ${effect.attribute}`)
        const current = state.playerAttributes[effect.attribute] ?? definition.default
        let value = effect.operation === 'add' ? current + effect.value : effect.value
        if (effect.clamp) value = Math.min(definition.maximum, Math.max(definition.minimum, value))
        state.playerAttributes[effect.attribute] = value
        return
      }
      case 'set_flag': {
        const definition = this.snapshot.project.flags[effect.flag]
        if (!definition) throw new GameEngineError(`Unknown flag: ${effect.flag}`)
        if (typeof effect.value !== typeof definition.default) {
          throw new GameEngineError(`Invalid flag value type for ${effect.flag}: expected ${typeof definition.default}`)
        }
        state.flags[effect.flag] = effect.value
        return
      }
      case 'inventory': {
        const definition = this.snapshot.project.items[effect.item_id]
        if (!definition) throw new GameEngineError(`Unknown item: ${effect.item_id}`)
        const index = state.inventory.findIndex(item => item.id === effect.item_id)
        const current = index >= 0 ? state.inventory[index]?.count ?? 1 : 0
        if (effect.operation === 'remove') {
          const remaining = current - effect.quantity
          if (remaining < 0) throw new GameEngineError(`Inventory removal would go below zero: ${effect.item_id}`)
          if (remaining === 0) {
            if (index >= 0) state.inventory.splice(index, 1)
            return
          }
          if (index >= 0) state.inventory[index] = itemFromDefinition(effect.item_id, this.snapshot.project, remaining)
          return
        }
        const updated = itemFromDefinition(effect.item_id, this.snapshot.project, current + effect.quantity)
        if (index >= 0) state.inventory[index] = updated
        else state.inventory.push(updated)
        return
      }
      case 'persist_node_item': {
        if (!this.nodeIds.has(effect.node_id)) throw new GameEngineError(`Unknown node: ${effect.node_id}`)
        if (!this.snapshot.project.items[effect.item_id]) throw new GameEngineError(`Unknown item: ${effect.item_id}`)
        const nodeState = state.persistentNodes[effect.node_id] ?? { items: [], dangers: [] }
        if (!nodeState.items.some(item => item.id === effect.item_id)) {
          nodeState.items.push(itemFromDefinition(effect.item_id, this.snapshot.project))
        }
        state.persistentNodes[effect.node_id] = nodeState
        return
      }
      case 'record_interaction': {
        if (!this.snapshot.project.npcs[effect.subject_id]) throw new GameEngineError(`Unknown NPC: ${effect.subject_id}`)
        const subjects = state.interactionHistory[effect.group] ?? []
        if (!subjects.includes(effect.subject_id)) subjects.push(effect.subject_id)
        state.interactionHistory[effect.group] = subjects
        return
      }
      case 'modify_counter': {
        if (!this.snapshot.project.counters.includes(effect.counter)) {
          throw new GameEngineError(`Unknown counter: ${effect.counter}`)
        }
        const key = effect.counter === 'completed_cycles' ? 'cycleCount' : 'halfCycleCount'
        state[key] = effect.operation === 'add' ? state[key] + effect.value : effect.value
        return
      }
      case 'mark_once': {
        if (!['visit', 'cycle', 'session'].includes(effect.scope)) throw new GameEngineError(`Unknown once scope: ${effect.scope}`)
        const markScope = effect.scope as keyof GameState['onceMarks']
        const marks = state.onceMarks[markScope]
        if (!marks.includes(effect.key)) marks.push(effect.key)
        return
      }
      case 'restore_entry_attribute': {
        const definition = this.snapshot.project.attributes[effect.attribute]
        if (!definition) throw new GameEngineError(`Unknown attribute: ${effect.attribute}`)
        const entry = state.entryAttributes[effect.attribute]
        if (entry === undefined) throw new GameEngineError(`Missing entry attribute: ${effect.attribute}`)
        state.playerAttributes[effect.attribute] = Math.min(definition.maximum, Math.max(definition.minimum, entry))
        return
      }
      default: {
        const exhaustive: unknown = effect
        throw new GameEngineError(`Unsupported v3 effect: ${JSON.stringify(exhaustive)}`)
      }
    }
  }
}

function visibleBlocks(blocks: { id: string; type: 'narration' | 'dialogue' | 'system' | 'check_result'; text: string; speaker_id?: string | undefined; when?: ConditionV3 | null | undefined }[], state: GameState, evaluator: ConditionEvaluator): ContentBlockView[] {
  const result: ContentBlockView[] = []
  for (const block of blocks) {
    if (!evaluator.check(block.when, state)) continue
    const view: ContentBlockView = { id: block.id, type: block.type, text: block.text }
    if (block.type === 'dialogue' && block.speaker_id) view.speakerId = block.speaker_id
    result.push(view)
  }
  return result
}

export class GameEngine {
  private readonly evaluator = new ConditionEvaluator()

  start(snapshot: StorySnapshotV3): { state: GameState; entryBlocks: ContentBlockView[] } {
    const state = createNewState(snapshot)
    return { state, entryBlocks: this.renderEntry(snapshot, state) }
  }

  resume(snapshot: StorySnapshotV3, input: GameState): { state: GameState; entryBlocks: ContentBlockView[] } {
    const state = normalizeState(snapshot, input)
    return { state, entryBlocks: this.renderEntry(snapshot, state) }
  }

  choose(snapshot: StorySnapshotV3, input: GameState, options: { nodeId: string; choiceId: string }): {
    state: GameState
    entryBlocks: ContentBlockView[]
    resultBlocks: ContentBlockView[]
    cycleEvent: CycleEventView | null
    transitionText?: string
  } {
    if (!snapshot.nodes[options.nodeId]) throw new GameEngineError(`Node '${options.nodeId}' not found`)
    const state = normalizeState(snapshot, input, { clampAttributes: false })
    if (state.currentNodeId !== options.nodeId) {
      throw new GameEngineError(`State node mismatch: path='${options.nodeId}', state='${state.currentNodeId}'`)
    }
    const node = snapshot.nodes[options.nodeId]!
    if (node.meta.terminal) throw new GameEngineError(`Terminal node has no exits: ${node.id}`)
    const choice = node.choices.find(item => item.id === options.choiceId)
    if (!choice) throw new GameEngineError(`Choice '${options.choiceId}' not found in node '${node.id}'`)
    if (!this.evaluator.check(choice.availability.condition, state)) throw new GameEngineError(`Choice is locked: ${choice.id}`)
    if (!this.repeatAvailable(choice, state)) throw new GameEngineError(`Choice already selected under repeat policy: ${choice.id}`)
    const target = snapshot.nodes[choice.next.target]
    if (!target) throw new GameEngineError(`Target node '${choice.next.target}' not found`)
    this.validateRoute(node, target, choice, state)
    const routeEffects = this.routeEffects(node, choice)
    const crossingEffect = this.crossingEffect(node, choice, state)
    if (crossingEffect) routeEffects.push(crossingEffect)
    const previousCycle = state.cycleCount
    const updated = new EffectExecutor(snapshot).apply([...choice.effects, ...routeEffects], state, options.nodeId)
    this.recordChoice(choice, updated)
    if (!updated.visitedNodes.includes(options.nodeId)) updated.visitedNodes.push(options.nodeId)
    if (choice.next.mode !== 'stay') {
      updated.entryAttributes = { ...updated.playerAttributes }
      if (choice.next.target !== options.nodeId) updated.visitId += 1
      if (target.routing?.type === 'crossing') updated.interactionHistory[`crossing_${target.id}`] = []
    }
    updated.currentNodeId = choice.next.target
    const terminal = target.meta.terminal
    if (terminal?.type === 'cycle_complete' && updated.cycleCount === previousCycle) {
      const next = new EffectExecutor(snapshot).apply([{
        type: 'modify_counter',
        counter: 'completed_cycles',
        operation: 'add',
        value: 1,
      }], updated, target.id)
      Object.assign(updated, next)
    }
    let cycleEvent: CycleEventView | null = null
    if (updated.cycleCount > previousCycle) {
      updated.visitedNodes = []
      updated.onceMarks.cycle = []
      cycleEvent = { type: 'cycle_complete', cycleCount: updated.cycleCount, halfCycleCount: updated.halfCycleCount }
    }
    if (terminal?.type === 'ending') {
      if (!terminal.ending_id) throw new GameEngineError(`Ending terminal requires ending_id: ${target.id}`)
      if (!updated.endingsReached.includes(terminal.ending_id)) updated.endingsReached.push(terminal.ending_id)
    }
    const resultBlocks = visibleBlocks(choice.result, updated, this.evaluator)
    return {
      state: updated,
      entryBlocks: this.renderEntry(snapshot, updated),
      resultBlocks,
      cycleEvent,
    }
  }

  discard(snapshot: StorySnapshotV3, input: GameState, itemId: string): { state: GameState; entryBlocks: ContentBlockView[] } {
    const definition = snapshot.project.items[itemId]
    if (!definition) throw new GameEngineError(`Unknown item: ${itemId}`)
    if (!definition.discardable) throw new GameEngineError(`Item cannot be discarded: ${itemId}`)
    const state = normalizeState(snapshot, input, { clampAttributes: false })
    const index = state.inventory.findIndex(item => item.id === itemId)
    if (index < 0) throw new GameEngineError(`Item not in inventory: ${itemId}`)
    const item = state.inventory[index]!
    if ((item.count ?? 1) > 1) {
      state.inventory[index] = { ...item, count: (item.count ?? 1) - 1 }
      delete state.inventory[index]?.count
    } else {
      state.inventory = state.inventory.filter(entry => entry.id !== itemId)
    }
    return { state, entryBlocks: this.renderEntry(snapshot, state) }
  }

  private renderEntry(snapshot: StorySnapshotV3, state: GameState): ContentBlockView[] {
    const node = snapshot.nodes[state.currentNodeId]
    if (!node) throw new GameEngineError(`Node '${state.currentNodeId}' not found`)
    for (const sequence of node.entry_sequences) {
      if (!this.evaluator.check(sequence.when, state)) continue
      return visibleBlocks(sequence.blocks, state, this.evaluator)
    }
    return []
  }

  private repeatAvailable(choice: StoryChoiceV3, state: GameState): boolean {
    const record = state.choiceHistory[choice.id]
    if (choice.repeat_policy === 'always' || !record) return true
    if (choice.repeat_policy === 'once_per_visit') return record.lastVisitId !== state.visitId
    if (choice.repeat_policy === 'once_per_cycle') return record.lastCycle !== state.cycleCount
    if (choice.repeat_policy === 'once_ever') return false
    throw new GameEngineError(`Unknown repeat policy: ${String(choice.repeat_policy)}`)
  }

  private recordChoice(choice: StoryChoiceV3, state: GameState): void {
    const previous = state.choiceHistory[choice.id]
    state.choiceHistory[choice.id] = {
      count: (previous?.count ?? 0) + 1,
      lastCycle: state.cycleCount,
      lastVisitId: state.visitId,
    }
  }

  private validateRoute(node: StoryNodeV3, target: StoryNodeV3, choice: StoryChoiceV3, state: GameState): void {
    const routing = node.routing
    if (choice.next.mode === 'shortcut') {
      if (routing?.type !== 'shortcut') throw new GameEngineError(`Shortcut choice requires shortcut routing: ${node.id}`)
      if (!this.evaluator.check(routing.entry_condition, state)) throw new GameEngineError('Shortcut entry condition not met')
      if (choice.next.target !== routing.exit_node_id) throw new GameEngineError(`Shortcut target must be exit node: ${routing.exit_node_id}`)
    } else if (choice.next.mode === 'warp') {
      if (routing?.type !== 'warp') throw new GameEngineError(`Warp choice requires warp routing: ${node.id}`)
      if (!this.evaluator.check(routing.entry_condition, state)) throw new GameEngineError('Warp entry condition not met')
      if (!routing.allowed_targets.includes(choice.next.target)) throw new GameEngineError(`Warp target is not allowed: ${choice.next.target}`)
    }
    if (choice.next.mode === 'stay') return
    const targetRouting = target.routing
    if (targetRouting?.type === 'shortcut') {
      if (node.id !== targetRouting.entry_node_id) throw new GameEngineError(`Shortcut entry must come from: ${targetRouting.entry_node_id}`)
      if (!this.evaluator.check(targetRouting.entry_condition, state)) throw new GameEngineError('Shortcut entry condition not met')
    } else if (targetRouting?.type === 'warp') {
      if (!this.evaluator.check(targetRouting.entry_condition, state)) throw new GameEngineError('Warp entry condition not met')
    }
  }

  private routeEffects(node: StoryNodeV3, choice: StoryChoiceV3): StoryEffectV3[] {
    if (choice.next.mode === 'shortcut' && node.routing?.type === 'shortcut') return [...node.routing.counter_effects]
    if (choice.next.mode === 'warp' && node.routing?.type === 'warp') return [...node.routing.exit_effects]
    return []
  }

  private crossingEffect(node: StoryNodeV3, choice: StoryChoiceV3, state: GameState): StoryEffectV3 | null {
    const routing = node.routing
    if (routing?.type !== 'crossing') return null
    const interaction = routing.deep_interactions.find(item => item.choice_id === choice.id)
    if (!interaction) return null
    if (this.crossingLimitReached(node, choice, state)) throw new GameEngineError(`Crossing interaction limit reached: ${node.id}`)
    return { type: 'record_interaction', group: `crossing_${node.id}`, subject_id: interaction.npc_id }
  }

  private crossingLimitReached(node: StoryNodeV3, choice: StoryChoiceV3, state: GameState): boolean {
    const routing = node.routing
    if (routing?.type !== 'crossing') return false
    if (!routing.deep_interactions.some(item => item.choice_id === choice.id)) return false
    const interactions = state.interactionHistory[`crossing_${node.id}`] ?? []
    return interactions.length >= routing.max_deep_interactions
  }

  private choicesForNode(snapshot: StorySnapshotV3, node: StoryNodeV3, state: GameState): ChoiceView[] {
    if (node.meta.terminal) return []
    const choices: ChoiceView[] = []
    for (const choice of node.choices) {
      if (this.crossingLimitReached(node, choice, state)) continue
      if (!this.repeatAvailable(choice, state)) continue
      const available = this.evaluator.check(choice.availability.condition, state)
      if (!available && choice.availability.locked_visibility === 'hide') continue
      const view: ChoiceView = {
        id: choice.id,
        text: choice.text,
        nextNodeId: choice.next.target,
        available,
        source: 'static',
      }
      if (choice.short_text) view.shortText = choice.short_text
      if (!available && choice.availability.locked_reason) view.reason = choice.availability.locked_reason
      choices.push(view)
    }
    return choices
  }

  public buildFrame(snapshot: StorySnapshotV3, state: GameState, turnId: string, options: {
    resultBlocks?: ContentBlockView[]
    cycleEvent?: CycleEventView | null
    transitionText?: string
  } = {}): Frame {
    const node = snapshot.nodes[state.currentNodeId]
    if (!node) throw new GameEngineError(`Node '${state.currentNodeId}' not found`)
    const entryBlocks = this.renderEntry(snapshot, state)
    const view: NodeView = {
      id: node.id,
      name: node.meta.name,
      nodeType: node.meta.node_type,
      position: node.meta.position,
      entryBlocks,
    }
    if (node.meta.time_label) view.timeLabel = node.meta.time_label
    const background = node.scene.background_id ? snapshot.assets.assets[node.scene.background_id] : undefined
    if (background) view.background = background.path
    const ambient = node.scene.ambient_id ? snapshot.assets.assets[node.scene.ambient_id] : undefined
    if (ambient) view.ambient = ambient.path
    if (node.scene.palette) view.colorPalette = node.scene.palette
    const frame: Frame = {
      node: view,
      state,
      choices: this.choicesForNode(snapshot, node, state),
      persistentFound: {
        items: state.persistentNodes[node.id]?.items ?? [],
        dangers: state.persistentNodes[node.id]?.dangers ?? [],
      },
      entryBlocks,
      resultBlocks: options.resultBlocks ?? [],
      cycleEvent: options.cycleEvent ?? null,
      speakerNames: Object.fromEntries(Object.entries(snapshot.project.npcs).map(([id, def]) => [id, def.display_name])),
      turnId,
      storyRevision: snapshot.revision,
    }
    if (options.transitionText) frame.transitionText = options.transitionText
    return frame
  }
}
