"""REST API 路由模块。

定义 FastAPI 路由端点，按功能域分为三个子模块。

Modules:
    game   — 游戏运行时 API（/api/game/start, /api/game/choose）
    saves  — 存档管理 API（/api/saves/*）
    editor — 可视化编辑器 API（/api/editor/*）
"""
