"""后端测试公共 fixture。

所有需要写数据库的新增测试应使用 isolated_db_session，禁止写入
data/cycle_master.db。现有纯引擎单测不需要数据库，可继续独立运行。
"""

import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from app.database import Base, init_db
from app.models.save import NodePersistentState, Save  # noqa: F401
from app.models.story import Choice, StoryNode  # noqa: F401
from app.story.compiler import StoryCompiler


PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def canonical_v3_snapshot():
    """编译并返回仓库中受版本控制的 canonical v3 剧情快照。"""
    return StoryCompiler().compile(
        PROJECT_ROOT / "data" / "story_v3"
    ).require_success()


@pytest.fixture(scope="session")
def project_root() -> Path:
    """返回项目根目录，供路径边界测试复用。"""
    return PROJECT_ROOT


@pytest.fixture
def copy_story_v3(project_root: Path):
    """将 canonical v3 创作源复制到隔离目录并返回复制函数。"""

    def copy(destination: Path) -> Path:
        return Path(
            shutil.copytree(project_root / "data" / "story_v3", destination)
        )

    return copy


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

    init_db(bind=test_engine)
    session_factory = sessionmaker(
        bind=test_engine,
        autocommit=False,
        autoflush=False,
    )
    session = session_factory()
    try:
        assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
