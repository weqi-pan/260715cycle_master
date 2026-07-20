export interface GameState {
  current_node_id: string
  cycle_count: number
  half_cycle_count: number
  inventory: ItemBrief[]
  flags: Record<string, any>
  visited_nodes: string[]
  endings_reached: string[]
  player_attributes: Record<string, number>
}

export interface ItemBrief {
  id: string
  name: string
  count?: number
}

export interface NodeData {
  id: string
  name: string
  node_type: string
  position: number
  time_label?: string
  content: string
  speaker?: string
  speaker_avatar?: string
  background?: string
  ambient?: string
  color_palette?: string
  dialogue_lines?: Array<{ speaker: string; text: string }>
}

export interface ChoiceResult {
  id: string
  text: string
  short_text?: string
  next_node_id?: string
  available: boolean
  reason?: string
  source: 'static' | 'special_shortcut' | 'special_warp'
}

export interface PersistentFound {
  items: ItemBrief[]
  cross_surface_items: ItemBrief[]
  dangers: any[]
}

export interface CycleEvent {
  type: string
  cycle_count: number
  half_cycle_count: number
}

export interface Frame {
  node: NodeData
  state: GameState
  available_choices: ChoiceResult[]
  persistent_found: PersistentFound
  cycle_event: CycleEvent | null
  transition_text?: string
  scene_effects?: Array<{ type: string; target?: string; value?: any }>
}
