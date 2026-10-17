# Cycle Master TypeScript 全栈重构计划

## 摘要

- 目标目录：`/home/weqi/projects/261017cycle_master`，初始化为独立 Git 仓库；不复制 `.git`、`venv`、`tmp`、构建缓存和旧存档。
- 范围：全栈 TypeScript。保留 Vue 3 产品能力，重写 Python/FastAPI 后端；允许 API、数据库结构和存档格式破坏式重构。
- 技术栈：pnpm monorepo、Node 22、TypeScript strict、Zod、better-sqlite3、Vue 3、Vite、Pinia、Vitest、Playwright。当前实现使用 Node 原生 HTTP；因环境无网络依赖，Fastify 与 Drizzle ORM 暂未引入。
- 基线：原项目保持只读作为行为参考；`data/story_v3` 与 `data/assets` 迁入新项目，剧情内容保持 Story v3 语义。
- 恢复策略：刷新页面或后端重启后，由玩家读取手动存档或开始新游戏；不自动恢复未保存进度。
- 存档兼容性：按剧情内容指纹与状态格式版本校验；剧情不匹配时保留存档并拒绝读取，还原原剧情后可再次读取。

## 项目结构

```text
261017cycle_master/
├── apps/
│   ├── server/              # Fastify + 游戏运行时 + SQLite
│   └── web/                 # Vue 3 + TypeScript 播放器
├── packages/
│   ├── api-contract/        # Zod 请求/响应/错误契约
│   ├── story-schema/        # Story v3 JSON 校验与不可变快照类型
│   └── game-runtime/        # 纯条件、效果、内容、状态、回合引擎
├── content/
│   ├── story_v3/            # 剧情创作源
│   ├── build/               # 编译后的不可变快照
│   └── assets/              # 图片、音频等资源
├── data/                    # 新版 SQLite 数据库
└── e2e/                     # Playwright TypeScript 测试
```

## 实施阶段

### 0. 固定行为基线

- 记录原项目当前工作区相关源码、剧情源的文件清单与内容哈希；存在未提交修改时，不仅记录 Git HEAD。
- 在重写前用旧实现生成固定 JSON fixtures，记录初始状态、动作序列及每一步的完整状态、可见选项、入场内容块和结果内容块。
- 覆盖完整循环、D 解锁 H、crossing 交互上限、J 捷径、K 跃迁、S20 入场属性恢复、重复选择、丢弃与存读档；同时保留条件与效果边界的合成用例。
- 对照时仅转换已约定的字段命名，排除随机 `turnId`、时间戳及新旧快照格式的 revision；保持内容块与动作顺序，不由新实现生成预期结果。
- 旧实现仅用于提取基线；新版测试直接读取 fixtures，不依赖 Python。原项目中的同名 golden journey 测试主要校验结构，不替代实际执行旅程。

### 1. 建立 TypeScript monorepo

- 初始化 pnpm workspace、根级 TypeScript、ESLint、Prettier、Vitest 配置。
- 统一 TS 配置：`strict: true`、`noUncheckedIndexedAccess: true`、`exactOptionalPropertyTypes: true`。
- 常用命令：
  - `pnpm dev`：并行启动 server 与 web，server 必须先通过严格剧情编译与快照校验，再开始监听；
  - `pnpm story:compile --strict`：严格编译剧情；
  - `pnpm test`：运行全部单元与 API 测试；
  - `pnpm build`：严格剧情编译、类型检查、后端构建、前端打包；
  - `pnpm e2e`：在临时数据库、临时剧情构建目录及独立服务实例上运行 Playwright 验收。

### 2. 定义共享契约

- 用 Zod 定义新版 HTTP API 和错误结构，server 与 web 共用 `api-contract` 包。
- 新版接口使用 camelCase，替换旧版 snake_case：
  - `GET /api/health`
  - `POST /api/game/start`：创建新游戏与初始回合；
  - `POST /api/game/resume`，body：`{ saveId }`，服务端读取并校验手动存档；
  - `POST /api/game/choose`，body：`{ nodeId, choiceId, turnId }`
  - `POST /api/game/inventory/discard`，body：`{ itemId, turnId }`
  - `GET /api/saves`
  - `POST /api/saves`，body：`{ name, turnId }`，保存服务端当前回合状态，不消耗回合；
  - `GET /api/saves/:saveId`：读取存档元数据及兼容性，不创建运行回合；
  - `PUT /api/saves/:saveId`，body：`{ turnId, name? }`，显式覆盖存档；
  - `DELETE /api/saves/:saveId`
