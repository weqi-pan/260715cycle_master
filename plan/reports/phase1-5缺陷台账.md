# Cycle Master Phase 1–5 缺陷台账

> **创建日期**：2026-07-20
> **关联计划**：[Phase 1–5 残留问题修复与前端重构计划](../11_Phase1-5残留问题修复计划.md)
> **状态说明**：`已确认` 表示已有代码证据或最小复现；`待浏览器复现` 表示静态链路成立但仍需视觉/交互证据；`待设计确认` 表示需要在新契约中明确语义。

## 基线

- Git：`main`，制定计划时领先 `origin/main` 13 个提交。
- 故事数据：30 个节点、143 个选项（补齐 5 个不可达节点入口后）。
- 节点类型：8 main、20 normal、1 special_shortcut、1 special_warp。
- 选项结构：82 个同节点选择、56 个跨节点选择。
- 当前后端测试：24 个单元测试通过，但未覆盖下列核心回归场景。
- 当前前端：TypeScript 严格检查与生产构建可通过。
- 当前数据库：4 张表；故事数据库为运行时生成文件，不进入 Git。

## P0 阻断缺陷

| ID | 状态 | 缺陷 | 证据/复现 | 目标测试 |
|---|---|---|---|---|
| P0-01 | 已关闭 | A→A 调查错误完成循环 | 引擎仅允许正常回程 H→A 触发完整循环；J→A 只计半循环，K→A 不计循环；单元与实时 API 均通过 | `test_a_self_loop_does_not_complete_cycle` |
| P0-02 | 已修复待浏览器验收 | 同节点选择结果被立即清空 | 前端不再改写 Frame，统一进入 `result` 播放阶段，完成后才恢复选项 | E2E：A 调查结果完整播放 |
| P0-03 | 已修复待浏览器验收 | 跨节点选择结果与新节点正文时序错误 | 状态机固定为 result→转场→entry→dialogue→choices | E2E：A→B 顺序 |
| P0-04 | 已修复待浏览器验收 | 新节点打字机重复启动 | 删除 node watcher/双回调，唯一计时器由播放器状态机持有 | 组件测试：每 Turn 只启动一次 |
| P0-05 | 已关闭 | 读档没有应用加载状态 | 新增 `/api/game/resume`，前端 Store 原子应用加载状态；API 与单元测试通过 | E2E：保存→推进→加载 |
| P0-06 | 已关闭 | 节点遗留状态未随存档恢复 | Create/Update/Load/Delete 完整管理 `NodePersistentState`，API 往返已验证 | API 深度状态对比 |
| P0-07 | 已关闭 | `half_cycle_count` 永远不递增 | D→E 产生半循环计数并有正式回归测试 | `test_reaching_e_updates_half_cycle` |
| P0-08 | 已关闭 | 控制模板泄漏 | v2 已迁移为结构化 when；v1 兼容层也会解析 if/else、变量并清理效果标记，两条内容回归通过 | 数据严格校验 + 内容解析测试 |
| P0-09 | 已关闭 | 5 个节点静态不可达 | 按既有设计补齐 B→S3/S4、C→S5、H→S19/S20；v1/v2 均为 30/30 可达 | 图完整性测试 |
| P0-10 | 已关闭 | K 跃迁损坏 sanity_max | 改为 `modify_attr -1`，旧存档首次跃迁以当前 sanity 为基准；99 断言通过 | EffectApplier 测试 |
| P0-11 | 已关闭 | 特殊路由可绕过入口验证 | 入口/出口重新校验当前位置、条件与目标白名单 | `test_warp_entry_cannot_be_forged` |
| P0-12 | 已关闭 | 启用外键后删除含遗留状态的存档返回 500 | 删除 Save 前显式清理 NodePersistentState；单元与实时 API 删除测试通过 | `test_delete_save_removes_persistent_children_first` |
| P0-13 | 已关闭 | K 三条解锁路线被旧嵌套解析器错误合并 | 条件嵌套改为显式括号，解析器按括号深度分隔；三条路线分别解锁与反例共 4 项参数化测试通过 | `test_warp_condition_has_three_independent_routes` |

## P1 严重体验/数据缺陷

