# Cycle Master — 变更日志

本项目遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 格式。
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [Unreleased]

### 新增
- 后端 Python FastAPI 应用骨架（engine / models / routers / schemas）
- 条件表达式求值器，支持 12 种条件语法
- 游戏引擎 9 步流水线（process_choice）
- K 节点跃迁枢纽特殊路由
- 前端 Vue 3 + Vite 应用骨架
- Cytoscape.js 可视化图编辑器
- 游戏播放器核心组件（TypewriterText, ChoicePanel, CycleMap 等）
- 存档系统 CRUD API
- 30 个故事节点 + 30 个选项的 JSON 数据
- 跨循环持久化系统（道具遗留/发现）
- A↔E 莫比乌斯环跨面道具共享

### 变更
- 项目结构整理：数据/文档/源码分离（2026-07-18）
  - `story_data/` → `data/story_data/`
  - `design_docs/` → `docs/design/` + `docs/story/`
  - `assets/` → `data/assets/`
  - `cycle_master.db` → `data/cycle_master.db`
  - `backend/import_story.py` → `backend/scripts/import_story.py`
  - plan/ 内部归档（implementations/ / checklists/ / reports/）
  - 所有 backend Python 模块添加中文 docstring

### 技术栈
- 前端：Vue 3.4 + TypeScript 5.5 + Vite 5.3 + Element Plus 2.7 + Pinia 2.1
- 后端：Python 3.12 + FastAPI 0.115 + SQLAlchemy 2.0 + Pydantic 2.10
- 数据库：SQLite (WAL 模式)
- 图渲染：Cytoscape.js 3.34 + 手写 SVG 小地图
- 测试：pytest (后端单测) + Playwright (E2E)

---

## [0.4.0] — 2026-07-18

### 新增
- 前端播放器全部核心组件
- 可视化编辑器（图编辑、属性面板、节点列表）
- 莫比乌斯环 SVG 小地图
- 场景特效系统（notify/shake/flash）
- 角色头像与类型机效果
- 音效挂载点

---

## [0.3.0] — 2026-07-17

### 新增
- 完整 REST API（game / saves / editor 三模块）
- 存档系统 CRUD + JSON 序列化
- 编辑器节点/选项 upsert API

---

## [0.2.0] — 2026-07-16

### 新增
- 图引擎核心（GraphBundle / GraphLoader / GameEngine）
- 条件表达式求值器（ConditionEvaluator）
- 特殊路由处理器（SpecialRouter）
- 引擎单元测试（24 用例全通过）

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

> **最后更新**：2026-07-18