- 统一错误响应：`{ error: { code, message, details? } }`。
- 状态码约定：参数或游戏规则错误 `400`；资源不存在 `404`；回合过期、重复消耗、节点/选项状态冲突 `409`。
- 存档拒读使用 `409 SAVE_STORY_MISMATCH`、`SAVE_STATE_VERSION_MISMATCH` 或 `SAVE_INVALID_STATE`；版本不匹配时，`details` 提供存档版本与当前版本。拒读不修改存档。
- `Frame` 包含：`turnId`、`storyRevision`、完整 `state`、`node`、分别有序的入场内容块与结果内容块、可见选项、说话人名称、节点遗留物、循环事件与转场文本。
- `GameState` 明确覆盖 `currentNodeId`、`cycleCount`、`halfCycleCount`、`inventory`、`flags`、`visitedNodes`、`endingsReached`、`playerAttributes`、`persistentNodes`、`visitId`、`choiceHistory`、`entryAttributes`、`interactionHistory`、`onceMarks`。
- choose、discard 与保存只接受服务端回合引用；resume 只接受 `saveId`，不接受客户端提交任意完整状态来重建回合。

### 3. 迁移 Story v3 编译器

- 将 `data/story_v3` 和 `data/assets` 复制到 `content/`，保留现有剧情 JSON 字段格式。
- 在 `story-schema` 中用 Zod 实现：
  - project、node、choice、condition、effect、content block、routing；
  - Story ID 校验；
  - unknown field 拒绝；
  - 交叉引用校验；
  - 不可能条件、不可达节点、非法资产路径诊断。
- 实现编译器与发布器：
  - 输入 `content/story_v3`；
  - 校验全部源 JSON；
  - 校验并补齐默认值后，对 project、assets 注册表与 nodes 的内容进行确定性规范化序列化，并生成带 SHA-256 revision 的不可变快照；
  - 通过临时文件 + rename 原子发布到 `content/build`；
  - revision 不匹配或文件损坏时启动失败。
- 提供独立 CLI：`pnpm story:compile --strict`，无错误且无警告才允许发布。
- revision 即 `storyRevision`，完全由上述规范化内容决定：对象键按固定顺序序列化，数组保留创作顺序；排除 revision 自身、构建时间、绝对路径、Git 提交号与发布批次。JSON 空白及对象键顺序不影响指纹；还原原剧情后必须得到相同指纹。
- 状态格式与解释语义的不兼容变更由独立的 `stateSchemaVersion` 管理，不用每次构建递增的版本号代替剧情指纹。
- 编译或发布失败时不切换活动快照；本次服务启动必须失败，不能回退加载残留的旧快照。首次启动应能从源文件完成编译，无需手工准备 build 目录。
- 每个运行进程固定使用启动时加载的快照；修改或还原剧情后需重新启动服务并通过严格编译，不在活动回合中热切换剧情。

### 4. 重写纯游戏引擎

- 在 `game-runtime` 中实现无 HTTP、无数据库、无文件 I/O 的引擎：
  - `ConditionEvaluator`；
  - `EffectExecutor`；
  - content block 过滤；
  - choice visibility / availability；
  - visit、cycle、session 范围的 `once` 标记；
  - shortcut、warp、crossing 路由；
  - node persistent state；
  - repeat policy；
  - `start`、`resume`、`choose`、`discardInventory`。