| ID | 状态 | 缺陷 | 证据/复现 |
|---|---|---|---|
| P1-01 | 已修复待浏览器验收 | NPC/主角气泡左右按索引奇偶决定 | 现按稳定 speaker 身份判断；player/主角在右，其余角色固定在左 |
| P1-02 | 部分修复 | 对话数据覆盖率不足 | v2 入场/结果块已进入运行 API，C/E 高频结果完成角色标注；其余引号文本仍需按剧情语义人工审校 |
| P1-03 | 已修复待浏览器验收 | 打字机对残缺 Markdown 反复生成 HTML | 现在按 Unicode 字符揭示单一内容块，先转义 HTML，再应用受限 Markdown；无未闭合 HTML 注入 |
| P1-04 | 已修复待浏览器验收 | 播放流程存在多个状态源 | `idle/entry/result/dialogue/choices` 成为唯一播放状态源，单一计时器可取消 |
| P1-05 | 已关闭 | 不可用选项及原因丢失 | 后端返回 visible locked choice 与原因，前端置灰并展示原因 |
| P1-06 | 已修复待浏览器验收 | 请求期间没有锁定整组选项 | `store.loading` 锁定整组选项，按钮使用 `.stop` 防止冒泡跳字 |
| P1-07 | 已关闭 | 道具添加不去重、不堆叠 | 相同道具 ID 合并 count |
| P1-08 | 已确认 | repeat/once/group 语义缺失 | 138 个 choices 中没有 once 或 choice_group 字段 |
| P1-09 | 部分修复 | 场景视觉字段未形成完整链路 | NodeData 已透传色板/背景/环境音，背景实际应用；缺少正式美术资源 |
| P1-10 | 已修复待浏览器验收 | shake/flash 没有前端消费 | notify/shake/flash 均有独立前端生命周期与动画 |
| P1-11 | 已修复待浏览器验收 | CycleMap 存在父子双开关 | 地图只保留父级开关，挂载即展开 |
| P1-12 | 已修复待浏览器验收 | 循环 toast 没有独立关闭生命周期 | 本地 3 秒 timer 自动清理，不再依赖旧 Frame 常驻 |
| P1-13 | 已关闭 | 开始界面被自动开始绕过 | 移除 mounted 自动开局，必须点击“踏入循环” |
| P1-14 | 已关闭 | Store 历史无限增长 | 历史上限 50 帧，读档/新游戏重置 |
| P1-15 | 已关闭 | API 错误反馈丢失 detail | Axios 错误优先展示后端 `detail` |

## P2 架构与维护缺陷

| ID | 状态 | 缺陷 | 证据/复现 |
|---|---|---|---|
| P2-01 | 已确认 | Phase 1 计划中的定义数据没有运行时模型 | 计划 8 张表，当前实际为 story_nodes/choices/saves/node_persistent_state 4 张 |
| P2-02 | 已确认 | Pydantic 与 TypeScript 不同步 | 后端 GameState 有 persistent_nodes，前端接口没有；前端声明 color_palette，后端 NodeData 不返回 |
| P2-03 | 已关闭 | SQLite 配置与注释不一致 | 应用连接现强制 `foreign_keys=ON`、`journal_mode=WAL`、busy timeout；运行连接实测为 1/WAL |
| P2-04 | 已关闭 | 导入脚本会删除存档 | 导入器不再删除 saves/node_persistent_state，实库导入前后存档数核对一致 |
| P2-05 | 已关闭 | 导入不是原子操作 | 节点 merge、选项重建、flush 与引用校验在单事务中执行，异常整体 rollback |
| P2-06 | 已确认 | 编辑器与 JSON 事实源脱节 | 编辑器写 SQLite，没有 JSON 导出或回写 |
| P2-07 | 已确认 | 编辑器写接口缺少严格 Schema | node/choice POST 接受裸 dict |
| P2-08 | 已确认 | 旧 E2E 依赖共享服务和真实数据库 | BASE_URL/API_BASE 固定，部分测试直接创建/修改/删除数据 |
| P2-09 | 已确认 | 旧 E2E 使用大量固定等待和 force click | `wait_for_timeout()`、`.nth()`、`force=True` 大量存在 |
| P2-10 | 已确认 | 前端播放器过度集中 | GamePlay 同时承担播放、Markdown、存档、音频、转场、面板和样式 |
| P2-11 | 已确认 | 版本和环境不一致 | 前端 package 1.0.0、后端 app 0.4.0；本机安装 FastAPI 版本与 requirements 固定版本不一致 |
| P2-12 | 待设计确认 | API 状态信任边界不清 | 客户端传回完整 GameState，后端没有绑定 save/turn 或校验 current_node_id |

## 待补充检查

- 所有 138 个选择的实际可执行性和返回选项集合。
- 30 节点内容迁移时的台词识别与角色归属。
- 道具、flag、NPC 定义 JSON 中未被代码消费的字段。
- 长文本、长选项、多个气泡在 1280×720 下的滚动与遮挡。
- API 超时、重复响应、快速点击、返回 4xx/5xx 时的 UI 恢复。
- 存档升级、旧存档兼容和损坏 JSON 的处理。
- 编辑器删除节点、创建边和修改复杂字段时的数据完整性。

## 状态变更规则

- 修复前：必须有自动化测试或可重复脚本。
- 修复中：记录关联提交和受影响契约。
- 修复后：自动化通过并完成相应人工验收，状态才改为“已关闭”。
- 发现新问题：使用同一 P0/P1/P2 编号序列追加，不覆盖既有记录。
