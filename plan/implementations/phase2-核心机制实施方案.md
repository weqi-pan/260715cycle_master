# Phase 2: 核心机制 — 实施方案

> **状态**: 部分完成 → 继续推进剩余 4 项
> **前置**: Phase 1 全部完成，状态持久化已完成

## 已完成（Phase 1 附带 + 刚完成）

| 任务 | 说明 |
|------|------|
| 条件表达式解析器 | 10 种类型 + `describe_condition()` |
| 特殊节点路由 (K/J) | special_router.py |
| 循环检测 | 回到 A 即 cycle_count++ |
| 状态持久化 | GameState 随请求传递，flag/道具/属性跨请求保持 |

## 剩余 4 项

### Task 1: 存档系统 (CRUD)
**文件**: `backend/app/routers/saves.py`, `frontend/src/api/saves.ts`, `frontend/src/stores/gameStore.ts`

- `POST /api/saves` — 创建存档（body: save_name + GameState）
- `GET /api/saves` — 列出所有存档
- `PUT /api/saves/{id}` — 更新存档
- `DELETE /api/saves/{id}` — 删除存档
- `GET /api/game/load/{save_id}` — 从存档恢复游戏
- 前端: 存档/读档按钮 + 简单弹窗

### Task 2: 跨循环持久化
**文件**: `backend/app/engine/engine.py`, `backend/app/models/save.py`

- 当选择包含 `leave_item` effect 时，写入 `node_persistent_state` 表
- 进入节点时检查是否有遗留道具/危险
- `cross_surface=true` 的道具在 A↔E 之间共享读取

### Task 3: 打字机逐字效果
**文件**: `frontend/src/views/GamePlay.vue`

- NarrativeText 逐字显示（可配置速度）
- 显示完毕出现 ContinueIndicator
- 点击继续 → 如果还有文本则加速显示完 → 否则进入选择模式
- 支持跳过（点击直接显示全文）

### Task 4: 莫比乌斯环形 SVG 小地图
**文件**: `frontend/src/components/player/CycleMap.vue`

- SVG 绘制环形路径，8 个主节点均匀分布
- 当前位置高亮，已访问节点标记
- E 位于 A 正下方（莫比乌斯扭转示意）
- 半透明小地图，固定在右下角
