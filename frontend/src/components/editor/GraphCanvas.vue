<!-- GraphCanvas.vue — Cytoscape.js 环形可视化 -->
<template>
  <div class="graph-canvas" ref="containerRef">
    <div class="toolbar">
      <span class="hint">点击节点选中 · 拖拽节点间连线创建边</span>
    </div>
    <div ref="cyRef" class="cy-container" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import cytoscape from 'cytoscape'

const props = defineProps<{ nodes: any[]; choices: any[]; selectedId: string | null }>()
const emit = defineEmits<{ select: [id: string]; connect: [from: string, to: string] }>()

const containerRef = ref<HTMLElement | null>(null)
const cyRef = ref<HTMLElement | null>(null)
let cy: cytoscape.Core | null = null

const NODE_COLORS: Record<string, string> = {
  main: '#b8943e',
  normal: '#6a5a4a',
  special_shortcut: '#8b2500',
  special_warp: '#3a4a5a',
}

const POSITIONS: Record<string, { x: number; y: number }> = {
  A: { x: 0, y: -120 }, B: { x: 85, y: -85 }, C: { x: 120, y: 0 }, D: { x: 85, y: 85 },
  E: { x: 0, y: 120 }, F: { x: -85, y: 85 }, G: { x: -120, y: 0 }, H: { x: -85, y: -85 },
}

function getPosition(id: string, index: number) {
  if (POSITIONS[id]) return POSITIONS[id]
  const angle = (index / 20) * Math.PI * 2
  return { x: Math.cos(angle) * 160, y: Math.sin(angle) * 160 }
}

function buildGraph() {
  if (!cyRef.value) return
  if (cy) cy.destroy()

  cy = cytoscape({
    container: cyRef.value,
    style: [
      { selector: 'node', style: {
        'background-color': '#4a3a2a', 'border-color': '#6a5a4a', 'border-width': 2,
        'label': 'data(id)', 'color': '#c8b896', 'font-size': '10px',
        'text-valign': 'bottom', 'text-halign': 'center', 'text-margin-y': 6,
      }},
      { selector: 'node:selected', style: { 'border-color': '#b8943e', 'border-width': 3 }},
      { selector: 'edge', style: {
        'width': 1, 'line-color': 'rgba(180,150,100,0.25)',
        'target-arrow-color': 'rgba(180,150,100,0.3)', 'target-arrow-shape': 'triangle',
        'curve-style': 'bezier',
      }},
    ],
    layout: { name: 'preset' },
  })

  // Add nodes
  props.nodes.forEach((n, i) => {
    const pos = getPosition(n.id, i)
    const color = NODE_COLORS[n.node_type] || '#6a5a4a'
    cy!.add({
      group: 'nodes', data: { id: n.id, name: n.name },
      position: pos,
      style: { 'background-color': color, 'border-color': color },
    })
  })

  // Add edges
  props.choices.forEach(c => {
    if (props.nodes.find(n => n.id === c.from_node_id) && props.nodes.find(n => n.id === c.next_node_id)) {
      cy!.add({ group: 'edges', data: { id: c.id, source: c.from_node_id, target: c.next_node_id } })
    }
  })

  // Events
  cy.on('tap', 'node', (evt) => { emit('select', evt.target.id()) })
  cy.on('tap', () => {}) // deselect on bg click

  // Drag to create edge
  let connecting = false
  cy.on('mousedown', 'node', () => { connecting = true })
  cy.on('mouseup', 'node', (evt) => {
    if (!connecting) return
    connecting = false
    const from = (evt.target as any).id()
    const to = prompt('连接到节点ID:', '')
    if (to && props.nodes.find(n => n.id === to)) emit('connect', from, to)
  })
}

onMounted(buildGraph)
watch(() => [props.nodes.length, props.choices.length], buildGraph)
watch(() => props.selectedId, (id) => {
  if (!cy) return
  cy.nodes().unselect()
  if (id) cy.getElementById(id).select()
})
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.graph-canvas {
  flex: 1; display: flex; flex-direction: column;
  background: radial-gradient(ellipse at center, rgba($accent-gold,0.03) 0%, transparent 70%);
}
.toolbar {
  padding: 0.4rem 1rem; border-bottom: 1px solid rgba($accent-gold,0.06);
}
.hint { color: $text-dim; font-size: 0.7rem; }
.cy-container { flex: 1; }
</style>
