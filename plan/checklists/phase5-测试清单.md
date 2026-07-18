# Phase 5 测试清单 — 沉浸体验

## 前提
- 后端重启（需重建 DB：删除 cycle_master.db → 运行 import_story.py）
- 前端刷新
- DB 重建后 D/C 节点的 speaker 才会生效

---

## A. 音频支持
- [ ] A1. NodeData 包含 `ambient` 字段（API 响应中可见）
- [ ] A2. 设置 `ambient` 路径的节点，前端尝试加载对应音频
- [ ] A3. 无 ambient 节点不报错，正常显示

## B. Speaker 显示
- [ ] B1. D 节点 speaker="张天民"，显示头像框+名字
- [ ] B2. C 节点 speaker="燕妍"，显示头像框+名字
- [ ] B3. A/B/E/F/G/H 节点 speaker=null，不显示头像框
- [ ] B4. speaker 首字正确显示在头像框中

## C. 节点色调节奏
- [ ] C1. `color_palette` 字段落到前端 NodeData
- [ ] C2. 不同节点背景暗角色调有差异
- [ ] C3. 视觉过渡自然，无突兀颜色跳变

## D. SFX 效果
- [ ] D1. `sfx` 效果类型不被引擎报错
- [ ] D2. 前端监听 sfx 效果通道（预留）

## E. 全环遍历
- [ ] E1. A→B→C→D→E→F→G→H→A 完整可走
- [ ] E2. 循环计数递增
- [ ] E3. 遍历过程中无崩溃或状态丢失

## F. 回归
- [ ] F1. `backend: python -m pytest tests/ -v` → 24 passed
- [ ] F2. `frontend: npx vue-tsc --noEmit` → 零错误
