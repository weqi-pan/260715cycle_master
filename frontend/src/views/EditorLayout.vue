<!-- EditorLayout.vue — 三栏可视化编辑器 -->
<template>
  <div class="editor-layout">
    <!-- Left: Node list -->
    <NodeListPanel
      :nodes="nodes"
      :selected-id="selectedNodeId"
      @select="selectNode"
      @create="createNode"
      @delete="deleteNode"
    />

    <!-- Center: Graph canvas -->
    <GraphCanvas
      :nodes="nodes"
      :choices="allChoices"
      :selected-id="selectedNodeId"
      @select="selectNode"
      @connect="createEdge"
    />

    <!-- Right: Inspector -->
    <InspectorPanel
      v-if="selectedNode"
      :node="selectedNode"
      :choices="selectedChoices"
      :all-nodes="nodes"
      @update:node="saveNode"
      @update:choice="saveChoice"
      @delete:choice="deleteChoice"
    />
    <div v-else class="inspector-empty">选择一个节点以编辑属性</div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import axios from 'axios'
import NodeListPanel from '@/components/editor/NodeListPanel.vue'
import GraphCanvas from '@/components/editor/GraphCanvas.vue'
import InspectorPanel from '@/components/editor/InspectorPanel.vue'

interface NodeItem { id: string; name: string; position: number; node_type: string; time_label?: string; content: string; speaker?: string; background?: string }
interface ChoiceItem { id: string; from_node_id: string; text: string; next_node_id: string; condition?: string; effects: any[]; priority: number; hint?: string; repeat_policy: 'always'|'once_per_visit'|'once_per_cycle'|'once_ever' }

const nodes = ref<NodeItem[]>([])
const allChoices = ref<ChoiceItem[]>([])
const selectedNodeId = ref<string | null>(null)

const selectedNode = computed(() => nodes.value.find(n => n.id === selectedNodeId.value) ?? null)
const selectedChoices = computed(() => allChoices.value.filter(c => c.from_node_id === selectedNodeId.value))

onMounted(refreshAll)

async function refreshAll() {
  const [nr, cr] = await Promise.all([
    axios.get('/api/editor/nodes'),
    axios.get('/api/editor/choices/_all'),
  ])
  nodes.value = nr.data.nodes ?? []
  allChoices.value = cr.data.choices ?? []
}

function selectNode(id: string) { selectedNodeId.value = id; fetchChoices(id) }
async function fetchChoices(id: string) {
  const r = await axios.get('/api/editor/choices/' + id)
  // merge into allChoices
  const updated = r.data.choices ?? []
  allChoices.value = allChoices.value.filter(c => c.from_node_id !== id).concat(updated)
}

async function createNode() {
  const id = prompt('节点ID (如 A, B, N_001):')
  if (!id) return
  await axios.post('/api/editor/nodes', { id, name: id, position: 0, node_type: 'normal', content: '' })
  refreshAll()
}

async function deleteNode(id: string) {
  if (!confirm('删除节点 ' + id + ' 及其所有连接？')) return
  await axios.delete('/api/editor/nodes/' + id)
  if (selectedNodeId.value === id) selectedNodeId.value = null
  refreshAll()
}

async function saveNode(data: any) {
  await axios.post('/api/editor/nodes', data)
  refreshAll()
}

async function saveChoice(data: any) {
  await axios.post('/api/editor/choices', data)
  fetchChoices(data.from_node_id)
}

async function deleteChoice(id: string) {
  await axios.delete('/api/editor/choices/' + id)
  refreshAll()
}

async function createEdge(fromId: string, toId: string) {
  const cid = fromId + '_choice_' + Date.now()
  await axios.post('/api/editor/choices', {
    id: cid, from_node_id: fromId, next_node_id: toId,
    text: fromId + ' → ' + toId, effects: [], priority: 99,
  })
  fetchChoices(fromId)
}
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.editor-layout {
  display: flex; height: 100vh; overflow: hidden;
  background: $bg-void; color: $text-primary; font-family: $font-ui;
}
.inspector-empty {
  width: 280px; padding: 2rem 1rem; color: $text-dim; font-size: 0.85rem; text-align: center;
}
</style>
