"""
数据库引擎与会话管理模块。

提供 SQLAlchemy 引擎创建、会话工厂、声明式基类和 FastAPI 依赖注入入口。
SQLite 引擎使用 WAL 模式 + check_same_thread=False 以支持异步并发。

核心导出：
    - engine: SQLAlchemy 引擎实例
    - SessionLocal: 线程安全的会话工厂
    - Base: ORM 模型声明式基类（所有模型继承自此）
    - get_db(): FastAPI Depends 可用的数据库会话生成器
    - init_db(): 应用启动时根据模型定义自动建表
"""

# backend/app/database.py
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DATABASE_URL

# ── SQLAlchemy 引擎 ──────────────────────────────────────────
# echo=False: 生产环境关闭 SQL 日志
# check_same_thread=False: FastAPI 多线程环境下允许跨线程使用连接
engine = create_engine(
    DATABASE_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def configure_sqlite_connection(dbapi_connection, _connection_record):
    """每条 SQLite 连接都启用外键、WAL 与合理的锁等待。"""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

# ── 会话工厂 ─────────────────────────────────────────────────
# autocommit=False: 显式调用 commit() 才提交，防止意外写入
# autoflush=False: 显式调用 flush()，避免隐式刷新干扰查询
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ── 声明式基类 ───────────────────────────────────────────────
# 所有 ORM 模型（StoryNode, Choice, Save 等）均继承此类
Base = declarative_base()


def get_db():
    """
    FastAPI 依赖注入：为每个请求提供独立的数据库会话。

    用法：
        @router.get("/xxx")
        def endpoint(db: Session = Depends(get_db)):
            ...

    请求结束时自动关闭会话，确保连接不会被泄漏。
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(bind=engine):
    """
    应用启动时自动建表。

    读取所有继承自 Base 的 ORM 模型，在数据库中创建对应的表结构。
    如果表已存在则跳过，不会覆盖已有数据（使用 create_all 的默认行为）。
    ``bind`` 允许测试在隔离的临时数据库上执行相同初始化流程。
    """
    Base.metadata.create_all(bind=bind)
