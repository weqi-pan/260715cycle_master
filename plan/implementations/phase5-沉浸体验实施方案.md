# Phase 5: 沉浸体验 — 实施方案

## Task 1: 音频支持
- 后端: NodeData 新增 `ambient` 字段（环境音路径）
- 后端: Choice 新增 `sfx` 效果类型（点击音效）
- 前端: 音频管理器（HTML5 Audio），节点切换时淡入淡出环境音
- 前端: 选项点击 + 打字机音效占位

## Task 2: 故事 Speaker 迁移
- 从 MD 详细故事文件中提取 NPC 对话标注
- 填充 story_data JSON 的 speaker 字段
- 覆盖: D(张天民), E(阿六/李二狗/刘启盛/慧觉等), C(燕妍), G(吴应执)

## Task 3: 节点氛围色调
- 根据 color_palette 字段动态调整背景色调
- 每个节点有独特的暗角颜色

## Task 4: E2E 自动化测试
- 后端持续状态验证（全环遍历 + flag 积累）
- 前端关键路径渲染验证
