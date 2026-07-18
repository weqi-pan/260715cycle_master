# Phase 6: UX 缺陷修复 — 实施方案

## 问题分析

| # | 问题 | 根因 | 优先级 |
|---|------|------|--------|
| 1 | 互斥选项缺失 | engine 不支持 choice group | 🔴 P0 |
| 2 | 过渡文本全屏覆盖 | transition overlay 阻断交互 | 🔴 P0 |
| 3 | 对话无头像框 | speaker 渲染代码被误删 | 🟡 P1 |
| 4 | 背包无法打开+道具显示ID | 缺面板UI+item.name=raw ID | 🟡 P1 |
| 5 | 点击位置无地图 | 位置标签无 click handler | 🟢 P2 |

## Fix 1: 互斥选项组

**后端**: Choice 模型新增 `choice_group` 字段（nullable string）
- 同组选项：选择其一后，engine 自动设置 `_group_{group}_chosen` flag
- 同组其他选项的 condition 中检查该 flag

**实现**: 引擎 `_apply_effects` 中检测 choice_group，自动追加 set_flag

## Fix 2: 内联叙事流

**前端**: 去掉全屏 transition overlay
- 选择后 transition_text 内联出现在选项下方（展开动画）
- 新节点内容接着出现
- 道具获取用浮动 toast 提示

## Fix 3: 对话头像框

**前端**: 恢复 speaker 渲染
- speaker 不为 null 时显示头像框+名字+对话气泡样式
- 旁白时正常叙事样式

## Fix 4: 背包面板

**后端**: add_item 时使用 ITEM_NAMES 映射中文名
**前端**: 背包按钮 → 弹出面板 → 显示道具列表 + 丢弃按钮

## Fix 5: 位置 → 地图

**前端**: 状态栏位置标签点击 → 切换 CycleMap 显示
