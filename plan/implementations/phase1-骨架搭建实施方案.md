# Phase 1: 骨架搭建 — 实施方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建后端 FastAPI + SQLite 图引擎和前端 Vue 3 播放器，跑通一个从节点 A 出发 → 做选择 → 到节点 B 的最简环形 demo（8 主节点 + 2 特殊节点 + 20 子节点数据全部可导入可渲染）。

**Architecture:** 后端 Python FastAPI 提供 REST API，内部由 graph.py 加载剧本图、engine.py 执行游戏主循环、condition_eval.py 解析条件表达式、special_router.py 处理 J/K 特殊路由。前端 Vue 3 + Pinia 通过 API 获取节点内容和选项，渲染文字冒险界面。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy 2.0 + SQLite + Pydantic v2 / Vue 3 + Vite + TypeScript + Element Plus + Pinia + SCSS

## Global Constraints

- Python >= 3.12, Node >= 20 LTS
- 后端端口 8000，前端端口 5173（Vite 默认），前端 proxy `/api` → `localhost:8000`
- 所有 JSON 字段使用 snake_case，TypeScript 使用 camelCase（API 层做转换）
- 游戏状态（GameState）在 API 层以 JSON 传输，不在后端做 session 持久化（Phase 1）
- Choice.id 命名: `{from_node}_choice_{序号}`（如 `A_choice_01`）
- Flag.id 命名: `snake_case`（如 `know_secret_tunnel`）
- Item.id 命名: `item_xxx`（如 `item_amulet`）
- `condition` 字段：null = 始终可选；非 null = 条件表达式字符串
- Effect 结构：`{"type": "xxx", "target": "xxx", "value": xxx}`
- 所有 story_data JSON 文件通过 `import_story.py` 导入 SQLite，不手动写 SQL insert

---

## File Structure

```
cycle_master/
├── plan/                                    # 实施方案文档
│   └── phase1-骨架搭建实施方案.md            # 本文档
│
├── backend/                                 # Python FastAPI 后端
│   ├── requirements.txt
│   ├── import_story.py                      # 故事数据导入脚本
│   ├── seed_data.py                         # 开发测试用种子数据（8节点环形demo）
│   └── app/
│       ├── __init__.py
│       ├── main.py                          # FastAPI 入口，CORS，路由注册
│       ├── config.py                        # 配置管理（DB路径等）
│       ├── database.py                      # SQLAlchemy engine + session 工厂
│       ├── models/
│       │   ├── __init__.py
│       │   ├── story.py                     # StoryNode, Choice ORM 模型
│       │   └── save.py                      # Save, NodePersistentState ORM 模型
│       ├── schemas/
│       │   ├── __init__.py
│       │   ├── game.py                      # GameState, Frame, ChoiceResult Pydantic
│       │   └── editor.py                    # NodeCreate, ChoiceCreate Pydantic
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── graph.py                     # 图结构加载/查询
│       │   ├── engine.py                    # 游戏主循环 process_choice()
│       │   ├── condition_eval.py            # 条件表达式解析器
│       │   └── special_router.py            # K/J 特殊节点路由
│       └── routers/
│           ├── __init__.py
│           ├── game.py                      # /api/game/* 端点
│           ├── saves.py                     # /api/saves/* 端点
│           └── editor.py                    # /api/editor/* 端点
│
├── frontend/                                # Vue 3 前端
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── src/
│       ├── main.ts                          # Vue 入口
│       ├── App.vue                          # 根组件
│       ├── router/
│       │   └── index.ts                     # /play 和 /editor 路由
│       ├── types/
│       │   └── index.ts                     # TypeScript 类型定义
│       ├── api/
│       │   └── game.ts                      # API 调用封装
│       ├── stores/
│       │   └── gameStore.ts                 # Pinia 游戏状态
│       ├── views/
│       │   ├── GamePlay.vue                 # 游戏播放器页面
│       │   └── EditorPlaceholder.vue        # 编辑器占位页
│       ├── components/
│       │   └── player/
│       │       ├── NarrativePanel.vue       # 正文显示区（打字机效果）
│       │       ├── ChoicePanel.vue          # 选项按钮列表
│       │       ├── ChoiceButton.vue         # 单个选项按钮
│       │       └── StatusBar.vue            # 顶部状态栏
│       └── assets/
│           └── styles/
│               ├── variables.scss           # SCSS 变量
│               └── global.scss              # 全局样式
│
├── story_data/                              # 故事数据 JSON（已存在，不修改）
│   ├── 00_meta.json
│   ├── 01_flags.json
│   ├── 02_items.json
│   ├── 03_npcs.json
│   ├── 04_player_attributes.json
│   ├── 05_nodes/
│   └── 06_choices/
│
└── design_docs/                             # 设计文档（已存在，不修改）
```

---

### Task 1: 后端项目骨架

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`

**Produces:** SQLAlchemy engine 和 session 工厂，后续所有模块通过 `get_db()` 获取数据库会话。

- [ ] **Step 1: 创建 requirements.txt**

```txt
fastapi==0.115.6
uvicorn[standard]==0.34.0
sqlalchemy==2.0.36
pydantic==2.10.3
```

- [ ] **Step 2: 安装依赖**

```bash
cd backend
python -m venv venv
source venv/Scripts/activate  # Windows
pip install -r requirements.txt
```

Expected: 所有包安装成功，无报错。

- [ ] **Step 3: 创建 config.py**

```python
# backend/app/config.py
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'cycle_master.db')}"
STORY_DATA_DIR = os.path.join(os.path.dirname(BASE_DIR), "story_data")
```

- [ ] **Step 4: 创建 database.py**

```python
# backend/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .config import DATABASE_URL

engine = create_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 5: 创建 backend/app/__init__.py（空文件）**

```bash
touch backend/app/__init__.py
```

- [ ] **Step 6: 验证 — 启动 Python 导入测试**

```bash
cd backend
python -c "from app.config import DATABASE_URL, STORY_DATA_DIR; from app.database import engine, Base; print('OK:', DATABASE_URL, STORY_DATA_DIR)"
```

Expected: `OK: sqlite:///.../cycle_master.db .../story_data`

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/app/__init__.py backend/app/config.py backend/app/database.py
git commit -m "feat: backend project skeleton with FastAPI + SQLAlchemy config"
```

---

### Task 2: 数据库 ORM 模型

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/story.py`
- Create: `backend/app/models/save.py`

**Consumes:** `Base` from `app.database`
**Produces:** `StoryNode`, `Choice` ORM 模型（剧本表）；`Save`, `NodePersistentState` ORM 模型（存档表）

- [ ] **Step 1: 创建 models/__init__.py（空文件）**

```bash
touch backend/app/models/__init__.py
```

- [ ] **Step 2: 创建 models/story.py**

```python
# backend/app/models/story.py
from sqlalchemy import Column, String, Float, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from ..database import Base

class StoryNode(Base):
    __tablename__ = "story_nodes"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    position = Column(Float, nullable=False)
    node_type = Column(String, nullable=False, default="normal")
    time_label = Column(String, nullable=True)
    content = Column(Text, nullable=False)
    speaker = Column(String, nullable=True)
    background = Column(String, nullable=True)
    cycle_variants_json = Column(Text, nullable=True, default="{}")
    color_palette = Column(String, nullable=True)
    atmosphere_json = Column(Text, nullable=True, default="[]")
    sensory = Column(Text, nullable=True)
    gender_variant_json = Column(Text, nullable=True)
    parent_node_id = Column(String, nullable=True)
    trigger_condition = Column(String, nullable=True)
    crossing_config_json = Column(Text, nullable=True)
    warp_config_json = Column(Text, nullable=True)
    shortcut_config_json = Column(Text, nullable=True)
    npc_item_mapping_json = Column(Text, nullable=True)
    scene_items_json = Column(Text, nullable=True)

    choices = relationship("Choice", back_populates="from_node",
                           foreign_keys="Choice.from_node_id")


class Choice(Base):
    __tablename__ = "choices"

    id = Column(String, primary_key=True)
    from_node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)
    text = Column(String, nullable=False)
    short_text = Column(String, nullable=True)
    next_node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)
    condition = Column(String, nullable=True)
    effects_json = Column(Text, nullable=False, default="[]")
    priority = Column(Integer, default=99)
    hint = Column(String, nullable=True)
    is_hidden_when_locked = Column(Integer, default=0)
    transition_text = Column(Text, nullable=True)

    from_node = relationship("StoryNode", back_populates="choices",
                             foreign_keys=[from_node_id])

    __table_args__ = (
        Index("idx_choices_from", "from_node_id"),
    )
```

- [ ] **Step 3: 创建 models/save.py**

