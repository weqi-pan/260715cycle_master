# Phase 7: 对话系统重构 — 修复方案

> **版本**: v1.0
> **日期**: 2026-07-19
> **状态**: 待实施

---

## 一、问题诊断

### Bug 1: 过渡文本有方框 + 文字突然出现

**现象**: 点击选项后，过渡文本被包裹在一个带左边框和背景色的方框中，且文字一次性全部出现。

**根因**:
- `frontend/src/views/GamePlay.vue` 中 `.transition-inline` CSS 设置了 `border-left: 2px solid` + `background: rgba(...)` + `padding: 0.8rem 1rem`，产生了明显的卡片包裹效果
- 过渡文本直接 `v-html` 渲染全文，没有经过打字机逐字输出

### Bug 2: 正文打字机特效消失

**现象**: 进入节点后文字一次性全部显示，没有逐字输出。

**根因**:
- `startTypewriter()` 中 `if (!raw || store.currentNode?.speaker) return` — 当 speaker 非空时跳过
- `canShowChoices` 计算属性在 `isTyping` 尚未结束时就已经让选项显示，时序竞争导致打字机被跳过
- 对话模式引入后，旁白模式的渲染路径被破坏

### Bug 3: 部分选项点击无反应

**现象**: 某些选项点击后没有任何响应，不触发 API 调用也不报错。

**根因**:
- `handleChoice` 守卫条件: `if (isTyping.value || hasMoreLines.value || chosenIds.value.has(c.id) || store.loading) return`
- `hasMoreLines` 在节点切换后未正确重置（`dialogIdx` 残留旧值），导致守卫一直拦截
- 对话模式的 `dialogIdx` 未在 `handleChoice` 的节点切换分支中清零

### Bug 4: 对话气泡包裹整个段落（核心设计缺陷）

**现象**: D 节点（上下九步行街）设置 `speaker: "张天民"` 后，整个 content 字段（包括 5 段旁白 + 1 句张天民台词）全部被渲染为张天民的聊天气泡。

**根因**: 当前数据模型只有一个 `content` 字段。当 `speaker` 非空时前端将整个 content 视为对话并逐段拆成气泡。故事数据中没有机制区分"旁白叙事"和"角色对话台词"。

**现有 D 节点数据**:
```json
{
  "id": "D",
  "speaker": "张天民",
  "content": "上下九步行街的霓虹灯在暮色中渐次亮起。骑楼长廊下人来人往...\n\n这是广州西关最热闹的地方...\n\n20:15。路灯同时闪了一下...\n\n在一家老糖水铺的角落座位上，一个戴黑框眼镜的男人...\n\n\"你是新来的。\"他说。不是疑问句。"
}
```

整个 content 被当成"张天民说的话"，实际上是旁白+台词混合体。

---

## 二、修复方案

### 核心改动: 新增 `dialogue_lines` 数组

在 StoryNode 数据模型中新增独立字段，与 `content`（旁白）彻底分离。

#### 2.1 新的数据格式

```jsonc
{
  "id": "D",
  "name": "上下九步行街",
  "content": "上下九步行街的霓虹灯...（纯旁白，无角色对话）",
  "speaker": null,                    // content 的说话人始终为 null
  "dialogue_lines": [                 // 新增：角色对话行数组
    {
      "speaker": "张天民",
      "text": "\"你是新来的。\"他抬起头，眼眶下有很重的黑眼圈。\"第几天？不用回答——我知道。第一天。你的眼神还没有那种东西。\""
    },
    {
      "speaker": "张天民",
      "text": "他把红豆沙推到你面前。\"我是3月24号来的。室内设计师。55天了。\""
    }
  ]
}
```

#### 2.2 渲染逻辑

旁白和对话在同一节点内顺序展示：

```
1. content 以打字机逐字显示（旁白模式）
2. 打字机完成 → 自动推进
3. dialogue_lines[0] 以聊天气泡显示（张天民 第1句）
4. 点击 → dialogue_lines[1]（张天民 第2句）
5. 点击 → 全部 dialogue_lines 显示完毕
6. 过渡文本（如有）→ 打字机显示
7. 选项按钮出现
```

#### 2.3 数据结构对比

