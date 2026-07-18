<!-- InspectorPanel.vue — 右侧属性编辑 -->
<template>
  <div class="inspector">
    <h3>属性编辑</h3>

    <!-- Node fields -->
    <div class="section">
      <h4>节点: {{ node.id }}</h4>
      <label>名称 <input v-model="form.name" @change="emitNode" /></label>
      <label>类型
        <select v-model="form.node_type" @change="emitNode">
          <option value="main">主节点</option>
          <option value="normal">子节点</option>
          <option value="special_shortcut">捷径 (J)</option>
          <option value="special_warp">跃迁 (K)</option>
        </select>
      </label>
      <label>位置 <input v-model.number="form.position" type="number" @change="emitNode" /></label>
      <label>时间标签 <input v-model="form.time_label" @change="emitNode" /></label>
      <label>说话人 <input v-model="form.speaker" @change="emitNode" placeholder="null = 旁白" /></label>
      <label>背景图 <input v-model="form.background" @change="emitNode" /></label>
      <label>正文 <textarea v-model="form.content" rows="6" @change="emitNode" /></label>
    </div>

    <!-- Choices -->
    <div class="section">
      <h4>选项 ({{ choices.length }})</h4>
      <button class="add-btn" @click="addChoice">+ 添加选项</button>
      <div v-for="c in localChoices" :key="c.id" class="choice-card">
        <div class="choice-header">
          <span class="choice-id">{{ c.id }}</span>
          <button class="del-btn" @click="$emit('delete:choice', c.id)">×</button>
        </div>
        <label>文本 <input v-model="c.text" @change="emitChoice(c)" /></label>
        <label>目标节点 <input v-model="c.next_node_id" @change="emitChoice(c)" list="node-list" /></label>
        <datalist id="node-list">
          <option v-for="n in allNodes" :key="n.id" :value="n.id">{{ n.name }}</option>
        </datalist>
        <label>条件 <input v-model="c.condition" @change="emitChoice(c)" placeholder="null = 始终可选" /></label>
        <label>优先级 <input v-model.number="c.priority" type="number" @change="emitChoice(c)" /></label>
        <label>提示 <input v-model="c.hint" @change="emitChoice(c)" /></label>
        <label class="cb-label"><input type="checkbox" v-model="c.is_hidden_when_locked" @change="emitChoice(c)" /> 不可用时隐藏</label>
        <label>过渡文本 <textarea v-model="c.transition_text" rows="3" @change="emitChoice(c)" /></label>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

const props = defineProps<{ node: any; choices: any[]; allNodes: any[] }>()
const emit = defineEmits<{ 'update:node': [data: any]; 'update:choice': [data: any]; 'delete:choice': [id: string] }>()

const form = ref({ ...props.node })
const localChoices = ref<any[]>(JSON.parse(JSON.stringify(props.choices)))

watch(() => props.node, (n) => { form.value = { ...n } }, { deep: true })
watch(() => props.choices, (c) => { localChoices.value = JSON.parse(JSON.stringify(c)) }, { deep: true })

function emitNode() { emit('update:node', { ...form.value }) }
function emitChoice(c: any) { emit('update:choice', { ...c }) }

function addChoice() {
  const c = {
    id: props.node.id + '_choice_' + Date.now(),
    from_node_id: props.node.id, text: '新选项', next_node_id: props.node.id,
    condition: null, effects: [], priority: 99, hint: null, is_hidden_when_locked: false,
  }
  localChoices.value.push(c)
  emitChoice(c)
}
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.inspector {
  width: 300px; flex-shrink: 0; overflow-y: auto;
  border-left: 1px solid rgba($accent-gold, 0.1); background: rgba(0,0,0,0.3);
  padding: 0.8rem;
  h3 { font-size: 0.9rem; color: $accent-gold; margin-bottom: 0.8rem; }
}
.section { margin-bottom: 1rem; }
h4 { font-size: 0.8rem; color: $text-secondary; margin-bottom: 0.4rem; }
label { display: block; font-size: 0.75rem; color: $text-dim; margin-bottom: 0.3rem; }
input, select, textarea {
  width: 100%; padding: 0.25rem 0.4rem; margin-top: 0.1rem;
  background: rgba(0,0,0,0.4); border: 1px solid rgba($accent-gold,0.12);
  color: $text-primary; font-family: $font-ui; font-size: 0.78rem;
  &:focus { outline: none; border-color: $accent-gold; }
}
textarea { resize: vertical; }
.add-btn {
  background: transparent; border: 1px solid rgba($accent-gold,0.2); color: $accent-gold;
  padding: 0.2rem 0.6rem; border-radius: 3px; cursor: pointer; font-size: 0.75rem; margin-bottom: 0.5rem;
  &:hover { background: rgba($accent-gold,0.08); }
}
.choice-card {
  border: 1px solid rgba($accent-gold,0.08); padding: 0.5rem; margin-bottom: 0.4rem; border-radius: 4px;
}
.choice-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.3rem; }
.choice-id { font-size: 0.7rem; color: $accent-gold; }
.del-btn { background: none; border: none; color: rgba($accent-red,0.5); cursor: pointer; font-size: 1rem;
  &:hover { color: $accent-red; }
}
.cb-label { display: flex; align-items: center; gap: 0.3rem;
  input { width: auto; }
}
</style>
