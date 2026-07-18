# Phase 3: 可视化编辑器 — 实施方案

## 架构

```
/editor 路由
  └── EditorLayout.vue (三栏布局)
        ├── NodeListPanel.vue    (左 20%)  节点列表 + 筛选 + 拖拽排序
        ├── GraphCanvas.vue      (中 55%)  Cytoscape.js 环形图
        └── InspectorPanel.vue   (右 25%)  属性编辑面板
```

## Tasks

### Task 1: 后端 Editor API (CRUD)
- `GET /api/editor/nodes` — 所有节点
- `POST /api/editor/nodes` — 创建或更新节点
- `DELETE /api/editor/nodes/{id}` — 删除节点（级联删除 choices）
- `GET /api/editor/choices/{node_id}` — 获取节点的 choices
- `POST /api/editor/choices` — 创建或更新 choice

### Task 2: 前端编辑器组件
- `EditorLayout.vue` — 三栏 flex 布局
- `NodeListPanel.vue` — 节点列表，按类型筛选
- `GraphCanvas.vue` — Cytoscape.js 环形可视化
- `InspectorPanel.vue` — 选中节点/边的属性编辑器

### Task 3: 测试清单
- 编辑器 UI 渲染、节点选择、属性编辑、保存验证
