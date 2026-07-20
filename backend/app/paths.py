"""
项目路径解析器。

所有路径均以本文件位置为锚点计算，不依赖绝对路径，支持跨机器迁移。

锚点链：
    backend/app/paths.py
    └── backend/          ← BACKEND_DIR
        └── app/
            └── paths.py  ← __file__ (anchor)

目录结构约定：
    cycle_master/                  ← PROJECT_ROOT
    ├── backend/                   ← BACKEND_DIR
    │   ├── app/                   ← _APP_DIR
    │   ├── scripts/               ← 工具脚本
    │   └── tests/                 ← 单元测试
    ├── frontend/                  ← FRONTEND_DIR
    ├── data/                      ← DATA_DIR
    │   ├── story_data_v2/         ← 游戏内容 JSON（唯一数据源）
    │   ├── assets/                ← 静态资源
    │   └── cycle_master.db        ← SQLite 数据库
    ├── docs/                      ← DOCS_DIR
    ├── plan/                      ← PLAN_DIR
    ├── tests/                     ← E2E 测试
    └── scripts/                   ← 启动脚本
"""

from pathlib import Path

# ── 锚点 ─────────────────────────────────────────────────────
# 本文件路径: cycle_master/backend/app/paths.py
_THIS_FILE = Path(__file__).resolve()
_APP_DIR = _THIS_FILE.parent            # backend/app/
BACKEND_DIR = _APP_DIR.parent           # backend/
PROJECT_ROOT = BACKEND_DIR.parent       # cycle_master/

# ── 数据目录（统一管理所有非代码数据） ──────────────────────
DATA_DIR = PROJECT_ROOT / "data"
STORY_DATA_V2_DIR = DATA_DIR / "story_data_v2"  # 游戏内容 JSON（v2）
# 兼容既有导入名；路径已明确指向 v2，不再支持 v1 目录。
STORY_DATA_DIR = STORY_DATA_V2_DIR
ASSETS_DIR = DATA_DIR / "assets"                # 静态资源（背景/立绘/音频）
DATABASE_PATH = DATA_DIR / "cycle_master.db"    # SQLite 数据库
EXPORTS_DIR = DATA_DIR / "exports"              # 数据导出

# ── 代码目录 ─────────────────────────────────────────────────
FRONTEND_DIR = PROJECT_ROOT / "frontend"        # Vue 3 前端
BACKEND_SCRIPTS_DIR = BACKEND_DIR / "scripts"   # 后端工具脚本

# ── 文档目录 ─────────────────────────────────────────────────
DOCS_DIR = PROJECT_ROOT / "docs"                # 设计文档 + 故事大纲
PLAN_DIR = PROJECT_ROOT / "plan"                # 开发计划

# ── 工具与测试 ───────────────────────────────────────────────
SCRIPTS_DIR = PROJECT_ROOT / "scripts"          # 启动/部署脚本
TESTS_DIR = PROJECT_ROOT / "tests"              # E2E 测试

# ── 启动时校验（确保关键目录存在） ───────────────────────────
_required = {
    "BACKEND_DIR": BACKEND_DIR,
    "DATA_DIR": DATA_DIR,
    "STORY_DATA_V2_DIR": STORY_DATA_V2_DIR,
}
_missing = [f"{name}: {path}" for name, path in _required.items() if not path.exists()]
if _missing:
    raise FileNotFoundError(
        "项目结构校验失败，以下目录不存在:\n"
        + "\n".join(f"  - {m}" for m in _missing)
        + f"\n\n预期项目根目录: {PROJECT_ROOT}"
    )


def print_paths():
    """打印所有已解析的路径（调试用）。"""
    import sys
    out = sys.stdout

    def p(key, val):
        out.write(f"  {key:24s} {val}\n")

    p("PROJECT_ROOT", PROJECT_ROOT)
    p("BACKEND_DIR", BACKEND_DIR)
    p("DATA_DIR", DATA_DIR)
    p("STORY_DATA_DIR", STORY_DATA_DIR)
    p("STORY_DATA_V2_DIR", STORY_DATA_V2_DIR)
    p("ASSETS_DIR", ASSETS_DIR)
    p("DATABASE_PATH", DATABASE_PATH)
    p("EXPORTS_DIR", EXPORTS_DIR)
    p("FRONTEND_DIR", FRONTEND_DIR)
    p("DOCS_DIR", DOCS_DIR)
    p("PLAN_DIR", PLAN_DIR)
    p("SCRIPTS_DIR", SCRIPTS_DIR)
    p("TESTS_DIR", TESTS_DIR)


if __name__ == "__main__":
    print_paths()
