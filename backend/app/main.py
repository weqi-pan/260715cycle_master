"""
FastAPI 应用入口。

职责：
    1. 创建 FastAPI 应用实例，配置 CORS 和静态文件挂载
    2. 注册三个路由模块（game / saves / editor）
    3. 挂载 assets/ 静态资源目录（背景图、角色立绘、音频文件）
    4. @app.on_event("startup") 启动时加载 v3 快照并初始化数据库表结构
    5. 提供 /api/health 健康检查端点
"""

# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from .database import init_db
from .routers import game, saves, editor
from .paths import ASSETS_DIR

# ── 创建 FastAPI 应用实例 ────────────────────────────────────
app = FastAPI(title="Cycle Master API", version="0.4.0")

# ── 挂载静态资源目录 ─────────────────────────────────────────
# 前端通过 /assets/bg_xxx.png 等路径访问背景图、立绘、音频文件
# 静态资源统一放在 data/assets/ 下
ASSETS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")

# ── CORS 中间件 ──────────────────────────────────────────────
# 开发环境下 Vue 3 dev server 运行在 localhost:5173
# 生产环境部署后可根据实际域名调整 allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由模块 ─────────────────────────────────────────────
# 三个路由模块分别负责：
#   - game:   游戏运行时（开始游戏、选择分支） → /api/game/*
#   - saves:  存档管理（新建、读取、更新、删除） → /api/saves/*
#   - editor: 可视化编辑器（增删改查节点和选项） → /api/editor/*
app.include_router(game.router)
app.include_router(saves.router)
app.include_router(editor.router)


@app.on_event("startup")
def on_startup():
    """严格加载 v3 快照后自动建表；任一步失败都阻止应用启动。"""
    game.story.refresh()
    init_db()


@app.get("/api/health")
def health():
    """
    健康检查端点。

    返回:
        {"status": "ok"}

    用于前端轮询确认后端已就绪、CI/CD 部署验证、监控探活。
    """
    return {"status": "ok"}
