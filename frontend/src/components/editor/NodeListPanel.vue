<!-- NodeListPanel.vue — 左侧节点列表 -->
<template>
  <div class="node-list">
    <div class="panel-header">
      <h3>节点列表 ({{ filtered.length }})</h3>
      <button @click="$emit('create')" class="add-btn">+ 新建</button>
    </div>
    <div class="filter-row">
      <select v-model="filter" class="filter-select">
        <option value="">全部类型</option>
        <option value="main">主节点</option>
        <option value="normal">子节点</option>
        <option value="special_shortcut">捷径 (J)</option>
        <option value="special_warp">跃迁 (K)</option>
      </select>
    </div>
    <div class="node-items">
      <div
        v-for="n in filtered" :key="n.id"
        class="node-item"
        :class="{ active: n.id === selectedId }"
        @click="$emit('select', n.id)"
      >
        <span class="node-tag" :class="'tag-' + n.node_type">{{ n.id }}</span>
        <span class="node-name">{{ n.name }}</span>
        <button class="del-btn" @click.stop="$emit('delete', n.id)" title="删除">×</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

const props = defineProps<{ nodes: any[]; selectedId: string | null }>()
defineEmits<{ select: [id: string]; create: []; delete: [id: string] }>()

const filter = ref('')
const filtered = computed(() => {
  if (!filter.value) return props.nodes
  return props.nodes.filter(n => n.node_type === filter.value)
})
</script>

<style scoped lang="scss">
@use '@/assets/styles/variables.scss' as *;

.node-list {
  width: 220px; flex-shrink: 0;
  border-right: 1px solid rgba($accent-gold, 0.1);
  display: flex; flex-direction: column;
  background: rgba(0,0,0,0.3);
}

.panel-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 0.6rem 0.8rem; border-bottom: 1px solid rgba($accent-gold, 0.08);
  h3 { font-size: 0.85rem; color: $accent-gold; font-weight: 500; }
}

.add-btn {
  background: transparent; border: 1px solid rgba($accent-gold, 0.3); color: $accent-gold;
  padding: 0.15rem 0.5rem; border-radius: 3px; cursor: pointer; font-size: 0.75rem;
  &:hover { background: rgba($accent-gold, 0.1); }
}

.filter-row { padding: 0.4rem 0.8rem; }
.filter-select {
  width: 100%; padding: 0.25rem; background: rgba(0,0,0,0.5); border: 1px solid rgba($accent-gold, 0.15);
  color: $text-secondary; font-size: 0.75rem; font-family: $font-ui;
}

.node-items { flex: 1; overflow-y: auto; }
.node-item {
  display: flex; align-items: center; gap: 0.4rem;
  padding: 0.4rem 0.8rem; cursor: pointer; font-size: 0.8rem;
  border-bottom: 1px solid rgba($accent-gold, 0.03);
  &:hover { background: rgba($accent-gold, 0.05); }
  &.active { background: rgba($accent-gold, 0.1); border-left: 2px solid $accent-gold; }
}

.node-tag {
  font-size: 0.65rem; padding: 0.05rem 0.3rem; border-radius: 2px; font-weight: 600; flex-shrink: 0;
  &.tag-main { background: rgba($accent-gold, 0.2); color: $accent-gold; }
  &.tag-normal { background: rgba($text-dim, 0.2); color: $text-dim; }
  &.tag-special_shortcut { background: rgba($accent-red, 0.15); color: $accent-red; }
  &.tag-special_warp { background: rgba($accent-ghost, 0.2); color: $accent-ghost; }
}

.node-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: $text-secondary; }
.del-btn { background: none; border: none; color: rgba($accent-red, 0.4); cursor: pointer; font-size: 1rem; padding: 0 0.2rem;
  &:hover { color: $accent-red; }
}
</style>
