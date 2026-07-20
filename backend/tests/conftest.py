"""后端测试公共 fixture。

所有需要写数据库的新增测试应使用 isolated_db_session，禁止写入
data/cycle_master.db。现有纯引擎单测不需要数据库，可继续独立运行。
"""

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base
from app.models.save import NodePersistentState, Save  # noqa: F401
from app.models.story import Choice, StoryNode  # noqa: F401


@pytest.fixture
def isolated_db_session(tmp_path) -> Iterator[Session]:
    """提供启用 SQLite 外键约束的临时数据库会话。"""
    database_path = tmp_path / "cycle_master_test.db"
    test_engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(test_engine, "connect")
    def enable_foreign_keys(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    session_factory = sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
    )
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