```python
# backend/app/models/save.py
import uuid
from sqlalchemy import Column, String, Integer, Float, Text, ForeignKey, Index, UniqueConstraint
from ..database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Save(Base):
    __tablename__ = "saves"

    id = Column(String, primary_key=True, default=generate_uuid)
    save_name = Column(String, nullable=False)
    created_at = Column(String, nullable=False)  # ISO 8601
    updated_at = Column(String, nullable=False)
    current_node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)
    cycle_count = Column(Integer, default=0)
    half_cycle_count = Column(Integer, default=0)
    inventory_json = Column(Text, default="[]")
    flags_json = Column(Text, default="{}")
    visited_nodes_json = Column(Text, default="[]")
    player_attributes_json = Column(Text, default="{}")
    endings_reached_json = Column(Text, default="[]")


class NodePersistentState(Base):
    __tablename__ = "node_persistent_state"

    id = Column(String, primary_key=True, default=generate_uuid)
    save_id = Column(String, ForeignKey("saves.id"), nullable=False)
    node_id = Column(String, ForeignKey("story_nodes.id"), nullable=False)
    items_json = Column(Text, default="[]")
    dangers_json = Column(Text, default="[]")

    __table_args__ = (
        UniqueConstraint("save_id", "node_id"),
        Index("idx_persist_save", "save_id"),
    )
```

- [ ] **Step 4: 验证 — 创建数据库表**

```bash
cd backend
python -c "
from app.database import init_db, engine
init_db()
from sqlalchemy import inspect
inspector = inspect(engine)
tables = inspector.get_table_names()
print('Tables:', tables)
assert 'story_nodes' in tables
assert 'choices' in tables
assert 'saves' in tables
assert 'node_persistent_state' in tables
print('All tables created successfully')
"
```

Expected: `Tables: ['choices', 'node_persistent_state', 'saves', 'story_nodes']` + success message

- [ ] **Step 5: Commit**

```bash
git add backend/app/models/
git commit -m "feat: add ORM models — StoryNode, Choice, Save, NodePersistentState"
```

---

### Task 3: Pydantic Schema

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/game.py`
- Create: `backend/app/schemas/editor.py`

**Consumes:** ORM models from Task 2
**Produces:** `GameState`, `Frame`, `ChoiceResult` Pydantic 模型（API 请求/响应验证）

- [ ] **Step 1: 创建 schemas/__init__.py（空文件）**

```bash
touch backend/app/schemas/__init__.py
```

- [ ] **Step 2: 创建 schemas/game.py**

```python
# backend/app/schemas/game.py
from pydantic import BaseModel, Field
from typing import Optional, Any


class Effect(BaseModel):
    type: str
    target: str
    value: Any


class ChoiceResult(BaseModel):
    id: str
    text: str
    short_text: Optional[str] = None
    available: bool = True
    reason: Optional[str] = None
    source: str = "static"  # "static" | "special_shortcut" | "special_warp"


class GameState(BaseModel):
    current_node_id: str
    cycle_count: int = 0
    half_cycle_count: int = 0
    inventory: list[dict] = []
    flags: dict[str, Any] = {}
    visited_nodes: list[str] = []
    endings_reached: list[str] = []
    player_attributes: dict[str, int] = {}


class NodeData(BaseModel):
    id: str
    name: str
    node_type: str
    position: float
    time_label: Optional[str] = None
    content: str
    speaker: Optional[str] = None
    background: Optional[str] = None


class PersistentFound(BaseModel):
    items: list[dict] = []
    cross_surface_items: list[dict] = []
    dangers: list[dict] = []


class Frame(BaseModel):
    node: NodeData
    state: GameState
    available_choices: list[ChoiceResult] = []
    persistent_found: PersistentFound = PersistentFound()
    cycle_event: Optional[dict] = None


class ChooseRequest(BaseModel):
    choice_id: str


class SaveGameRequest(BaseModel):
    save_id: str
    state: GameState
```

- [ ] **Step 3: 创建 schemas/editor.py**

```python
# backend/app/schemas/editor.py
from pydantic import BaseModel
from typing import Optional
from .game import Effect


class NodeCreate(BaseModel):
    id: str
    name: str
    position: float
    node_type: str = "normal"
    time_label: Optional[str] = None
    content: str
    speaker: Optional[str] = None
    background: Optional[str] = None


class ChoiceCreate(BaseModel):
    id: str
    from_node_id: str
    text: str
    short_text: Optional[str] = None
    next_node_id: str
    condition: Optional[str] = None
    effects: list[Effect] = []
    priority: int = 99
    hint: Optional[str] = None
    is_hidden_when_locked: bool = False
```

- [ ] **Step 4: 验证 — 导入并实例化**

```bash
cd backend
python -c "
from app.schemas.game import Frame, GameState, ChoiceResult, NodeData
gs = GameState(current_node_id='A')
print('GameState:', gs.model_dump())
fr = Frame(node=NodeData(id='A', name='Test', node_type='main', position=0.0, content='Hello'), state=gs)
print('Frame created OK')
"
```

Expected: GameState dict printed + `Frame created OK`

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas/
git commit -m "feat: add Pydantic schemas — GameState, Frame, ChoiceResult, Editor"
```

---

### Task 4: 条件表达式解析器

**Files:**
- Create: `backend/app/engine/__init__.py`
- Create: `backend/app/engine/condition_eval.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/test_condition_eval.py`

**Consumes:** `GameState` schema from Task 3
**Produces:** `ConditionEvaluator` 类，提供 `evaluate(condition_str, state) -> bool` 和 `check(condition_str, state) -> bool`（后者 condition 为 null 时返回 True）

**Condition syntax:**
```
has_item:ID              背包持有道具
has_flag:NAME            标记为 true
flag:NAME=VALUE          标记等于指定值
attr:NAME>=N             属性比较 (>=, <=, >, <, ==, !=)
cycle>=N                 完整循环次数
half_cycle>=N            半循环次数
at_node:ID               当前节点
not:COND                 取反
and:COND1,COND2,...      全部满足
or:COND1,COND2,...       满足其一
```

- [ ] **Step 1: 创建 tests/test_condition_eval.py — 基础条件测试**

```python
# backend/tests/test_condition_eval.py
import pytest
from app.engine.condition_eval import ConditionEvaluator
from app.schemas.game import GameState


def make_state(**kwargs):
    defaults = {
        "current_node_id": "A",
        "cycle_count": 1,
        "half_cycle_count": 0,
        "inventory": [],
        "flags": {},
        "player_attributes": {"sanity": 100, "courage": 5, "insight": 3},
    }
    defaults.update(kwargs)
    return GameState(**defaults)


@pytest.fixture
def evaluator():
    return ConditionEvaluator()


# --- null / empty ---
def test_null_condition_always_true(evaluator):
    assert evaluator.check(None, make_state()) == True
    assert evaluator.check("", make_state()) == True


# --- has_item ---
def test_has_item_true(evaluator):
    state = make_state(inventory=[{"id": "item_key", "name": "Key"}])
    assert evaluator.evaluate("has_item:item_key", state) == True


def test_has_item_false(evaluator):
    state = make_state(inventory=[])
    assert evaluator.evaluate("has_item:item_key", state) == False


# --- has_flag ---
def test_has_flag_true(evaluator):
    state = make_state(flags={"know_secret": True})
    assert evaluator.evaluate("has_flag:know_secret", state) == True


def test_has_flag_false(evaluator):
    state = make_state(flags={})
    assert evaluator.evaluate("has_flag:know_secret", state) == False


# --- flag:NAME=VALUE ---
def test_flag_eq_true(evaluator):
    state = make_state(flags={"zhang_trust": 3})
    assert evaluator.evaluate("flag:zhang_trust=3", state) == True


def test_flag_eq_false(evaluator):
    state = make_state(flags={"zhang_trust": 1})
    assert evaluator.evaluate("flag:zhang_trust=3", state) == False


# --- attr ---
def test_attr_gte_true(evaluator):
    assert evaluator.evaluate("attr:courage>=5", make_state()) == True


def test_attr_gte_false(evaluator):
    assert evaluator.evaluate("attr:courage>=8", make_state()) == False


def test_attr_lt_true(evaluator):
    assert evaluator.evaluate("attr:sanity<50", make_state(player_attributes={"sanity": 30})) == True


# --- cycle ---
def test_cycle_gte_true(evaluator):
    assert evaluator.evaluate("cycle>=3", make_state(cycle_count=5)) == True


def test_cycle_gte_false(evaluator):
    assert evaluator.evaluate("cycle>=3", make_state(cycle_count=1)) == False


# --- half_cycle ---
def test_half_cycle_true(evaluator):
    assert evaluator.evaluate("half_cycle>=1", make_state(half_cycle_count=2)) == True


# --- at_node ---
def test_at_node_true(evaluator):
    assert evaluator.evaluate("at_node:E", make_state(current_node_id="E")) == True


def test_at_node_false(evaluator):
    assert evaluator.evaluate("at_node:E", make_state(current_node_id="A")) == False


# --- not ---
def test_not(evaluator):
    assert evaluator.evaluate("not:has_item:item_key", make_state(inventory=[])) == True
    assert evaluator.evaluate("not:has_item:item_key", make_state(inventory=[{"id": "item_key"}])) == False


# --- and ---
def test_and_both_true(evaluator):
    state = make_state(inventory=[{"id": "item_key"}], flags={"unlocked": True})
    assert evaluator.evaluate("and:has_item:item_key,has_flag:unlocked", state) == True


def test_and_one_false(evaluator):
    state = make_state(inventory=[{"id": "item_key"}], flags={})
    assert evaluator.evaluate("and:has_item:item_key,has_flag:unlocked", state) == False


# --- or ---
def test_or_one_true(evaluator):
    state = make_state(inventory=[], flags={"unlocked": True})
    assert evaluator.evaluate("or:has_item:item_key,has_flag:unlocked", state) == True


def test_or_both_false(evaluator):
    state = make_state(inventory=[], flags={})
    assert evaluator.evaluate("or:has_item:item_key,has_flag:unlocked", state) == False


# --- nested ---
def test_nested_and_or(evaluator):
    # and:has_item:beads,or:courage>=8,cycle>=3
    state = make_state(
        inventory=[{"id": "item_beads"}],
        player_attributes={"courage": 5},
        cycle_count=5,
    )
    assert evaluator.evaluate("and:has_item:item_beads,or:attr:courage>=8,cycle>=3", state) == True
```

