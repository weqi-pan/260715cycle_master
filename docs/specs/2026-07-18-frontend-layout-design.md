# 前端布局重构 — 设计文档

> **状态**: 已确认
> **关联**: [技术实现方案](../技术实现方案.md) | [故事内容格式规范](../故事内容格式规范.md)

---

## 一、设计目标

将当前"纯文本滚动 + 底部选项栏"重构为可扩展的五层叠加布局，支持未来添加背景插图、人物立绘、头像框等视觉元素。采用**文字冒险风格**——背景图做氛围衬底，半透明对话框覆盖底部，文本为主角。

### 参考风格

《探灵直播》式的文字冒险：背景图压暗 + 半透明遮罩文本区，氛围感强，文字清晰。

---

## 二、五层叠加模型

```
┌──────────────────────────────────────┐
│  z-100  StatusBar (半透明顶栏)        │  循环计数 / 属性 / 背包
├──────────────────────────────────────┤
│                                      │
│  z-10   人物立绘区 (预留 slot)        │  左/中/右定位，Phase 1 不渲染
│                                      │
│  z-0    背景图层                     │  全屏背景 + 暗角呼吸动画
│                                      │
├──────────────────────────────────────┤
│  z-20   对话框 (底部 35-40%)          │  半透明暗色渐变遮罩
│         ┌────────────────────────┐   │
│         │ [头像] 名字             │   │  说话人时有头像+名字，旁白时无
│         │ 文本内容...             │   │  叙事时打字机逐字，选择时截断
│         │ [[ 选项 1 ]]           │   │  选项从下方滑入
│         │ [[ 选项 2 ]]           │   │
│         └────────────────────────┘   │
└──────────────────────────────────────┘
```

---

## 三、组件树（重构后）

```
GamePlay.vue                          ← 主容器
├── BackgroundLayer.vue               ← z-0: 背景图 + 暗角 + 切换动画
├── CharacterLayer.vue                ← z-10: 立绘区 (slot 预留)
│   └── CharacterSprite.vue           ← 单个立绘 (左/中/右定位)
├── DialogBox.vue                     ← z-20: 底部对话框
│   ├── SpeakerHeader.vue             ← 头像框 + 名字
│   ├── NarrativeText.vue             ← 文本 (打字机逐字)
│   ├── ChoicePanel.vue               ← 选项列表
│   │   └── ChoiceButton.vue          ← 单个选项按钮
│   └── ContinueIndicator.vue         ← "▼ 点击继续"
└── StatusBar.vue                     ← z-100: 顶部状态栏 (不变)
```

### 组件职责

| 组件 | 职责 | 输入 |
|------|------|------|
| `BackgroundLayer` | 渲染背景图，淡入淡出切换 | `node.background` |
| `CharacterLayer` | 管理立绘 slot 布局，Phase 1 为空 | (未来) `node.speaker` → 立绘路径 |
| `CharacterSprite` | 单个立绘，入场/退场动画 | 立绘路径 + 位置 |
| `DialogBox` | 对话区容器，半透明遮罩，管理模式切换 | 模式状态 |
| `SpeakerHeader` | 有说话人显示头像+名字，旁白隐藏 | `node.speaker`, `node.speaker_avatar` |
| `NarrativeText` | 渲染文本，打字机逐字，完成后触发回调 | `node.content` |
| `ChoicePanel` | 选项列表 | `choices[]` |
| `ChoiceButton` | 单个选项按钮（符纸风格，不变） | `choice` |
| `ContinueIndicator` | 叙事模式完成后的"点击继续"提示 | `show` (boolean) |
| `StatusBar` | 顶部状态栏（不变） | `state.*` |

---

## 四、模式切换

DialogBox 根据 `choices.length` 自动切换两种模式：

### 叙事模式 (choices.length === 0)

```
┌──────────────────────────┐
│ [头像] 名字               │  ← 旁白时整行隐藏
│                          │
│ 文本逐字显示中...         │  ← NarrativeText 打字机
│ (显示完毕后)              │
│                    ▼     │  ← ContinueIndicator 闪烁
└──────────────────────────┘

用户点击 →
  → 如果 Frame 有 choices → 切换选择模式
  → 如果无 choices 且无下一节点 → 循环结束事件
```

### 选择模式 (choices.length > 0)

```
┌──────────────────────────┐
│ 文本 (已完整显示，截断)    │  ← 不再滚动
│                          │
│ ┌──────────────────────┐ │
│ │ 选项 1               │ │  ← ChoicePanel
│ │ 选项 2               │ │
│ └──────────────────────┘ │
└──────────────────────────┘

用户点击选项 → store.choose(id) → API → 新 Frame → 回到叙事模式
```

---

## 五、数据流

所有组件从 `gameStore` 单向读取，不直接调用 API。

```
API Frame
  │
  ▼
gameStore.currentFrame
  │
  ├─→ BackgroundLayer      props: node.background
  ├─→ CharacterLayer       props: node.speaker (预留)
  ├─→ DialogBox
  │   ├─→ SpeakerHeader    props: node.speaker, node.speaker_avatar
  │   ├─→ NarrativeText    props: node.content
  │   ├─→ ChoicePanel      props: available_choices[]
  │   └─→ ContinueIndicator props: !hasChoices && typingDone
  └─→ StatusBar            props: state.*
```

**状态流转**：
1. `onMounted` → `gameStore.init()` → `GET /api/game/start` → Frame → 渲染
2. 用户点击继续/选项 → `gameStore.choose(choiceId?)` → `POST /api/game/choose/{nodeId}` → 新 Frame → 重新渲染

---

## 六、后端新增字段

`NodeData` 需新增：

| 字段 | 类型 | 默认值 | 用途 |
|------|------|--------|------|
| `speaker_avatar` | `string\|null` | `null` | 说话人头像路径 |

`speaker_avatar` 从 NPC 数据 (`03_npcs.json`) 中读取。需在 NPC schema 中新增 `avatar` 可选字段。

---

## 七、与现有代码的关系

| 现有文件 | 处理 |
|---------|------|
| `GamePlay.vue` | **重写** — 五层布局 + 模式切换 |
| `NarrativePanel.vue` | **合并到 NarrativeText.vue** |
| `ChoicePanel.vue` | **保留** — 移到 DialogBox 内部 |
| `ChoiceButton.vue` | **保留** — 样式不变 |
| `StatusBar.vue` | **保留** — 不变 |
| `gameStore.ts` | **微调** — 新增 `typingDone` 状态 |
| `types/index.ts` | **微调** — `NodeData` 新增 `speaker_avatar` |

---

## 八、Phase 1 vs Phase 2+ 边界

| 功能 | Phase 1 | Phase 2+ |
|------|---------|----------|
| 背景图 | 静态占位（纯 CSS 渐变） | 真实图片 + 淡入淡出 |
| 立绘 | 不渲染 (slot 空) | 人物插画 + 入场动画 |
| 头像框 | 文字占位（显示名字首字） | 真实头像图片 |
| 打字机效果 | 一次性显示全文 | 逐字输出 + 音效 |
| 对话气泡 | 纯文本 | 气泡样式 + 历史回看 |

---

> **版本**: v1.0
> **创建日期**: 2026-07-18
