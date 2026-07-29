# Cycle Master — 荔湾·四日轮回

> **莫比乌斯环上的每一圈，都是一次对历史的重新发现。**

一款以广州荔湾为舞台的中式恐怖视觉小说 Demo。玩家在四日循环中调查异常、收集线索与道具，并通过主角属性、持有物品和跨循环状态开启隐藏选项与路线。

## 当前状态

项目已经完成纯 Story System v3 Demo 切换：

- `data/story_v3` 是唯一剧情创作源；
- 后端启动时严格编译、发布并加载 v3 不可变快照；
- 游戏 API、回合处理、条件、效果、路线、存档和前端播放器都使用 v3；
- v2 剧情、旧图引擎、迁移链和可视化编辑器已经删除；
- 本地存档仅面向当前 Demo，旧 v2 存档不受支持；
- AI NPC 对话功能尚未开始实现。

当前 Demo 包含 30 个节点、143 个选项和 846 个内容块。

## 核心体验

- **莫比乌斯环叙事**：A~H 八个主节点、J 捷径、K 跃迁和 S1~S20 支线节点组成循环故事。
- **状态解锁**：主角属性、flags、线索与携带物品共同决定选项是否可见、可用及隐藏路线是否开放。
- **跨循环影响**：循环次数、节点遗留物、一次性行为和特殊交互范围由 v3 状态统一管理。
- **服务端回合授权**：每次选择使用一次性 `turn_id`，重复提交不会重复执行效果。
- **视觉小说播放器**：按创作顺序呈现旁白、对话、系统提示与检定结果，并支持存档、背包和环形地图。

## 技术栈

| 层 | 技术 |
|---|---|
| 前端 | Vue 3、TypeScript、Vite、Pinia、Element Plus、SCSS |
| 后端 | Python 3.12、FastAPI、Pydantic v2、SQLAlchemy 2.0 |
| 数据 | Story System v3 JSON、不可变编译快照、SQLite 存档 |
| 测试 | pytest、Vitest/Node Test、Playwright |

## 项目结构

```text
cycle_master/
├── backend/
│   ├── app/
│   │   ├── engine/                  # v3 条件、效果、内容、路由与回合执行
│   │   ├── story/                   # v3 编译器、诊断和快照发布
│   │   ├── routers/                 # game / saves API
│   │   ├── schemas/                 # v3 剧情与游戏状态契约
│   │   └── models/                  # 存档与节点持久状态
│   ├── scripts/
│   │   ├── compile_story_v3.py      # 严格编译与发布
│   │   └── export_story_v3_schema.py
│   └── tests/                       # 后端测试
├── frontend/
│   ├── src/
│   │   ├── components/player/       # 状态栏和循环地图
│   │   ├── player/                  # 内容时间线与选项展示
│   │   ├── stores/                  # v3 回合与存档状态
│   │   └── views/GamePlay.vue       # 视觉小说播放器
│   └── tests/                       # 前端单元测试
├── data/
│   ├── story_v3/                    # 唯一剧情创作源
│   ├── story_build/                 # 后端生成的不可变运行快照
│   ├── assets/                      # 背景、立绘和音频资源
│   └── cycle_master.db              # 本地 Demo 存档
├── tests/e2e/                       # 核心玩家旅程
├── docs/                            # 设计、故事、规格与计划归档
└── plan/reports/                    # 项目交接报告
```

## 本地运行

安装后端依赖：

```powershell
python -m pip install -r backend/requirements.txt
python -m pip install -r backend/requirements-dev.txt
```

启动后端：

```powershell
python -m uvicorn backend.app.main:app --reload --port 8000
```

后端启动会编译 `data/story_v3`，将通过校验的快照发布到 `data/story_build`，随后仅从该 v3 快照提供游戏内容。存在编译错误或警告时，严格启动门禁会阻止错误内容进入运行时。

启动前端：

```powershell
Set-Location frontend
npm install
npm run dev
```

浏览器访问 `http://localhost:5173/play`，点击“踏入循环”开始游戏。

## 剧情编译与验证

严格编译到隔离目录：

```powershell
python -m backend.scripts.compile_story_v3 --strict --build-root tmp/pure-v3-check
```

完整验证：

```powershell
python -m pytest backend/tests -q
python -m backend.scripts.compile_story_v3 --strict --build-root tmp/pure-v3-final

Set-Location frontend
npm.cmd run test:unit
npm.cmd run build
Set-Location ..

python -m pytest tests/e2e/test_phase2_checklist.py tests/e2e/test_phase2_final.py tests/e2e/test_phase5_immersion.py -q
```

E2E 需要本地后端运行在 `localhost:8000`、前端运行在 `localhost:5173`。测试后端应通过 `CYCLE_MASTER_DATABASE_PATH` 使用隔离数据库，避免写入日常 Demo 存档。

## 内容编辑方式

当前没有可视化编辑器。剧情内容直接维护在 `data/story_v3`：

1. 修改项目注册表或节点 JSON；
2. 运行严格编译；
3. 运行相关后端测试和核心玩家 E2E；
4. 只有无错误、无警告的快照才可作为运行内容。

如未来确实需要编辑器，应围绕 v3 Schema 和不可变快照重新设计，不恢复旧编辑器。

## Demo 边界

- 当前回合授权保存在后端进程内；后端重启后，未保存的当前回合需要重新开始或读档。
- SQLite 存档适合本地单机 Demo，不提供生产级账号、并发会话或跨设备同步。
- 旧 v2 存档和旧内容迁移工具已经移除，不提供兼容或回退路径。
- 桌面打包、完整资源门禁、前端拆包优化仍属于后续发布工作。
- AI NPC 尚未实现；未来接入时应以 v3 状态、NPC 白名单和剧情权限为边界。

## 许可证

待定。

## 作者

- 游戏设计与剧本：weqi
- 技术架构：weqi

> **最后更新**：2026-07-29