- [ ] **Step 2: 运行测试验证全部失败**

```bash
cd backend
pip install pytest
python -m pytest tests/test_condition_eval.py -v
```

Expected: 全部 17 个测试 FAIL（ModuleNotFoundError）

- [ ] **Step 3: 实现 condition_eval.py**

```python
# backend/app/engine/condition_eval.py
import re
from app.schemas.game import GameState


class ConditionEvaluator:
    """解析条件表达式字符串，根据 GameState 求值。"""

    def check(self, condition: str | None, state: GameState) -> bool:
        """null/空字符串 = 无条件限制，始终可选。"""
        if condition is None or condition.strip() == "":
            return True
        return self.evaluate(condition, state)

    def evaluate(self, condition: str, state: GameState) -> bool:
        condition = condition.strip()

        # ── and ──
        if condition.startswith("and:"):
            inner = condition[4:]
            parts = self._split_top_level(inner)
            return all(self.evaluate(p, state) for p in parts)

        # ── or ──
        if condition.startswith("or:"):
            inner = condition[3:]
            parts = self._split_top_level(inner)
            return any(self.evaluate(p, state) for p in parts)

        # ── not ──
        if condition.startswith("not:"):
            inner = condition[4:]
            return not self.evaluate(inner, state)

        # ── has_item ──
        if condition.startswith("has_item:"):
            item_id = condition[9:]
            return any(item.get("id") == item_id for item in state.inventory)

        # ── has_flag ──
        if condition.startswith("has_flag:"):
            flag_name = condition[9:]
            return bool(state.flags.get(flag_name))

        # ── flag:NAME=VALUE ──
        m = re.match(r"^flag:([^=]+)=(.+)$", condition)
        if m:
            flag_name, expected = m.group(1), m.group(2)
            actual = state.flags.get(flag_name)
            return str(actual) == expected

        # ── attr:NAME OP VALUE ──
        m = re.match(r"^attr:(\w+)(>=|<=|>|<|==|!=)(.+)$", condition)
        if m:
            attr_name, op, raw_val = m.group(1), m.group(2), m.group(3)
            attr_val = state.player_attributes.get(attr_name, 0)
            try:
                cmp_val = int(raw_val)
            except ValueError:
                cmp_val = float(raw_val)
            if op == ">=": return attr_val >= cmp_val
            if op == "<=": return attr_val <= cmp_val
            if op == ">":  return attr_val > cmp_val
            if op == "<":  return attr_val < cmp_val
            if op == "==": return attr_val == cmp_val
            if op == "!=": return attr_val != cmp_val

        # ── cycle ──
        m = re.match(r"^cycle>=(\d+)$", condition)
        if m:
            return state.cycle_count >= int(m.group(1))

        # ── half_cycle ──
        m = re.match(r"^half_cycle>=(\d+)$", condition)
        if m:
            return state.half_cycle_count >= int(m.group(1))

        # ── at_node ──
        m = re.match(r"^at_node:(.+)$", condition)
        if m:
            return state.current_node_id == m.group(1)

        raise ValueError(f"Unknown condition expression: {condition}")

    def _split_top_level(self, text: str) -> list[str]:
        """在顶层逗号处分割，不切割嵌套括号内的逗号。
        条件表达式嵌套深度最多 1 层 (and/or 内嵌简单条件)，
        所以简单的括号计数即可。"""
        parts = []
        depth = 0
        current = []
        for ch in text:
            if ch == "," and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                if ch == "(": depth += 1
                elif ch == ")": depth -= 1
                current.append(ch)
        if current:
            parts.append("".join(current).strip())
        return [p for p in parts if p]
```

- [ ] **Step 4: 运行测试验证全部通过**

```bash
cd backend
python -m pytest tests/test_condition_eval.py -v
```

Expected: 全部 17 个测试 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/__init__.py backend/app/engine/condition_eval.py backend/tests/
git commit -m "feat: implement condition expression evaluator with 17 tests"
```

---

### Task 5: 图结构加载器

**Files:**
- Create: `backend/app/engine/graph.py`

**Consumes:** SQLAlchemy session, ORM models from Task 2
**Produces:** `GraphLoader` 类，提供 `load_all(session) -> dict[str, GraphBundle]` 加载整个剧本图为内存数据结构

- [ ] **Step 1: 实现 graph.py**

```python
# backend/app/engine/graph.py
import json
from sqlalchemy.orm import Session
from ..models.story import StoryNode as StoryNodeModel, Choice as ChoiceModel


class GraphBundle:
    """一个节点的完整数据：节点本体 + 它的所有选择。"""
    def __init__(self, node: StoryNodeModel, choices: list[ChoiceModel]):
        self.id = node.id
        self.name = node.name
        self.position = node.position
        self.node_type = node.node_type
        self.time_label = node.time_label
        self.content = node.content
        self.speaker = node.speaker
        self.background = node.background
        self.cycle_variants = self._safe_json(node.cycle_variants_json, {})
        self.color_palette = node.color_palette
        self.atmosphere = self._safe_json(node.atmosphere_json, [])
        self.sensory = node.sensory
        self.gender_variant = self._safe_json(node.gender_variant_json, None)
        self.parent_node_id = node.parent_node_id
        self.trigger_condition = node.trigger_condition
        self.crossing_config = self._safe_json(node.crossing_config_json, None)
        self.warp_config = self._safe_json(node.warp_config_json, None)
        self.shortcut_config = self._safe_json(node.shortcut_config_json, None)
        self.npc_item_mapping = self._safe_json(node.npc_item_mapping_json, None)
        self.scene_items = self._safe_json(node.scene_items_json, None)

        self.choices: list[ChoiceData] = []
        for c in choices:
            self.choices.append(ChoiceData(
                id=c.id,
                from_node_id=c.from_node_id,
                text=c.text,
                short_text=c.short_text,
                next_node_id=c.next_node_id,
                condition=c.condition,
                effects=self._safe_json(c.effects_json, []),
                priority=c.priority,
                hint=c.hint,
                is_hidden_when_locked=bool(c.is_hidden_when_locked),
                transition_text=c.transition_text,
            ))

    @staticmethod
    def _safe_json(raw, default):
        if raw is None:
            return default
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return default


class ChoiceData:
    def __init__(self, id, from_node_id, text, short_text, next_node_id,
                 condition, effects, priority, hint, is_hidden_when_locked, transition_text):
        self.id = id
        self.from_node_id = from_node_id
        self.text = text
        self.short_text = short_text
        self.next_node_id = next_node_id
        self.condition = condition
        self.effects = effects
        self.priority = priority
        self.hint = hint
        self.is_hidden_when_locked = is_hidden_when_locked
        self.transition_text = transition_text


class GraphLoader:
    """从数据库加载整个故事图为字典 {node_id: GraphBundle}。"""

    def load_all(self, session: Session) -> dict[str, GraphBundle]:
        nodes = session.query(StoryNodeModel).all()
        choices = session.query(ChoiceModel).all()

        choices_by_node: dict[str, list[ChoiceModel]] = {}
        for c in choices:
            choices_by_node.setdefault(c.from_node_id, []).append(c)

        graph: dict[str, GraphBundle] = {}
        for node in nodes:
            node_choices = choices_by_node.get(node.id, [])
            node_choices.sort(key=lambda c: c.priority)
            graph[node.id] = GraphBundle(node, node_choices)

        return graph

    def get_node(self, graph: dict[str, GraphBundle], node_id: str) -> GraphBundle:
        if node_id not in graph:
            raise ValueError(f"Node '{node_id}' not found in graph")
        return graph[node_id]

    def get_choice(self, bundle: GraphBundle, choice_id: str) -> ChoiceData:
        for c in bundle.choices:
            if c.id == choice_id:
                return c
        raise ValueError(f"Choice '{choice_id}' not found in node '{bundle.id}'")