- 回合授权放在 server 层：
  - 单机 Demo 在单个后端进程中维护一个活动回合，绑定完整状态与 `storyRevision`；不持久化回合令牌，不提供并行游戏会话；
  - start / resume 成功后签发新 `turnId` 并作废旧活动回合；从存档恢复不复用存档时的令牌；
  - choose / discard 的校验、纯引擎执行、响应契约校验、旧回合消费与新回合发布作为同一原子操作；同一令牌并发提交最多一个成功；
  - choose / discard 失败时都保留原状态与原令牌，不发布部分效果；保存只复制并持久化已校验的当前状态，不消耗令牌；
  - 失效或重复 `turnId` 返回 `409 TURN_EXPIRED` 或 `TURN_CONFLICT`；页面刷新丢弃客户端当前回合，后端重启清空进程内回合；
  - 网络超时或连接断开可能发生在动作成功后，不能视为业务回滚。当前 Demo 不自动重试动作或恢复未保存进度，由前端提示读取手动存档或重新开始。
- 将原 Python 引擎测试中的关键语义逐条迁移到 Vitest，优先覆盖：
  - 属性、flag、道具、计数器条件；
  - 全部 effect；
  - 一次性选择与重复访问；
  - 跨循环持久状态；
  - shortcut / warp / crossing；
  - 终局节点；
  - 非法状态恢复。

### 5. 实现 Fastify 后端与 Drizzle 存储

- `apps/server` 使用 Fastify：
  - Zod request/response 校验；
  - CORS；
  - `@fastify/static` 挂载 `content/assets`；
  - 启动时严格编译并发布当前剧情源，再校验并加载与本次编译结果匹配的快照，全部成功后才监听端口；
  - 优雅关闭时释放 SQLite 连接。
- Drizzle Schema：
  - `saves`：`id`、`name`、`storyRevision`、`stateSchemaVersion`、`currentNodeId`、`cycleCount`、`stateJson`、`createdAt`、`updatedAt`；
  - `stateJson` 保存除 `persistentNodes` 外的完整 `GameState`；`currentNodeId`、`cycleCount` 列为同步写入的列表摘要，不作为独立状态来源；
  - `persistentNodes`：`saveId`、`nodeId`、`dataJson`，复合主键 `(saveId, nodeId)`，外键关联 `saves.id` 并级联删除；该表是节点持久状态的唯一存储来源；
  - SQLite 打开 WAL、foreign keys、`busy_timeout`。
- 创建或覆盖存档时，主体、摘要与节点子表在同一事务中写入；覆盖时完整替换子表，移除已不存在的节点状态；删除同样以事务完成。
- 读档顺序：读取存档 → 比较 `storyRevision` → 比较 `stateSchemaVersion` → 组装并校验完整状态 → 引擎 resume → 签发新回合；失败不得更改已有活动回合或存档。
- 存档列表始终保留不兼容存档，兼容性相对当前已加载的剧情与状态格式动态计算；不将剧情不匹配永久标记为损坏，不隐式删除、迁移或覆盖。恢复原剧情后重新判断为可读，无需恢复旧 build 目录或重建存档。
- 手动存档保存游戏状态检查点，不保存回合令牌、打字机光标、动画或一次性事件播放进度；读档重新呈现当前节点，不重执行选择效果或循环事件。
- Drizzle Kit 管理迁移；新项目默认不迁移旧 Python 存档。
- 数据库、剧情源与构建目录均可配置，并按项目目录解析绝对路径；API 测试使用临时 SQLite 文件与隔离构建目录，不污染开发数据。

### 6. 重构 Vue 3 前端

- 保留核心体验：视觉小说播放、状态栏、选项、背包、环形地图、存档读档。
- 目录整理为：
  - `apps/web/src/features/game/api.ts`；
  - `stores/gameStore.ts`；
  - `components/player/`；
  - `views/GamePlay.vue`；
  - 纯逻辑模块 `playbackTimeline.ts`、`choiceVisibility.ts`。
- 使用共享 `api-contract` 类型替换手写接口类型。
- Vite 开发代理：
  - `/api` → `http://localhost:8000`；
  - `/assets` → `http://localhost:8000`。
