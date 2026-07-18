# Phase 4 测试清单 — 打磨与扩展

## 前提
- 后端重启（main.py 加了静态文件挂载，engine.py 加了效果处理）
- 前端刷新
- 重新导入数据（`cd backend && venv/Scripts/python import_story.py`）以应用 D 节点 speaker

---

## A. 节点切换动画
- [ ] A1. 点击选项后新节点内容淡入（opacity + translateY）
- [ ] A2. 切换节点时无闪白或布局跳动
- [ ] A3. 不同节点间切换动画流畅

## B. 场景效果
- [ ] B1. `notify` 效果：屏幕上方出现提示文字，渐显渐隐（2.5s）
- [ ] B2. `shake` 效果：屏幕短暂水平震动（0.4s）
- [ ] B3. `flash` 效果：全屏颜色闪烁后消失（0.3s）

## C. 静态资源
- [ ] C1. `GET /assets/` 返回 200（目录存在）
- [ ] C2. 后端挂载 assets 目录不干扰 API 路由
- [ ] C3. 节点 `background` 字段可指向 `/assets/bg/xxx.jpg`

## D. Speaker 显示
- [ ] D1. D 节点（上下九）speaker 显示「张天民」
- [ ] D2. 张天民名字旁有头像占位框（首字「张」）
- [ ] D3. 无 speaker 的节点不显示头像框

## E. 前端交互完整性
- [ ] E1. 打字机效果正常运作（逐字显示）
- [ ] E2. 选项按钮正常显示和点击
- [ ] E3. 存档/读档功能正常
- [ ] E4. 环形小地图正常
- [ ] E5. 过渡文本覆盖层正常

## F. 回归检查
- [ ] F1. `backend: python -m pytest tests/ -v` → 24 passed
- [ ] F2. `frontend: npx vue-tsc --noEmit` → 零错误
- [ ] F3. /play 完整环形遍历 A→H→A 正常
- [ ] F4. /editor 正常工作