```

- [ ] **Step 2: 验证 — 手动导入测试（此时数据库为空，验证代码无语法错误）**

```bash
cd backend
python -c "from app.engine.graph import GraphLoader, GraphBundle; print('GraphLoader imported OK')"
```

Expected: `GraphLoader imported OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/engine/graph.py
git commit -m "feat: implement graph loader — loads story nodes and choices from DB"
```

---

### Task 6: 游戏引擎核心

**Files:**
- Create: `backend/app/engine/engine.py`
- Create: `backend/tests/test_engine.py`

**Consumes:** `graph.py`, `condition_eval.py`, `GameState`/`Frame` schemas
**Produces:** `GameEngine` 类，提供 `process_choice(graph, node_id, choice_id, state, save_id=None) -> Frame`

- [ ] **Step 1: 创建 test_engine.py — 单元测试**

```python
# backend/tests/test_engine.py
import pytest
from unittest.mock import MagicMock, patch
from app.engine.engine import GameEngine
from app.engine.graph import GraphBundle, ChoiceData
from app.schemas.game import GameState, Frame


def make_state(**kwargs):
    defaults = {
        "current_node_id": "A",
        "cycle_count": 1,
        "inventory": [],
        "flags": {},
        "visited_nodes": [],
        "endings_reached": [],
        "player_attributes": {"sanity": 100, "courage": 5, "insight": 3},
    }
    defaults.update(kwargs)
    return GameState(**defaults)


def make_choice(id, next_node_id, condition=None, effects=None):
    return ChoiceData(
        id=id, from_node_id="A", text="Go", short_text="Go",
        next_node_id=next_node_id, condition=condition,
        effects=effects or [], priority=1, hint=None,
        is_hidden_when_locked=False, transition_text=None,
    )


def make_bundle(node_id, choices):
    from app.engine.graph import GraphBundle
    from app.models.story import StoryNode as StoryNodeModel
    node = StoryNodeModel(
        id=node_id, name="Test", position=0.0, node_type="main",
        content="Test content", speaker=None, background=None,
        time_label=None,
    )
    return GraphBundle(node, [])


@pytest.fixture
def graph():
    node_a = MagicMock(spec=StoryNodeModel)
    node_a.id = "A"
    node_a.name = "Start"
    node_a.position = 0.0
    node_a.node_type = "main"
    node_a.time_label = "Day 1"
    node_a.content = "You are at start."
    node_a.speaker = None
    node_a.background = None
    node_a.cycle_variants_json = "{}"
    node_a.atmosphere_json = "[]"
    node_a.sensory = None
    node_a.color_palette = None
    node_a.gender_variant_json = None
    node_a.parent_node_id = None
    node_a.trigger_condition = None
    node_a.crossing_config_json = None
    node_a.warp_config_json = None
    node_a.shortcut_config_json = None
    node_a.npc_item_mapping_json = None
    node_a.scene_items_json = None

    node_b = MagicMock(spec=StoryNodeModel)
    node_b.id = "B"
    node_b.name = "Room"
    node_b.position = 25.0
    node_b.node_type = "main"
    node_b.time_label = "Day 1 Night"
    node_b.content = "You enter the room."
    node_b.speaker = None
    node_b.background = None
    node_b.cycle_variants_json = "{}"
    node_b.atmosphere_json = "[]"
    node_b.sensory = None
    node_b.color_palette = None
    node_b.gender_variant_json = None
    node_b.parent_node_id = None
    node_b.trigger_condition = None
    node_b.crossing_config_json = None
    node_b.warp_config_json = None
    node_b.shortcut_config_json = None
    node_b.npc_item_mapping_json = None
    node_b.scene_items_json = None

    choice = MagicMock()
    choice.id = "A_choice_01"
    choice.from_node_id = "A"
    choice.text = "Go to B"
    choice.short_text = "Go"
    choice.next_node_id = "B"
    choice.condition = None
    choice.effects_json = '[{"type":"set_flag","target":"moved","value":true}]'
    choice.priority = 1
    choice.hint = None
    choice.is_hidden_when_locked = 0
    choice.transition_text = None

    return {
        "A": GraphBundle(node_a, [choice]),
        "B": GraphBundle(node_b, []),
    }


def test_process_choice_basic(graph):
    engine = GameEngine()
    state = make_state(current_node_id="A")
    frame = engine.process_choice(graph, "A", "A_choice_01", state)

    assert frame.node.id == "B"
    assert frame.state.current_node_id == "B"
    assert frame.state.flags.get("moved") == True
    assert len(frame.available_choices) == 0


def test_process_choice_condition_blocked(graph):
    engine = GameEngine()
    # modify the choice to have a blocking condition
    from app.engine.graph import ChoiceData
    graph["A"].choices[0] = ChoiceData(
        id="A_choice_01", from_node_id="A", text="Go", short_text="Go",
        next_node_id="B", condition="has_item:item_key",
        effects=[], priority=1, hint="Need key",
        is_hidden_when_locked=False, transition_text=None,
    )

    state = make_state(current_node_id="A", inventory=[])
    with pytest.raises(ValueError, match="Condition not met"):
        engine.process_choice(graph, "A", "A_choice_01", state)


def test_resolve_choices_includes_warp(graph):
    engine = GameEngine()
    state = make_state(current_node_id="A", flags={"taoist_chant": True})

    choices = engine.resolve_available_choices(graph, "A", state)
    # 应该包含静态 choice + special_router 注入的 K 入口
    choice_ids = [c.id for c in choices]
    assert "A_choice_01" in choice_ids
    # 如果有 taoist_chant flag，K 入口应该出现
    has_warp = any(c.source == "special_warp" for c in choices)
    assert has_warp == True
```

- [ ] **Step 2: 实现 engine.py**

```python
# backend/app/engine/engine.py
from .graph import GraphBundle, ChoiceData
from .condition_eval import ConditionEvaluator
from .special_router import SpecialRouter
from ..schemas.game import GameState, Frame, NodeData, ChoiceResult, PersistentFound


