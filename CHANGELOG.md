# Cycle Master — 变更日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 格式。
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### 新增
- Story System v3 权威运行仓库：启动时严格编译、发布并加载不可变快照
- v3 类型化条件求值、原子效果执行、内容选择、重复策略和特殊路线
- 服务端一次性 `turn_id` 回合授权与重放防护
- v3 存档状态校验、恢复和物品元数据补全
- 统一内容时间线，按顺序渲染旁白、对话、系统提示和检定结果
- 纯 v3 边界测试及核心玩家 Playwright E2E

### 变更
- `data/story_v3` 成为唯一剧情源，游戏 API 和前端播放器只消费 v3 快照
- 锁定选项按 `locked_visibility=hide/show` 显示，并由服务端提供可用状态
- `always / once_per_visit / once_per_cycle / once_ever` 四种重复策略统一由 v3 执行
- travel、shortcut、warp、完整循环、E 深度互动限制和 S20 恢复规则切换到 v3
- 选择和丢弃失败时保持原回合状态，不产生部分效果
- README、路线图和 E2E 更新为纯 v3 Demo 契约

### 修复
- K 跃迁出口重复与统一代价问题
- H 隐藏路线的实际解锁路径
- E 节点每次访问的深度互动上限
- S20 每轮仅恢复一次及失败选择原子性
- 网络请求失败时保留当前前端画面

### 移除
- 全部旧剧情数据、Schema、加载器、图引擎和迁移工具
- 后端与前端可视化编辑器及相关 API、组件和测试
- 旧故事数据库模型和重复的物品/NPC 注册表
- 旧存档兼容与回退路径

---

## [0.7.0] — 2026-07-20

### 新增
- dialogue_lines 数组对话系统，替代纯文本 narrative
- 聊天气泡式对话渲染
- 对话分镜支持（speaker / content / emotion / backdrop）
- 场景转场动画系统：
  - 水墨扩散（ink-wash）
  - 时痕裂隙（time-rift）
  - 标题卡（title-card）
- 转场数组化配置（`transitions` 替代内联分段）

### 修复
- 转场颜色可见性修复（黑色背景下的色调适配）
- 转场 clip-path circle 渲染竞态修复
- 转场持久化：节点切换前快照 await 前状态，完成后重置
- 节点切换时清除旧转场

---

## [0.6.0] — 2026-07-19

### 新增
- 内联展开叙事流（inline expand），支持节点内分段内容推送
- 场景特效系统标记剥离（前端过滤 `[notify]`/`[shake]`/`[flash]` 标记渲染效果）
- 顶部导航按钮（场景过渡动画控制）
- 播放器动画系统（scene transition animations）

### 变更
- 简化内联流：移除 segment 系统，统一使用 transitions 数组
- UX 打磨：道具名称/描述正确显示、选项分组优化

### 修复
- 道具名称正确显示
- 选项分组可见性控制
- 背包系统展示修复
- 小地图切换状态修复
- `import_story.py` 绝对导入兼容独立执行

---

## [0.5.0] — 2026-07-19

### 新增
- 音效挂载点支持
- 角色 speaker 数据迁移
- 场景色彩氛围（color tint）
- E2E 端到端测试框架（Playwright）
- Playwright E2E 测试用例

---

## [0.4.0] — 2026-07-18

### 新增
- 前端播放器全部核心组件（TypewriterText, ChoicePanel, CycleMap 等）
- 可视化编辑器（图编辑、属性面板、节点列表）
- 莫比乌斯环 SVG 小地图（环形进度条 + 扭转示意）
- 场景特效系统（notify/shake/flash）
- 角色头像与打字机效果
- 音效挂载点

### 变更
- 项目结构系统性整理（数据/文档/源码分离）
  - `story_data/` → `data/story_data/`
  - `design_docs/` → `docs/design/` + `docs/story/`
  - `assets/` → `data/assets/`
  - `cycle_master.db` → `data/cycle_master.db`
  - `backend/import_story.py` → `backend/scripts/import_story.py`
  - plan/ 内部归档（implementations/ / checklists/ / reports/）
  - 所有 backend Python 模块添加中文 docstring 与注释
- Health check：移除死代码、清理未使用 import

---

## [0.3.0] — 2026-07-17

### 新增
- 完整 REST API（game / saves / editor 三模块）
- 存档系统 CRUD + JSON 序列化
- 编辑器节点/选项 upsert API
- v2 剧情数据架构设计（story_node_v2 JSON Schema）

---

## [0.2.0] — 2026-07-16

### 新增
- 图引擎核心（GraphBundle / GraphLoader / GameEngine）
- 条件表达式求值器（ConditionEvaluator，12 种条件语法）
- 特殊路由处理器（SpecialRouter）
- K 节点跃迁枢纽
- 引擎单元测试（全部通过）

---

## [0.1.0] — 2026-07-16

### 新增
- 项目骨架搭建
- SQLAlchemy ORM 模型（StoryNode, Choice, Save, NodePersistentState）
- Pydantic Schema 定义
- story_data JSON 导入脚本
- 30 节点 + 30 选项 JSON 数据
- 设计文档（技术方案 / 故事方案 / 故事地图 / 道具系统）

---

### 技术栈

- 前端：Vue 3.4 + TypeScript 5.5 + Vite 5.3 + Element Plus 2.7 + Pinia 2.1
- 后端：Python 3.12 + FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic 2.10
- 数据库：SQLite (WAL 模式)
- 图渲染：Cytoscape.js 3.34 + 手写 SVG 小地图
- 测试：pytest（后端单测）+ Playwright（E2E）+ Vitest（前端单测）

---

> **最后更新**：2026-07-21
