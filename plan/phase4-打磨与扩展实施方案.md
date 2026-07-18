# Phase 4: 打磨与扩展 — 实施方案

## Task 1: 节点切换动画
- 叙事文本淡入 (opacity 0→1, 400ms)
- 选项按钮从下方滑入 (translateY + opacity)
- 背景图 crossfade 过渡

## Task 2: 静态资源服务
- FastAPI 挂载 `/assets` 静态目录
- 背景图占位（纯 CSS 渐变模拟场景氛围）
- `background` 字段生效：有色调覆盖层

## Task 3: 新效果类型
- `notify:消息文本` — 屏幕中央短暂提示
- `shake` — 屏幕震动效果
- `flash:颜色` — 全屏闪烁

## Task 4: 故事 Speaker 填充
- D节点(上下九) — 张天民对话段落拆分为 speaker
- E节点(八棺) — 穿越后 NPC 对话段落拆分为 speaker