class GameEngine:
    def __init__(self):
        self.evaluator = ConditionEvaluator()
        self.special_router = SpecialRouter(self.evaluator)

    def process_choice(
        self,
        graph: dict[str, GraphBundle],
        node_id: str,
        choice_id: str,
        state: GameState,
        save_id: str | None = None,
    ) -> Frame:
        bundle = graph[node_id]

        # ① 检查是否为特殊路由选项
        if choice_id.startswith("__"):
            choice = self.special_router.resolve(choice_id, bundle, graph, state)
        else:
            choice = self._find_choice(bundle, choice_id)

        # ② 条件校验
        if choice.condition and not self.evaluator.evaluate(choice.condition, state):
            raise ValueError(f"Condition not met: {choice.condition}")

        # ③ 应用 Effects
        self._apply_effects(choice.effects, state, node_id)

        # ④ 跳转目标节点
        next_bundle = graph[choice.next_node_id]
        state.current_node_id = next_bundle.id

        # ⑤ 循环检测
        cycle_event = None
        if next_bundle.id == "A" and len(state.visited_nodes) > 0:
            state.cycle_count += 1
            state.visited_nodes = []
            cycle_event = {
                "type": "cycle_complete",
                "cycle_count": state.cycle_count,
                "half_cycle_count": state.half_cycle_count,
            }

        # ⑥ 解析可用选项
        available = self.resolve_available_choices(graph, next_bundle.id, state)

        # ⑦ 构建 Frame
        return Frame(
            node=NodeData(
                id=next_bundle.id,
                name=next_bundle.name,
                node_type=next_bundle.node_type,
                position=next_bundle.position,
                time_label=next_bundle.time_label,
                content=self._resolve_content(next_bundle, state),
                speaker=next_bundle.speaker,
                background=next_bundle.background,
            ),
            state=state,
            available_choices=available,
            persistent_found=PersistentFound(),
            cycle_event=cycle_event,
        )

    def resolve_available_choices(
        self, graph: dict[str, GraphBundle], node_id: str, state: GameState
    ) -> list[ChoiceResult]:
        bundle = graph[node_id]
        results = []

        for c in bundle.choices:
            available = self.evaluator.check(c.condition, state)
            if c.is_hidden_when_locked and not available:
                continue
            results.append(ChoiceResult(
                id=c.id,
                text=c.text,
                short_text=c.short_text,
                available=available,
                reason=None if available else (c.hint or f"需要满足条件: {c.condition}"),
                source="static",
            ))

        # 注入特殊路由选项
        specials = self.special_router.get_available(bundle, graph, state)
        results.extend(specials)

        results.sort(key=lambda r: (
            0 if r.source != "static" else 1,
            next((c.priority for c in bundle.choices if c.id == r.id), 99)
        ))
        return results

    def _find_choice(self, bundle: GraphBundle, choice_id: str) -> ChoiceData:
        for c in bundle.choices:
            if c.id == choice_id:
                return c
        raise ValueError(f"Choice '{choice_id}' not found in node '{bundle.id}'")

    def _apply_effects(self, effects: list[dict], state: GameState, node_id: str):
        for effect in effects:
            etype = effect.get("type")
            target = effect.get("target", "")
            value = effect.get("value")

            if etype == "add_item":
                state.inventory.append({"id": target, "name": target, "count": value})
            elif etype == "remove_item":
                state.inventory = [i for i in state.inventory if i.get("id") != target]
            elif etype == "set_flag":
                state.flags[target] = value
            elif etype == "remove_flag":
                state.flags.pop(target, None)
            elif etype == "heal":
                attr = state.player_attributes.get(target, 0)
                state.player_attributes[target] = min(attr + value, 100)
            elif etype == "damage":
                attr = state.player_attributes.get(target, 100)
                state.player_attributes[target] = max(attr - value, 0)
            elif etype == "set_attr":
                state.player_attributes[target] = value

    def _resolve_content(self, bundle: GraphBundle, state: GameState) -> str:
        """解析 cycle_variants + {{变量}} 替换。"""
        variants = bundle.cycle_variants or {}
        content = bundle.content

        # 匹配最精确的 cycle variant
        for key in [f"cycle_{state.cycle_count}", f"cycle_{state.cycle_count}+"]:
            if key in variants and variants[key]:
                content = variants[key]
                break
        else:
            for key in sorted(variants.keys()):
                if key.endswith("+") and state.cycle_count >= int(key.replace("cycle_", "").replace("+", "")):
                    if variants[key]:
                        content = variants[key]

        # {{变量}} 替换
        content = content.replace("{{cycle_count}}", str(state.cycle_count))
        content = content.replace("{{half_cycle_count}}", str(state.half_cycle_count))
        for attr_name, attr_val in state.player_attributes.items():
            content = content.replace(f"{{{{attr:{attr_name}}}}}", str(attr_val))

        return content
```

- [ ] **Step 3: 实现 special_router.py（最小化 — K 入口仅在条件满足时注入）**

```python
# backend/app/engine/special_router.py
from .graph import GraphBundle, ChoiceData
from ..schemas.game import ChoiceResult, GameState


class SpecialRouter:
    def __init__(self, evaluator):
        self.evaluator = evaluator

    def get_available(
        self, bundle: GraphBundle, graph: dict[str, GraphBundle], state: GameState
    ) -> list[ChoiceResult]:
        results = []

        # K 跃迁入口
        warp_node = graph.get("K")
        if warp_node and warp_node.warp_config and bundle.id != "K":
            entry_cond = warp_node.warp_config.get("entry_condition")
            if entry_cond and self.evaluator.check(entry_cond, state):
                entry_text = warp_node.warp_config.get("entry_text", "踏入跃迁裂隙")
                results.append(ChoiceResult(
                    id="__warp_K_enter",
                    text=entry_text,
                    available=True,
                    source="special_warp",
                ))

        # K 从内部跳转到各目标
        if bundle.id == "K" and warp_node and warp_node.warp_config:
            targets = warp_node.warp_config.get("warp_targets", [])
            for target_id in targets:
                if target_id in graph:
                    target = graph[target_id]
                    results.append(ChoiceResult(
                        id=f"__warp_K_exit_{target_id}",
                        text=f"跃迁至{target.name}（{target.id}）",
                        available=True,
                        source="special_warp",
                    ))

        return results

    def resolve(
        self, choice_id: str, bundle: GraphBundle,
        graph: dict[str, GraphBundle], state: GameState
    ) -> ChoiceData:
        if choice_id == "__warp_K_enter":
            return ChoiceData(
                id=choice_id, from_node_id=bundle.id,
                text="踏入跃迁裂隙", short_text="跃迁",
                next_node_id="K", condition=None, effects=[],
                priority=0, hint=None, is_hidden_when_locked=False,
                transition_text="灰白色的虚空在你周围展开。脚下暗红色的光脉在缓慢搏动。",
            )
        if choice_id.startswith("__warp_K_exit_"):
            target_id = choice_id.replace("__warp_K_exit_", "")
            return ChoiceData(
                id=choice_id, from_node_id="K",
                text=f"跃迁至{target_id}", short_text=f"→{target_id}",
                next_node_id=target_id, condition=None,
                effects=[
                    {"type": "set_attr", "target": "sanity_max", "value": -1}
                ],
                priority=10, hint="消耗san值上限-1",
                is_hidden_when_locked=False,
                transition_text=f"暗红色的光吞没了一切。再睁开眼时——你已到达{target_id}。",
            )
        raise ValueError(f"Unknown special choice: {choice_id}")
```

- [ ] **Step 4: 运行测试**

```bash
cd backend
python -m pytest tests/test_engine.py -v
```

Expected: `test_process_choice_basic` PASS, `test_process_choice_condition_blocked` PASS, `test_resolve_choices_includes_warp` PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/engine/engine.py backend/app/engine/special_router.py backend/tests/test_engine.py
git commit -m "feat: implement game engine — process_choice + special router"
```

---

### Task 7: 故事数据导入脚本

**Files:**
- Create: `backend/import_story.py`

**Consumes:** `story_data/` 目录下的 JSON 文件，ORM 模型
**Produces:** 将 30 个节点 + 所有 choice + flag/item/npc 定义写入 SQLite

- [ ] **Step 1: 创建 import_story.py**

```python
# backend/import_story.py
"""将 story_data/ 下的 JSON 文件导入 SQLite 数据库。"""
import json
import os
import sys
from datetime import datetime
from app.database import SessionLocal, init_db, engine, Base
from app.models.story import StoryNode, Choice
from app.config import STORY_DATA_DIR


def import_all():
    init_db()

    # 清空已有故事数据
    with SessionLocal() as session:
        session.execute("DELETE FROM choices")
        session.execute("DELETE FROM node_persistent_state")
        session.execute("DELETE FROM saves")
        session.execute("DELETE FROM story_nodes")
        session.commit()

    with SessionLocal() as session:
        _import_nodes(session)
        _import_choices(session)
        session.commit()
        _verify(session)


def _import_nodes(session):
    nodes_dir = os.path.join(STORY_DATA_DIR, "05_nodes")
    count = 0
    for fname in sorted(os.listdir(nodes_dir)):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(nodes_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        node = StoryNode(
            id=data["id"],
            name=data["name"],
            position=data["position"],
            node_type=data["node_type"],
            time_label=data.get("time_label"),
            content=data["content"],
            speaker=data.get("speaker"),
            background=data.get("background"),
            cycle_variants_json=json.dumps(data.get("cycle_variants", {}), ensure_ascii=False),
            color_palette=data.get("color_palette"),
            atmosphere_json=json.dumps(data.get("atmosphere", []), ensure_ascii=False),
            sensory=data.get("sensory"),
            gender_variant_json=json.dumps(data.get("gender_variant"), ensure_ascii=False) if data.get("gender_variant") else None,
            parent_node_id=data.get("parent_node_id"),
            trigger_condition=data.get("trigger_condition"),
            crossing_config_json=json.dumps(data.get("crossing_config"), ensure_ascii=False) if data.get("crossing_config") else None,
            warp_config_json=json.dumps(data.get("warp_config"), ensure_ascii=False) if data.get("warp_config") else None,
            shortcut_config_json=json.dumps(data.get("shortcut_config"), ensure_ascii=False) if data.get("shortcut_config") else None,
            npc_item_mapping_json=json.dumps(data.get("npc_item_mapping"), ensure_ascii=False) if data.get("npc_item_mapping") else None,
            scene_items_json=json.dumps(data.get("scene_items"), ensure_ascii=False) if data.get("scene_items") else None,
        )
        session.add(node)
        count += 1
    print(f"[import_nodes] Imported {count} nodes")


def _import_choices(session):
    choices_dir = os.path.join(STORY_DATA_DIR, "06_choices")
    count = 0
    for fname in sorted(os.listdir(choices_dir)):
        if not fname.endswith(".json"):
            continue
        filepath = os.path.join(choices_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            choices = json.load(f)

        for c in choices:
            choice = Choice(
                id=c["id"],
                from_node_id=c["from_node_id"],
                text=c["text"],
                short_text=c.get("short_text"),
                next_node_id=c["next_node_id"],
                condition=c.get("condition"),
                effects_json=json.dumps(c.get("effects", []), ensure_ascii=False),
                priority=c.get("priority", 99),
                hint=c.get("hint"),
                is_hidden_when_locked=1 if c.get("is_hidden_when_locked") else 0,
                transition_text=c.get("transition_text"),
            )
            session.add(choice)
            count += 1
    print(f"[import_choices] Imported {count} choices")


def _verify(session):
    node_count = session.query(StoryNode).count()
    choice_count = session.query(Choice).count()
    print(f"[verify] Database has {node_count} nodes, {choice_count} choices")

    # 引用完整性检查
    bad_choices = session.execute("""
        SELECT c.id, c.next_node_id FROM choices c
        WHERE c.next_node_id NOT IN (SELECT id FROM story_nodes)
    """).fetchall()
    if bad_choices:
        print(f"[verify] WARNING: {len(bad_choices)} choices point to non-existent nodes:")
        for bc in bad_choices:
            print(f"  {bc[0]} -> {bc[1]}")
    else:
        print("[verify] All choice targets valid ✓")


if __name__ == "__main__":
    import_all()
```