| | 旧方案 | 新方案 |
|---|--------|--------|
| 旁白存储 | `content` (与对话混在一起) | `content` (纯旁白) |
| 对话存储 | 无独立字段 | `dialogue_lines[]` |
| speaker 作用 | 标识整个节点的说话人 | 每行 dialogue_line 有自己的 speaker |
| 多角色对话 | 不支持 | 支持（每行可不同 speaker） |
| 旁白+对话混合 | 导致气泡包裹全段 | 先渲染 content，再渲染 dialogue_lines |

---

## 三、完整改动清单

### 数据层

| 文件 | 改动 |
|------|------|
| `data/story_data/05_nodes/D_上下九.json` | speaker 改为 null, 新增 `dialogue_lines` 数组提取张天民台词 |
| `data/story_data/05_nodes/C_华林寺.json` | speaker 改为 null, 新增 `dialogue_lines` 数组提取燕妍台词 |
| `story_data/` 其他有 speaker 的节点 | 统一迁移到新格式 |

### 后端

| 文件 | 改动 |
|------|------|
| `backend/app/models/story.py` | StoryNode 新增 `dialogue_lines_json` 列 |
| `backend/app/schemas/game.py` | NodeData 新增 `dialogue_lines: list[dict]` |
| `backend/app/engine/graph.py` | GraphBundle 新增 `dialogue_lines` 属性 |
| `backend/app/engine/engine.py` | 传递 `dialogue_lines` 到 NodeData |
| `backend/scripts/import_story.py` | 导入时读取 `dialogue_lines` |

### 前端

| 文件 | 改动 |
|------|------|
| `frontend/src/types/index.ts` | NodeData 新增 `dialogue_lines?: Array<{speaker:string,text:string}>` |
| `frontend/src/views/GamePlay.vue` | 修复全部 4 个问题（见第四节） |

### 文档

| 文件 | 改动 |
|------|------|
| `docs/design/故事内容格式规范.md` | 新增 `dialogue_lines` 字段说明 |

---

## 四、GamePlay.vue 关键修复

### 4.1 新渲染流程

```
watch node change →
  1. 重置: transitions=[], chosenIds=new Set(), dialogIdx=0
  2. if content (旁白):  typing = true, typewriter(content)
     else:               typing = false, 直接跳到下一步
  3. typing 结束 →
     if dialogue_lines 存在:  进入对话模式, 逐条显示气泡
     else:                    显示选项/过渡文本
  4. 对话模式: 点击 → dialogIdx++ → 新气泡出现
  5. 所有对话显示完毕 → 显示选项
```

### 4.2 过渡文本样式

去掉 `.transition-inline` 的 `border-left`、`background`、`padding`，改为纯文本样式：
```scss
.transition-inline {
  margin: 0.8rem 0;
  // 无背景，无边框 — 纯文本
}
.transition-text {
  color: $text-secondary;
  font-size: 0.93rem;
  line-height: 1.8;
}
```

### 4.3 打字机修复

```js
function startTypewriter() {
  // 删除 speaker 跳过逻辑 — 旁白始终打字机
  if (tt) clearInterval(tt)
  const raw = store.currentNode?.content ?? ''
  if (!raw) { isTyping.value = false; return }
  isTyping.value = true
  displayedText.value = ''
  // ... typewriter loop
}
```

### 4.4 选项守卫修复

```js
async function handleChoice(c) {
  // 节点切换时清除 hasMoreLines 状态
  // 简化为只检查 typing + loading + chosen
  if (isTyping.value || store.loading || chosenIds.value.has(c.id)) return
  // ...
  // 节点切换分支中: dialogIdx = 0
}
```

---

## 五、实施步骤

1. **数据迁移**: 修改 D/C 节点 JSON，新增 `dialogue_lines`
2. **后端模型**: ORM → Schema → GraphBundle → Engine 全链路加字段
3. **前端类型**: NodeData 加 `dialogue_lines`
4. **前端渲染**: 重写 GamePlay.vue 对话/旁白分支
5. **样式**: 去掉 transition 方框，恢复打字机
6. **测试**: API 返回验证 + 前端交互验证
7. **文档**: 更新内容格式规范
