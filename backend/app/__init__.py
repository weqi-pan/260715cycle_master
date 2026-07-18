"""Cycle Master — FastAPI 后端应用。

Package:
    app.main       — FastAPI 应用入口
    app.config     — 数据库连接配置
    app.database   — SQLAlchemy 引擎与会话管理
    app.paths      — 项目路径解析器
    app.engine     — 图引擎核心（图加载、条件求值、特殊路由）
    app.models     — ORM 模型（StoryNode, Choice, Save）
    app.routers    — REST API 路由（game, saves, editor）
    app.schemas    — Pydantic 数据校验模型
"""