- [ ] **Step 2: 运行导入脚本**

```bash
cd backend
python import_story.py
```

Expected:
```
[import_nodes] Imported 30 nodes
[import_choices] Imported N choices
[verify] Database has 30 nodes, N choices
[verify] All choice targets valid ✓
```

- [ ] **Step 3: Commit**

```bash
git add backend/import_story.py
git commit -m "feat: add story data import script — imports 30 nodes + choices from JSON to SQLite"
```

---

### Task 8: API 路由

**Files:**
- Create: `backend/app/routers/__init__.py`
- Create: `backend/app/routers/game.py`
- Create: `backend/app/routers/saves.py`
- Create: `backend/app/routers/editor.py`
- Modify: `backend/app/main.py`

**Consumes:** Engine, graph, database, schemas from Tasks 1-7
**Produces:** FastAPI 端点 — `/api/game/start`, `/api/game/choose/{node_id}`

- [ ] **Step 1: 创建 routers/__init__.py（空文件）**

```bash
touch backend/app/routers/__init__.py
```

- [ ] **Step 2: 创建 routers/game.py**

```python
# backend/app/routers/game.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..engine.graph import GraphLoader
from ..engine.engine import GameEngine
from ..schemas.game import Frame, ChooseRequest, GameState

router = APIRouter(prefix="/api/game", tags=["game"])
loader = GraphLoader()
engine = GameEngine()

# 按请求加载图（Phase 1 简化：每次 API 调用重新加载）
def _get_graph(db: Session):
    return loader.load_all(db)


@router.get("/start", response_model=Frame)
def start_game(db: Session = Depends(get_db)):
    graph = _get_graph(db)
    state = GameState(current_node_id="A")
    # 直接返回 A 节点的内容 + 可选选项
    return engine.process_choice.__wrapped__ if False else _start_frame(graph, state)


def _start_frame(graph, state):
    """特殊处理：start 不是从一个 choice 来的，而是初始化。"""
    bundle = graph["A"]
    state.current_node_id = "A"
    available = engine.resolve_available_choices(graph, "A", state)
    from ..schemas.game import NodeData
    return Frame(
        node=NodeData(
            id=bundle.id, name=bundle.name, node_type=bundle.node_type,
            position=bundle.position, time_label=bundle.time_label,
            content=engine._resolve_content(bundle, state),
            speaker=bundle.speaker, background=bundle.background,
        ),
        state=state,
        available_choices=available,
    )


@router.post("/choose/{node_id}", response_model=Frame)
def choose_action(node_id: str, req: ChooseRequest, db: Session = Depends(get_db)):
    graph = _get_graph(db)
    # 从请求中恢复状态（Phase 1: 前端持有完整 state）
    # 实际 state 由前端在请求中传递（简化为从 query param 或 body 获取）
    # Phase 1 简化：创建一个 fresh state 用于测试
    state = GameState(current_node_id=node_id)
    try:
        frame = engine.process_choice(graph, node_id, req.choice_id, state)
        return frame
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

- [ ] **Step 3: 创建 routers/saves.py（最小实现）**

```python
# backend/app/routers/saves.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/saves", tags=["saves"])

# Phase 1: 最小存根 — 后续 Phase 2 实现完整 CRUD
@router.get("/")
def list_saves():
    return {"saves": [], "message": "Save system available in Phase 2"}
```

- [ ] **Step 4: 创建 routers/editor.py（最小实现）**

```python
# backend/app/routers/editor.py
from fastapi import APIRouter

router = APIRouter(prefix="/api/editor", tags=["editor"])

# Phase 1: 最小存根 — 后续 Phase 3 实现完整 CRUD
@router.get("/nodes")
def list_nodes():
    return {"nodes": [], "message": "Editor available in Phase 3"}
```

- [ ] **Step 5: 创建 main.py**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .routers import game, saves, editor

app = FastAPI(title="Cycle Master API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(game.router)
app.include_router(saves.router)
app.include_router(editor.router)


@app.on_event("startup")
def on_startup():
    init_db()


@app.get("/api/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 6: 启动后端并验证 API**

```bash
cd backend
python -m uvicorn app.main:app --reload --port 8000
```

在另一个终端：

```bash
# 验证 health
curl http://localhost:8000/api/health

# 验证 game start
curl http://localhost:8000/api/game/start | python -m json.tool

# 验证 choose (用 A 节点的第一条 choice)
curl -X POST http://localhost:8000/api/game/choose/A \
  -H "Content-Type: application/json" \
  -d '{"choice_id": "A_choice_01"}' | python -m json.tool
```

Expected:
- `/api/health` → `{"status": "ok"}`
- `/api/game/start` → 返回 Frame JSON，node.id="A"，available_choices 包含 12 条选项
- `/api/game/choose/A` → 返回 Frame JSON，node.id="B"

- [ ] **Step 7: Commit**

```bash
git add backend/app/main.py backend/app/routers/
git commit -m "feat: implement REST API — game start/choose, saves stub, editor stub"
```

---

### Task 9: 前端项目初始化

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`

- [ ] **Step 1: 创建 package.json**

```bash
cd frontend
npm init -y
npm install vue@3 vue-router@4 pinia@2 element-plus axios
npm install -D typescript @vitejs/plugin-vue vite sass
```

- [ ] **Step 2: 创建 vite.config.ts**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: 创建 tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "module": "ESNext",
    "moduleResolution": "bundler",
    "strict": true,
    "jsx": "preserve",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "esModuleInterop": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "noEmit": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["src/**/*.ts", "src/**/*.d.ts", "src/**/*.vue"]
}
```

- [ ] **Step 4: 创建 index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>荔湾·四日轮回 - Cycle Master</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **Step 5: 创建 src/main.ts**

```typescript
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'
import './assets/styles/global.scss'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.use(ElementPlus)
app.mount('#app')
```

- [ ] **Step 6: 创建 src/App.vue**

```vue
<template>
  <router-view />
</template>
```

- [ ] **Step 7: 创建样式文件**

```scss
// frontend/src/assets/styles/variables.scss
$bg-dark: #1a1a2e;
$bg-panel: #16213e;
$text-primary: #e0d5c1;
$text-secondary: #a09080;
$accent-gold: #c9a96e;
$accent-red: #8b2500;
$font-body: 'Noto Serif SC', 'Source Han Serif SC', 'SimSun', serif;
```

```scss
// frontend/src/assets/styles/global.scss
@import './variables.scss';

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
  background: $bg-dark;
  color: $text-primary;
  font-family: $font-body;
  font-size: 16px;
  line-height: 1.8;
}

#app {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
}
```

- [ ] **Step 8: 验证前端启动**

```bash
cd frontend
npx vite --port 5173
```

Expected: Vite dev server 启动在 `http://localhost:5173`，页面空白但无报错。

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat: initialize Vue 3 frontend with Vite + Element Plus + Pinia + SCSS"
```

---

### Task 10: 前端类型定义 + API 客户端

**Files:**
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/game.ts`
- Create: `frontend/src/router/index.ts`

- [ ] **Step 1: 创建 types/index.ts**

```typescript
// frontend/src/types/index.ts
export interface GameState {
  current_node_id: string
  cycle_count: number
  half_cycle_count: number
  inventory: ItemBrief[]
  flags: Record<string, any>
  visited_nodes: string[]
  endings_reached: string[]
  player_attributes: Record<string, number>
}

export interface ItemBrief {
  id: string
  name: string
  count?: number
}

export interface NodeData {
  id: string
  name: string
  node_type: string
  position: number
  time_label?: string
  content: string
  speaker?: string
  background?: string
}

export interface ChoiceResult {
  id: string
  text: string
  short_text?: string
  available: boolean
  reason?: string
  source: 'static' | 'special_shortcut' | 'special_warp'
}

export interface PersistentFound {
  items: ItemBrief[]
  cross_surface_items: ItemBrief[]
  dangers: any[]
}

export interface CycleEvent {
  type: string
  cycle_count: number
  half_cycle_count: number
}

export interface Frame {
  node: NodeData
  state: GameState
  available_choices: ChoiceResult[]
  persistent_found: PersistentFound
  cycle_event: CycleEvent | null
}
```

