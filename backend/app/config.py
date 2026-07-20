"""
应用配置模块。

通过 paths 模块解析项目目录结构，构造 SQLite 数据库连接 URL。
所有路径均基于 paths.py 的相对路径计算，不依赖绝对路径，支持跨机器迁移。
"""

# backend/app/config.py
import os
from pathlib import Path

from .paths import DATABASE_PATH as DEFAULT_DATABASE_PATH, STORY_DATA_DIR

# 测试和隔离运行可通过环境变量指向临时数据库。
# 未设置时仍使用 data/cycle_master.db，保持现有开发体验不变。
DATABASE_PATH = Path(
    os.environ.get("CYCLE_MASTER_DATABASE_PATH", str(DEFAULT_DATABASE_PATH))
).resolve()

# SQLite 数据库连接 URL（使用 WAL 模式以支持并发读写）
# connect_args={"check_same_thread": False} 在 database.py 中配置
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