- 所有运行时 API 错误通过统一错误结构映射为对应的用户文案，不再依赖旧 FastAPI `detail` 结构。
- choose / discard / save 串行执行，提交期间禁用冲突操作。明确的业务失败保留当前画面；超时、连接断开或回合冲突时禁用后续选择与保存，提示读取手动存档或重新开始，不以客户端旧状态重新申请回合。
- 页面刷新后回到开始/手动读档入口，不从 localStorage、sessionStorage 或后台自动恢复未保存状态。
- 不兼容存档继续显示并说明拒读原因；剧情还原并重启后重新获取兼容性，恢复加载入口。仅显式手动覆盖或删除才会改变原存档。
- 播放顺序明确区分结果内容与入场内容：发生节点切换时先呈现结果再切场入场，stay 呈现结果后返回选项；读档只重建当前节点，取消旧播放定时器与回调。

### 7. 替换测试与验收

- 单元测试：
  - Story compiler 诊断与合法内容编译；
  - 对象键顺序和 JSON 空白不改变 revision，数组创作顺序参与指纹；剧情 A → B → A 的 revision 回到原值；
  - conditions、effects、content、routing；
  - turn store；
  - playback timeline；
  - choice visibility。
- API 集成测试：
  - start / resume / choose / discard 完整流程；
  - save / load / update / delete；
  - 重复 turnId、同一 turnId 并发 choose/discard、choose/discard 失败回滚、保存不消耗回合、新游戏或读档使旧回合失效；
  - 全量状态存读往返，特别覆盖 `visitId`、`choiceHistory`、`entryAttributes`、`interactionHistory`、`onceMarks` 与节点遗留状态；
  - 存档主体与子表中途写入失败整体回滚，覆盖删除旧子行，删除级联无残留；
  - 剧情 A 下保存 → 切到 B 并重启后拒读但保留存档 → 改回 A 并重启后成功读取原状态，全程无需重建存档或恢复旧 build；
  - 状态格式版本不匹配及非法状态拒读，拒读不改变存档或已有活动回合；
  - 非法 nodeId / choiceId / itemId；
  - 首次启动自动编译；存在合法旧快照但当前源编译失败时启动仍被阻断；快照损坏、发布或校验失败时拒绝启动。
- Golden journey：
  - 在阶段 0 记录的旧实现 fixtures 上运行 Vitest 集成测试，并随编译器与引擎实现逐步执行；
  - 对比每一步的完整状态、选项、入场/结果内容块及顺序；规范剧情保持 30 个节点、143 个选项、846 个内容块，结构计数不能替代行为对照。
- Playwright E2E：
  - 自行启动独立服务，使用临时数据库、剧情源副本、临时构建目录与独立端口，不复用开发服务器；测试结束清理临时数据与进程；
  - 默认单 worker，避免单活动回合相互覆盖；将来并行时，每个 worker 必须独立运行后端与数据目录；
  - 启动新游戏并推进到选项阶段；
  - 执行一次带状态效果的选项；
  - 存档、读档、删除存档；
  - 背包丢弃道具；
  - 刷新后从手动存档恢复，未保存进度不自动恢复；后端重启后同样可从手动存档恢复；
  - 模拟选择已在服务端成功、响应却被丢弃，验证客户端提示手动恢复，随后读档可继续且不自动重复执行动作；
  - 剧情不兼容时存档仍可见且不能加载，还原剧情并重启后可加载原档。
- 最终验收：
  - `pnpm story:compile --strict` 通过；
  - `pnpm typecheck` 通过；
  - `pnpm test` 通过；
  - `pnpm build` 通过；
  - `pnpm e2e` 通过；
  - 目标项目无 Python 源码依赖。

## 明确假设

- 旧 SQLite 存档、旧 FastAPI 请求/响应格式和旧 `data/story_build` 不作为兼容目标。
- 新版存档按剧情内容指纹及状态格式版本拒读；“拒绝旧档”针对当前不匹配，拒读本身不使存档永久失效。在状态格式仍兼容且存档未被手动覆盖或删除的前提下，改回原剧情即可正常读档。
- 持久恢复只提供手动存档；页面刷新、后端重启或动作结果不确定时，接受丢失未手动保存的进度。
- 现有剧情内容仍按 Story v3 源 JSON 迁移，不改写剧情文本和设计语义。
- 本项目仍是本地单机 Demo；不考虑多用户、云端同步或账号系统。
- AI NPC、可视化编辑器、桌面打包不进入本次重构范围。
- `261017cycle_master` 当前仅包含本计划，尚未初始化独立 Git 仓库。