- [ ] **Step 2: 创建 api/game.ts**

```typescript
// frontend/src/api/game.ts
import axios from 'axios'
import type { Frame } from '@/types'

const api = axios.create({ baseURL: '/api' })

export async function startGame(): Promise<Frame> {
  const res = await api.get<Frame>('/game/start')
  return res.data
}

export async function chooseAction(nodeId: string, choiceId: string): Promise<Frame> {
  const res = await api.post<Frame>(`/game/choose/${nodeId}`, { choice_id: choiceId })
  return res.data
}
```

- [ ] **Step 3: 创建 router/index.ts**

```typescript
// frontend/src/router/index.ts
import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/play' },
    {
      path: '/play',
      name: 'play',
      component: () => import('@/views/GamePlay.vue'),
    },
    {
      path: '/editor',
      name: 'editor',
      component: () => import('@/views/EditorPlaceholder.vue'),
    },
  ],
})

export default router
```

- [ ] **Step 4: 创建 EditorPlaceholder.vue**

```vue
<!-- frontend/src/views/EditorPlaceholder.vue -->
<template>
  <div class="editor-placeholder">
    <h1>可视化编辑器</h1>
    <p>Phase 3 实现</p>
  </div>
</template>
```

- [ ] **Step 5: 验证 — TypeScript 编译**

```bash
cd frontend
npx vue-tsc --noEmit
```

Expected: 无类型错误（或仅有未使用变量 warning）。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/types/ frontend/src/api/ frontend/src/router/ frontend/src/views/EditorPlaceholder.vue
git commit -m "feat: add TypeScript types, API client, router for frontend"
```

---

### Task 11: 前端游戏状态管理 + 播放器组件

**Files:**
- Create: `frontend/src/stores/gameStore.ts`
- Create: `frontend/src/views/GamePlay.vue`
- Create: `frontend/src/components/player/NarrativePanel.vue`
- Create: `frontend/src/components/player/ChoicePanel.vue`
- Create: `frontend/src/components/player/ChoiceButton.vue`
- Create: `frontend/src/components/player/StatusBar.vue`

- [ ] **Step 1: 创建 stores/gameStore.ts**

```typescript
// frontend/src/stores/gameStore.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Frame, GameState, NodeData, ChoiceResult } from '@/types'
import { startGame, chooseAction } from '@/api/game'

export const useGameStore = defineStore('game', () => {
  const currentFrame = ref<Frame | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const history = ref<Frame[]>([])

  const currentNode = computed<NodeData | null>(() => currentFrame.value?.node ?? null)
  const currentState = computed<GameState | null>(() => currentFrame.value?.state ?? null)
  const choices = computed<ChoiceResult[]>(() => currentFrame.value?.available_choices ?? [])
  const cycleEvent = computed(() => currentFrame.value?.cycle_event ?? null)

  async function init() {
    loading.value = true
    error.value = null
    try {
      const frame = await startGame()
      currentFrame.value = frame
      history.value = [frame]
    } catch (e: any) {
      error.value = e.message || 'Failed to start game'
    } finally {
      loading.value = false
    }
  }

  async function choose(choiceId: string) {
    if (!currentFrame.value) return
    const nodeId = currentFrame.value.node.id
    loading.value = true
    error.value = null
    try {
      const frame = await chooseAction(nodeId, choiceId)
      currentFrame.value = frame
      history.value.push(frame)
    } catch (e: any) {
      error.value = e.message || 'Failed to process choice'
    } finally {
      loading.value = false
    }
  }

  return { currentFrame, loading, error, history, currentNode, currentState, choices, cycleEvent, init, choose }
})
```

- [ ] **Step 2: 创建 components/player/NarrativePanel.vue**

```vue
<!-- frontend/src/components/player/NarrativePanel.vue -->
<template>
  <div class="narrative-panel">
    <div v-if="speaker" class="speaker-tag">{{ speaker }}</div>
    <div class="narrative-text" v-html="renderedContent"></div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  content: string
  speaker?: string | null
}>()

const renderedContent = computed(() => {
  let text = props.content
  text = text.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*(.+?)\*/g, '<em>$1</em>')
  text = text.replace(/---/g, '<span class="scene-break">· · ·</span>')
  text = text.replace(/\n\n/g, '</p><p>')
  text = `<p>${text}</p>`
  return text
})
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.narrative-panel {
  padding: 2rem;
  max-width: 720px;
  margin: 0 auto;
}

.speaker-tag {
  color: $accent-gold;
  font-weight: bold;
  margin-bottom: 0.5rem;
  font-size: 1.1em;
}

.narrative-text {
  :deep(p) {
    margin-bottom: 1.2rem;
  }
  :deep(strong) {
    color: $accent-gold;
  }
  :deep(em) {
    color: $text-secondary;
  }
  :deep(.scene-break) {
    display: block;
    text-align: center;
    color: $accent-red;
    margin: 2rem 0;
    letter-spacing: 0.5em;
  }
}
</style>
```

- [ ] **Step 3: 创建 components/player/ChoiceButton.vue**

```vue
<!-- frontend/src/components/player/ChoiceButton.vue -->
<template>
  <button
    class="choice-button"
    :class="{ locked: !choice.available, warp: choice.source === 'special_warp' }"
    :disabled="!choice.available"
    @click="$emit('select', choice.id)"
  >
    <span class="choice-text">{{ choice.text }}</span>
    <span v-if="!choice.available && choice.reason" class="choice-reason">{{ choice.reason }}</span>
  </button>
</template>

<script setup lang="ts">
import type { ChoiceResult } from '@/types'

defineProps<{ choice: ChoiceResult }>()
defineEmits<{ select: [id: string] }>()
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.choice-button {
  display: block;
  width: 100%;
  padding: 0.8rem 1.2rem;
  margin-bottom: 0.6rem;
  background: $bg-panel;
  border: 1px solid rgba($accent-gold, 0.3);
  border-radius: 4px;
  color: $text-primary;
  font-family: inherit;
  font-size: 1rem;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;

  &:hover:not(.locked) {
    border-color: $accent-gold;
    background: lighten($bg-panel, 5%);
  }

  &.locked {
    opacity: 0.4;
    cursor: not-allowed;
  }

  &.warp {
    border-color: rgba($accent-red, 0.5);
    border-style: dashed;
  }
}

.choice-reason {
  display: block;
  font-size: 0.8rem;
  color: $text-secondary;
  margin-top: 0.3rem;
}
</style>
```

- [ ] **Step 4: 创建 components/player/ChoicePanel.vue**

```vue
<!-- frontend/src/components/player/ChoicePanel.vue -->
<template>
  <div class="choice-panel" v-if="choices.length > 0">
    <ChoiceButton
      v-for="choice in choices"
      :key="choice.id"
      :choice="choice"
      @select="$emit('select', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import type { ChoiceResult } from '@/types'
import ChoiceButton from './ChoiceButton.vue'

defineProps<{ choices: ChoiceResult[] }>()
defineEmits<{ select: [id: string] }>()
</script>

<style scoped lang="scss">
.choice-panel {
  padding: 1rem 2rem;
  max-width: 720px;
  margin: 0 auto;
}
</style>
```

- [ ] **Step 5: 创建 components/player/StatusBar.vue**

```vue
<!-- frontend/src/components/player/StatusBar.vue -->
<template>
  <div class="status-bar">
    <div class="status-item">
      <span class="status-label">循环</span>
      <span class="status-value">{{ cycle }}</span>
      <span v-if="halfCycle > 0" class="status-half">(半:{{ halfCycle }})</span>
    </div>
    <div class="status-item" v-for="(val, key) in attrs" :key="key">
      <span class="status-label">{{ key.toUpperCase() }}</span>
      <span class="status-value" :class="{ warn: isWarn(key, val) }">{{ val }}</span>
    </div>
    <div class="status-item" v-if="nodeName">
      <span class="status-label">📍</span>
      <span class="status-value">{{ nodeName }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  cycleCount: number
  halfCycleCount: number
  attributes: Record<string, number>
  nodeName?: string
}>()

const cycle = computed(() => props.cycleCount)
const halfCycle = computed(() => props.halfCycleCount)
const attrs = computed(() => props.attributes)

function isWarn(key: string, val: number): boolean {
  if (key === 'sanity') return val <= 30
  if (key === 'courage') return val <= 3
  return false
}
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.status-bar {
  display: flex;
  gap: 2rem;
  padding: 0.6rem 2rem;
  background: rgba(0, 0, 0, 0.5);
  border-bottom: 1px solid rgba($accent-gold, 0.2);
}

