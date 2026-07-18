"""
应用配置模块。

通过 paths 模块解析项目目录结构，构造 SQLite 数据库连接 URL。
所有路径均基于 paths.py 的相对路径计算，不依赖绝对路径，支持跨机器迁移。
"""

# backend/app/config.py
from .paths import DATABASE_PATH, STORY_DATA_DIR

# SQLite 数据库连接 URL（使用 WAL 模式以支持并发读写）
# connect_args={"check_same_thread": False} 在 database.py 中配置
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"