.status-item {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.status-label {
  color: $text-secondary;
  font-size: 0.85rem;
}

.status-value {
  color: $text-primary;
  font-weight: bold;

  &.warn { color: $accent-red; }
}

.status-half {
  color: $text-secondary;
  font-size: 0.75rem;
}
</style>
```

- [ ] **Step 6: 创建 views/GamePlay.vue**

```vue
<!-- frontend/src/views/GamePlay.vue -->
<template>
  <div class="game-play">
    <StatusBar
      v-if="store.currentState"
      :cycle-count="store.currentState.cycle_count"
      :half-cycle-count="store.currentState.half_cycle_count"
      :attributes="store.currentState.player_attributes"
      :node-name="store.currentNode?.name"
    />

    <div class="game-main">
      <div v-if="store.loading" class="loading">加载中...</div>
      <div v-else-if="store.error" class="error">{{ store.error }}</div>

      <template v-else-if="store.currentNode">
        <div class="time-label" v-if="store.currentNode.time_label">
          {{ store.currentNode.time_label }}
        </div>
        <NarrativePanel
          :content="store.currentNode.content"
          :speaker="store.currentNode.speaker"
        />
        <ChoicePanel
          :choices="store.choices"
          @select="handleChoice"
        />

        <div v-if="store.cycleEvent" class="cycle-event">
          ⏳ 第 {{ store.cycleEvent.cycle_count }} 次循环完成
        </div>
      </template>

      <div v-else class="start-screen">
        <h1>荔湾·四日轮回</h1>
        <button @click="store.init()">开始游戏</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useGameStore } from '@/stores/gameStore'
import NarrativePanel from '@/components/player/NarrativePanel.vue'
import ChoicePanel from '@/components/player/ChoicePanel.vue'
import StatusBar from '@/components/player/StatusBar.vue'

const store = useGameStore()

onMounted(() => {
  store.init()
})

function handleChoice(choiceId: string) {
  store.choose(choiceId)
}
</script>

<style scoped lang="scss">
@import '@/assets/styles/variables.scss';

.game-play {
  height: 100vh;
  display: flex;
  flex-direction: column;
}

.game-main {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 4rem;
}

.time-label {
  text-align: center;
  color: $text-secondary;
  font-size: 0.9rem;
  padding: 1rem 0 0;
}

.loading, .error {
  text-align: center;
  padding: 4rem;
}

.start-screen {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;

  h1 {
    font-size: 2.5rem;
    color: $accent-gold;
    margin-bottom: 2rem;
  }

  button {
    padding: 1rem 3rem;
    font-size: 1.2rem;
    background: $accent-red;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;

    &:hover { opacity: 0.9; }
  }
}

.cycle-event {
  text-align: center;
  color: $accent-gold;
  padding: 2rem;
  font-size: 1.1rem;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
</style>
```

- [ ] **Step 7: 验证 — 启动前端并测试完整流程**

```bash
# 终端1: 启动后端
cd backend
python -m uvicorn app.main:app --reload --port 8000

# 终端2: 启动前端
cd frontend
npx vite --port 5173
```

浏览器打开 `http://localhost:5173/play`

Expected:
1. 页面加载 → 显示 "荔湾·四日轮回" 标题 + "开始游戏" 按钮
2. 点击开始 → 显示 A 节点内容（"夕阳将荔湾广场圆弧形穹顶染成暗红色..."）
3. 顶部状态栏显示：循环 0 | SAN 100 | COU 5 | INS 3 | 📍 荔湾广场正门
4. 下方出现 10+ 个可点击选项按钮
5. 点击 "直接进入广场办理入住" → 显示 transition_text（电梯叙事），然后跳转到 B 节点
6. B 节点内容渲染正常，选项正常

- [ ] **Step 8: Commit**

```bash
git add frontend/src/stores/ frontend/src/views/GamePlay.vue frontend/src/components/player/
git commit -m "feat: implement game player — NarrativePanel, ChoicePanel, StatusBar, gameStore"
```

---

### Task 12: 端到端验证 + 环形 Demo 确认

- [ ] **Step 1: 确认 30 个节点数据全部导入**

```bash
cd backend
python -c "
from app.database import SessionLocal
from app.models.story import StoryNode, Choice
with SessionLocal() as s:
    nodes = s.query(StoryNode).all()
    choices = s.query(Choice).all()
    print(f'Nodes: {len(nodes)}')
    for n in sorted(nodes, key=lambda x: x.id):
        print(f'  {n.id}: {n.name} [{n.node_type}] pos={n.position}')
    print(f'Choices: {len(choices)}')
"
```

Expected: 30 nodes 列出（A~H, J, K, S1~S20），N choices（约 100+ 条）

- [ ] **Step 2: 测试完整 A→B→C→D→E→F→G→H→A 环形路径**

```bash
cd backend
python -c "
from app.database import SessionLocal
from app.engine.graph import GraphLoader
from app.engine.engine import GameEngine
from app.schemas.game import GameState

with SessionLocal() as db:
    graph = GraphLoader().load_all(db)
    engine = GameEngine()
    state = GameState(current_node_id='A')

    path = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    for node_id in path:
        bundle = graph[node_id]
        static_choices = [c for c in bundle.choices if c.condition is None]
        if static_choices:
            choice = static_choices[0]  # 选第一个无条件选项
            print(f'{node_id} -> {choice.next_node_id}: {choice.text}')
            frame = engine.process_choice(graph, node_id, choice.id, state)
            assert frame.node.id == choice.next_node_id, f'Expected {choice.next_node_id}, got {frame.node.id}'
        else:
            print(f'{node_id}: no choices available')

    print('Ring path traversal OK')
"
```

Expected: `Ring path traversal OK`

- [ ] **Step 3: 验证 K 节点跃迁**

```bash
cd backend
python -c "
from app.database import SessionLocal
from app.engine.graph import GraphLoader
from app.engine.engine import GameEngine
from app.schemas.game import GameState

with SessionLocal() as db:
    graph = GraphLoader().load_all(db)
    engine = GameEngine()
    state = GameState(current_node_id='A', flags={'taoist_chant': True})
    
    choices = engine.resolve_available_choices(graph, 'A', state)
    warp_choices = [c for c in choices if c.source == 'special_warp']
    print(f'Warp choices available from A: {len(warp_choices)}')
    if warp_choices:
        print(f'  {warp_choices[0].id}: {warp_choices[0].text}')
    
    # 实际跃迁到 K
    frame = engine.process_choice(graph, 'A', '__warp_K_enter', state)
    print(f'Arrived at: {frame.node.id} ({frame.node.name})')
    assert frame.node.id == 'K'
    
    # 从 K 跃迁到 B
    choices_at_K = engine.resolve_available_choices(graph, 'K', frame.state)
    exit_choices = [c for c in choices_at_K if c.id.startswith('__warp_K_exit_')]
    print(f'Destinations from K: {len(exit_choices)}')
    
    frame2 = engine.process_choice(graph, 'K', '__warp_K_exit_B', frame.state)
    print(f'Warped to: {frame2.node.id} ({frame2.node.name})')
    assert frame2.node.id == 'B'
    print('K warp traversal OK')
"
```

Expected: `K warp traversal OK`

- [ ] **Step 4: 验证条件表达式链**

```bash
cd backend
python -m pytest tests/ -v
```

Expected: 全部 test_condition_eval + test_engine 测试 PASS

- [ ] **Step 5: 最终 Commit**

```bash
git add -A
git commit -m "feat: Phase 1 complete — ring demo traversable, 30 nodes loaded, K warp working"
```

---

## Verification Checklist

完成所有 task 后验证：

- [ ] `python -m pytest backend/tests/ -v` — 全部测试 PASS
- [ ] `python backend/import_story.py` — 30 节点 + choices 导入成功
- [ ] `curl http://localhost:8000/api/game/start` — 返回 A 节点 Frame JSON
- [ ] `curl -X POST http://localhost:8000/api/game/choose/A -H "Content-Type: application/json" -d '{"choice_id":"A_choice_01"}'` — 返回 B 节点 Frame
- [ ] 前端 `http://localhost:5173/play` — 显示文本 + 可点击选项
- [ ] 环形路径 A→B→C→D→E→F→G→H→A 可遍历
- [ ] K 节点跃迁 A→K→B 正常工作
- [ ] 条件表达式 `has_item`、`has_flag`、`attr`、`cycle`、`and`/`or`/`not` 全部求值正确

---

> **版本**: v1.0
> **创建日期**: 2026-07-18
> **关联文档**: [技术实现方案.md](../../docs/design/技术实现方案.md) | [故事内容格式规范.md](../../docs/design/故事内容格式规范.md)
